"""What the app does: take uploads, process them in the background, record reviews,
approve products, compute action flags and export the inventory."""

import io
import json
import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from chemready.app.store import NewField, Row, Store
from chemready.config import Settings
from chemready.extraction.extract import PrivacyError, ScannedDocumentError, extract_sds
from chemready.extraction.llm import LlmClient, LlmError
from chemready.pdf.parse import PdfError, file_hash, parse_pdf, parse_pdf_bytes
from chemready.pdf.sections import missing_sections, split_sections
from chemready.validation.flags import ActionFlag, product_flags
from chemready.validation.rules import (
    cas_check_digit_ok,
    h_code_ok,
    iso_date_ok,
    pictogram_ok,
    signal_word_ok,
)
from chemready.validation.validate import validate_extraction

log = logging.getLogger("chemready.service")


class ServiceError(Exception):
    """A problem the user can fix. The message is safe to show."""


# ---------- Upload ----------


@dataclass(frozen=True)
class UploadResult:
    file_name: str
    accepted: bool
    message: str
    document_id: int | None = None


def accept_uploads(
    store: Store,
    settings: Settings,
    *,
    facility_id: int,
    user_id: int,
    files: list[tuple[str, bytes]],
    private: bool,
) -> list[UploadResult]:
    """Check each file and store the good ones. R1: clear message for every rejected file."""
    if len(files) > settings.max_batch_files:
        raise ServiceError(
            f"You selected {len(files)} files. Please select {settings.max_batch_files} or fewer."
        )
    results = []
    limit = settings.max_upload_mb * 1024 * 1024
    for name, data in files:
        if not name.lower().endswith(".pdf") or not data.startswith(b"%PDF"):
            results.append(UploadResult(name, False, "Not a PDF. Only PDF files can be added."))
            continue
        if len(data) > limit:
            results.append(
                UploadResult(
                    name, False, f"This file is larger than {settings.max_upload_mb} MB. Check it is one SDS."
                )
            )
            continue
        digest = file_hash(data)
        existing = store.document_by_hash(facility_id, digest)
        if existing:
            when = existing["uploaded_at"][:10]
            results.append(UploadResult(name, False, f"Already uploaded on {when}. Skipped."))
            continue
        path = settings.upload_dir / f"{facility_id}" / f"{digest}.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        document_id = store.add_document(facility_id, name, digest, str(path), user_id, private)
        results.append(UploadResult(name, True, "Added. Processing has started.", document_id))
    return results


# ---------- Background processing ----------


def _to_new_fields(checks: list[Any], extraction: Any) -> list[NewField]:
    fields = []
    for position, check in enumerate(checks):
        extra: dict[str, Any] = {}
        name = check.field_name
        if name.startswith("hazard_statements["):
            item = extraction.hazard_statements[int(name.split("[")[1].split("]")[0])]
            extra = {"statement": item.statement}
        elif name.startswith("ingredients["):
            item = extraction.ingredients[int(name.split("[")[1].split("]")[0])]
            extra = {"name": item.name, "percent": item.percent}
        fields.append(
            NewField(
                position=position,
                field_name=name,
                label=check.label,
                value=check.value,
                page=check.page,
                quote=check.quote,
                confidence=check.confidence,
                status=str(check.status),
                checks=check.checks,
                reasons=check.reasons,
                extra=extra,
            )
        )
    return fields


def process_document(
    store: Store,
    document_id: int,
    make_client: Callable[[], LlmClient],
    prices: tuple[float, float] = (0.0, 0.0),
) -> None:
    """Parse, extract and validate one document. Errors become a clear 'failed' status.

    The model client is wrapped so every call is traced with tokens, time and cost.
    """
    from chemready.app.observability import TracedClient
    from chemready.extraction.prompts import PROMPT_VERSION

    document = store.document_any_facility(document_id)
    if document is None:
        return
    try:
        store.set_status(document_id, "extracting", "Reading pages")
        parsed = parse_pdf(Path(document["storage_path"]))
        store.set_status(document_id, "extracting", "Finding sections")
        missing = missing_sections(split_sections(parsed))
        store.update_document_meta(document_id, parsed.page_count, parsed.is_scanned, missing)
        store.set_status(document_id, "extracting", "Extracting")
        client = TracedClient(
            make_client(),
            store,
            facility_id=document["facility_id"],
            document_id=document_id,
            prompt_version=PROMPT_VERSION,
            price_in=prices[0],
            price_out=prices[1],
        )
        run = extract_sds(parsed, client, private=bool(document["is_private"]))
        store.set_status(document_id, "extracting", "Checking")
        checks = validate_extraction(run.extraction, parsed)
        meta = {
            "pages": parsed.page_count,
            "is_scanned": int(parsed.is_scanned),
            "missing_sections": missing,
            "provider": run.usage.provider,
            "model": run.usage.model,
            "prompt_version": run.prompt_version,
            "input_tokens": run.usage.input_tokens,
            "output_tokens": run.usage.output_tokens,
            "latency_ms": run.usage.latency_ms,
        }
        store.save_extraction(document_id, meta, _to_new_fields(checks, run.extraction))
        log.info("document processed", extra={"document_id": document_id, **meta})
    except (PdfError, ScannedDocumentError) as error:
        store.set_status(document_id, "failed", "Failed", f"Could not read this file. {error}")
    except PrivacyError as error:
        store.set_status(document_id, "failed", "Failed", str(error))
    except LlmError as error:
        store.set_status(document_id, "failed", "Failed", f"The AI step failed: {error}")
    except Exception:  # never leave a document stuck in "extracting"
        log.exception("unexpected error while processing", extra={"document_id": document_id})
        store.set_status(document_id, "failed", "Failed", "Something went wrong. Try again.")


class Worker:
    """Processes documents one at a time in a background thread.

    One at a time keeps us inside free-tier rate limits. Documents left waiting
    when the server stopped are picked up again at start-up.
    """

    def __init__(
        self, store: Store, make_client: Callable[[], LlmClient], prices: tuple[float, float] = (0.0, 0.0)
    ):
        self.store = store
        self.make_client = make_client
        self.prices = prices
        self.jobs: queue.Queue[int | None] = queue.Queue()
        self.thread = threading.Thread(target=self._loop, name="chemready-worker", daemon=True)

    def start(self) -> None:
        for document_id in self.store.pending_document_ids():
            self.jobs.put(document_id)
        self.thread.start()

    def submit(self, document_id: int) -> None:
        self.jobs.put(document_id)

    def stop(self) -> None:
        self.jobs.put(None)
        self.thread.join(timeout=5)

    def _loop(self) -> None:
        while (document_id := self.jobs.get()) is not None:
            process_document(self.store, document_id, self.make_client, self.prices)


# ---------- Review ----------


def _check_edit(field_name: str, value: str) -> str:
    """Edits pass the same format rules as the AI's values. Returns the cleaned value."""
    value = value.strip()
    if not value:
        raise ServiceError("Enter a value, or use Not in SDS.")
    if field_name == "revision_date" and not iso_date_ok(value):
        raise ServiceError("Enter the date as YYYY-MM-DD, for example 2025-03-01.")
    if field_name == "signal_word" and not signal_word_ok(value.capitalize()):
        raise ServiceError("The signal word must be Danger or Warning.")
    if field_name == "signal_word":
        return value.capitalize()
    if field_name.endswith(".cas_number") and not cas_check_digit_ok(value):
        raise ServiceError("CAS check digit is wrong. Check the number in the SDS.")
    if field_name.startswith("hazard_statements"):
        codes = [code.strip().upper() for code in value.replace(";", ",").split(",") if code.strip()]
        if not codes or not all(h_code_ok(code) for code in codes):
            raise ServiceError(
                "This is not a valid H code format (H plus 3 digits). Separate several with commas."
            )
        return ", ".join(codes)
    if field_name.startswith("pictograms") and not pictogram_ok(value.upper()):
        raise ServiceError("Pictograms must be GHS01 to GHS09.")
    return value.upper() if field_name.startswith("pictograms") else value


def resolve_field(
    store: Store, *, facility_id: int, field_id: int, action: str, value: str | None, reviewer: str
) -> None:
    field = store.field(facility_id, field_id)
    if field is None:
        raise ServiceError("This field does not exist.")
    document = store.document(facility_id, field["sds_id"])
    if document is None or document["status"] != "in_review":
        raise ServiceError("This document is not waiting for review.")
    if action == "approve":
        if field["value"] is None:
            raise ServiceError("There is no value to approve. Use Edit to enter it, or Not in SDS.")
        checks = json.loads(field["check_result"])
        if field["status"] == "needs_review" and checks.get("format") is False:
            raise ServiceError("This value fails a format check. Use Edit to correct it.")
        store.resolve_field(field_id, "approved", field["value"], reviewer)
    elif action == "edit":
        store.resolve_field(field_id, "edited", _check_edit(field["field_name"], value or ""), reviewer)
    elif action == "missing":
        store.resolve_field(field_id, "missing", None, reviewer)
    else:
        raise ServiceError("Unknown action.")


def open_review_count(fields: list[Row]) -> int:
    return sum(1 for f in fields if f["status"] == "needs_review" and not f["reviewed"])


def _final_value(field: Row) -> str | None:
    if field["resolution"] == "missing":
        return None
    if field["resolution"] in ("approved", "edited"):
        return str(field["value"]) if field["value"] is not None else None
    return str(field["value"]) if field["status"] == "passed" and field["value"] is not None else None


def approve_document(store: Store, *, facility_id: int, document_id: int, approver: str) -> int:
    """Turn reviewed fields into an inventory product. Nothing enters the inventory without this step."""
    document = store.document(facility_id, document_id)
    if document is None or document["status"] != "in_review":
        raise ServiceError("This document is not waiting for review.")
    fields = store.fields(document_id)
    open_count = open_review_count(fields)
    if open_count:
        raise ServiceError(f"Resolve the {open_count} field(s) that need review first.")

    scalars: dict[str, str | None] = {}
    hazards: list[tuple[str, str | None]] = []
    pictograms: list[str] = []
    ingredients: list[tuple[str | None, str | None, str | None]] = []
    for field in fields:
        name, value = field["field_name"], _final_value(field)
        if name.startswith("hazard_statements"):
            for code in (value or "").split(","):
                if code.strip():
                    hazards.append((code.strip(), field["extra"].get("statement")))
        elif name.startswith("pictograms"):
            if value:
                pictograms.append(value)
        elif name.startswith("ingredients"):
            ingredients.append((field["extra"].get("name"), value, field["extra"].get("percent")))
        else:
            scalars[name] = value

    now = datetime.now(UTC).isoformat(timespec="seconds")
    with store.transaction() as db:
        db.execute("DELETE FROM chemical_product WHERE sds_id = ?", (document_id,))
        cursor = db.execute(
            "INSERT INTO chemical_product (facility_id, sds_id, product_name, supplier,"
            " revision_date, signal_word,"
            " ppe, storage, approved_by, approved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                facility_id,
                document_id,
                scalars.get("product_name") or document["file_name"],
                scalars.get("supplier"),
                scalars.get("revision_date"),
                scalars.get("signal_word"),
                scalars.get("ppe"),
                scalars.get("storage"),
                approver,
                now,
            ),
        )
        product_id = int(cursor.lastrowid or 0)
        db.executemany(
            "INSERT INTO hazard (product_id, h_code, statement) VALUES (?, ?, ?)",
            [(product_id, code, statement) for code, statement in hazards],
        )
        db.executemany(
            "INSERT INTO hazard (product_id, pictogram) VALUES (?, ?)", [(product_id, p) for p in pictograms]
        )
        db.executemany(
            "INSERT INTO ingredient (product_id, substance_name, cas_number, cas_valid, percent_range)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (product_id, name, cas, None if cas is None else int(cas_check_digit_ok(cas)), percent)
                for name, cas, percent in ingredients
            ],
        )
        db.execute(
            "UPDATE sds_document SET status = 'approved', stage = 'Approved' WHERE id = ?", (document_id,)
        )
    return product_id


def reopen_document(store: Store, *, facility_id: int, product_id: int) -> int:
    product = store.product(facility_id, product_id)
    if product is None:
        raise ServiceError("This product does not exist.")
    store.set_status(product["sds_id"], "in_review", "Ready for review")
    return int(product["sds_id"])


# ---------- Inventory, flags and export ----------


def flags_for(product: Row, max_age: int, today: date) -> list[ActionFlag]:
    return product_flags(
        revision_date=product["revision_date"],
        cas_numbers=[i["cas_number"] for i in product["ingredients"]],
        missing_sections=product["missing_sections"],
        max_age_years=max_age,
        today=today,
    )


def all_flags(store: Store, facility_id: int, today: date) -> list[dict[str, Any]]:
    facility = store.facility(facility_id) or {"sds_max_age_years": 3}
    rows: list[dict[str, Any]] = []
    for product in store.products(facility_id):
        for flag in flags_for(product, facility["sds_max_age_years"], today):
            rows.append({"kind": flag.kind, "label": flag.label, "detail": flag.detail, "product": product})
    for document in store.documents(facility_id):
        if document["status"] == "failed":
            rows.append(
                {
                    "kind": "unreadable",
                    "label": "Unreadable file",
                    "detail": document["error"],
                    "document": document,
                }
            )
    return rows


def filter_inventory(
    products: list[Row],
    *,
    query: str = "",
    supplier: str = "",
    hazard: str = "",
    status: str = "",
    flagged: set[int],
) -> list[Row]:
    query = query.strip().lower()
    result = []
    for product in products:
        haystack = " ".join(
            [product["product_name"] or "", product["supplier"] or ""]
            + [h["h_code"] for h in product["h_codes"]]
            + [i["cas_number"] or "" for i in product["ingredients"]]
        ).lower()
        product_status = (
            "action" if product["id"] in flagged or product["document_status"] != "approved" else "verified"
        )
        if query and query not in haystack:
            continue
        if supplier and product["supplier"] != supplier:
            continue
        if hazard and hazard not in [h["h_code"] for h in product["h_codes"]]:
            continue
        if status and status != product_status:
            continue
        result.append(product)
    return result


CIL_COLUMNS = (
    "Product name",
    "Supplier",
    "SDS revision date",
    "Signal word",
    "H codes",
    "Pictograms",
    "Substance",
    "CAS number",
    "Concentration",
    "Approved by",
    "Approved at",
)


def export_cil(store: Store, facility_id: int, today: date) -> bytes:
    """R7: Excel with the inventory on sheet 1 and open flags on sheet 2."""
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None  # noqa: S101 - a new workbook always has one sheet
    sheet.title = "CIL"
    sheet.append(CIL_COLUMNS)
    for product in store.products(facility_id):
        if product["document_status"] != "approved":
            continue
        base = [
            product["product_name"],
            product["supplier"],
            product["revision_date"],
            product["signal_word"],
            " ".join(h["h_code"] for h in product["h_codes"]),
            " ".join(product["pictograms"]),
        ]
        ingredients = product["ingredients"] or [
            {"substance_name": None, "cas_number": None, "percent_range": None}
        ]
        for ingredient in ingredients:
            sheet.append(
                [
                    *base,
                    ingredient["substance_name"],
                    ingredient["cas_number"] or "Not disclosed",
                    ingredient["percent_range"],
                    product["approved_by"],
                    product["approved_at"],
                ]
            )
    flags = workbook.create_sheet("Flags")
    flags.append(("Product or file", "Problem", "Detail", "Note"))
    for flag in all_flags(store, facility_id, today):
        owner = flag.get("product") or flag.get("document") or {}
        flags.append(
            (
                owner.get("product_name") or owner.get("file_name"),
                flag["label"],
                flag["detail"],
                owner.get("note", ""),
            )
        )
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def page_text(document: Row, page: int) -> str:
    parsed = parse_pdf(Path(document["storage_path"]))
    if not 1 <= page <= parsed.page_count:
        raise ServiceError("This page does not exist.")
    return parsed.page(page).text


def parse_check(data: bytes) -> None:  # pragma: no cover - small helper for the CLI
    parse_pdf_bytes(data)
