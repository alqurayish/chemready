"""Data access. Every query that reads facility data takes facility_id, so one
factory can never see another factory's documents (server-side authorization)."""

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chemready.app.db import connect

Row = dict[str, Any]


def _row(row: sqlite3.Row | None) -> Row | None:
    return dict(row) if row is not None else None


@dataclass
class NewField:
    position: int
    field_name: str
    label: str
    value: str | None
    page: int | None
    quote: str | None
    confidence: float
    status: str
    checks: dict[str, bool]
    reasons: list[str]
    extra: dict[str, Any]


class Store:
    def __init__(self, path: Path):
        self.db = connect(path)
        self._lock = threading.RLock()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self.db.execute("BEGIN")
            try:
                yield self.db
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            self.db.execute("COMMIT")

    def one(self, sql: str, *params: Any) -> Row | None:
        with self._lock:
            return _row(self.db.execute(sql, params).fetchone())

    def all(self, sql: str, *params: Any) -> list[Row]:
        with self._lock:
            return [dict(row) for row in self.db.execute(sql, params).fetchall()]

    def run(self, sql: str, *params: Any) -> int:
        """Run one write statement and return the new row id."""
        with self._lock:
            return int(self.db.execute(sql, params).lastrowid or 0)

    # Facilities and users
    def create_facility(self, name: str, max_age: int) -> int:
        return self.run("INSERT INTO facility (name, sds_max_age_years) VALUES (?, ?)", name, max_age)

    def facility(self, facility_id: int) -> Row | None:
        return self.one("SELECT * FROM facility WHERE id = ?", facility_id)

    def update_facility(self, facility_id: int, **values: Any) -> None:
        allowed = {"name", "location", "solution_provider", "sds_max_age_years"}
        sets = {key: value for key, value in values.items() if key in allowed}
        if sets:
            assignments = ", ".join(f"{key} = ?" for key in sets)
            self.run(f"UPDATE facility SET {assignments} WHERE id = ?", *sets.values(), facility_id)  # noqa: S608

    def create_user(self, facility_id: int, name: str, email: str, password_hash: str) -> int:
        return self.run(
            "INSERT INTO app_user (facility_id, name, email, password_hash) VALUES (?, ?, ?, ?)",
            facility_id,
            name,
            email.lower(),
            password_hash,
        )

    def user_by_email(self, email: str) -> Row | None:
        return self.one("SELECT * FROM app_user WHERE email = ?", email.lower())

    def user(self, user_id: int) -> Row | None:
        return self.one("SELECT * FROM app_user WHERE id = ?", user_id)

    # Documents
    def document_by_hash(self, facility_id: int, file_hash: str) -> Row | None:
        return self.one(
            "SELECT * FROM sds_document WHERE facility_id = ? AND file_hash = ?", facility_id, file_hash
        )

    def add_document(
        self, facility_id: int, file_name: str, file_hash: str, storage_path: str, user_id: int, private: bool
    ) -> int:
        return self.run(
            "INSERT INTO sds_document (facility_id, file_name, file_hash, storage_path, uploaded_by,"
            " is_private)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            facility_id,
            file_name,
            file_hash,
            storage_path,
            user_id,
            int(private),
        )

    # Documents with their open review count and the best known product name
    # (the approved name, or the name found by extraction while still in review).
    _DOCUMENTS = (
        "SELECT d.*,"
        " (SELECT COUNT(*) FROM field_value f"
        "  WHERE f.sds_id = d.id AND f.status = 'needs_review' AND f.reviewed = 0) AS open_reviews,"
        " COALESCE(p.product_name, (SELECT f.value FROM field_value f"
        "  WHERE f.sds_id = d.id AND f.field_name = 'product_name')) AS product_name"
        " FROM sds_document d LEFT JOIN chemical_product p ON p.sds_id = d.id"
        " WHERE d.facility_id = ?"
    )

    def document(self, facility_id: int, document_id: int) -> Row | None:
        return self.one(self._DOCUMENTS + " AND d.id = ?", facility_id, document_id)

    def document_any_facility(self, document_id: int) -> Row | None:
        """Only for the background worker, which already knows the document is valid."""
        return self.one("SELECT * FROM sds_document WHERE id = ?", document_id)

    def documents(self, facility_id: int) -> list[Row]:
        """All documents, newest first."""
        return self.all(self._DOCUMENTS + " ORDER BY d.uploaded_at DESC, d.id DESC", facility_id)

    def set_status(self, document_id: int, status: str, stage: str, error: str | None = None) -> None:
        self.run(
            "UPDATE sds_document SET status = ?, stage = ?, error = ? WHERE id = ?",
            status,
            stage,
            error,
            document_id,
        )

    def pending_document_ids(self) -> list[int]:
        rows = self.all("SELECT id FROM sds_document WHERE status IN ('queued', 'extracting') ORDER BY id")
        return [int(row["id"]) for row in rows]

    def delete_document(self, facility_id: int, document_id: int) -> None:
        with self.transaction() as db:
            db.execute(
                "DELETE FROM chemical_product WHERE sds_id = ? AND facility_id = ?",
                (document_id, facility_id),
            )
            db.execute(
                "DELETE FROM sds_document WHERE id = ? AND facility_id = ?", (document_id, facility_id)
            )

    def save_extraction(self, document_id: int, meta: dict[str, Any], fields: list[NewField]) -> None:
        with self.transaction() as db:
            db.execute("DELETE FROM field_value WHERE sds_id = ?", (document_id,))
            db.executemany(
                "INSERT INTO field_value (sds_id, position, field_name, label, value,"
                " original_value, page, quote,"
                " confidence, status, check_result, reasons, extra) VALUES (?, ?, ?, ?, ?, ?, ?, ?,"
                " ?, ?, ?, ?, ?)",
                [
                    (
                        document_id,
                        f.position,
                        f.field_name,
                        f.label,
                        f.value,
                        f.value,
                        f.page,
                        f.quote,
                        f.confidence,
                        f.status,
                        json.dumps(f.checks),
                        json.dumps(f.reasons),
                        json.dumps(f.extra),
                    )
                    for f in fields
                ],
            )
            db.execute(
                "UPDATE sds_document SET status = 'in_review', stage = 'Ready for review', error ="
                " NULL, pages = ?,"
                " is_scanned = ?, missing_sections = ?, provider = ?, model = ?, prompt_version = ?,"
                " input_tokens = ?, output_tokens = ?, latency_ms = ? WHERE id = ?",
                (
                    meta["pages"],
                    meta["is_scanned"],
                    json.dumps(meta["missing_sections"]),
                    meta["provider"],
                    meta["model"],
                    meta["prompt_version"],
                    meta["input_tokens"],
                    meta["output_tokens"],
                    meta["latency_ms"],
                    document_id,
                ),
            )

    def update_document_meta(
        self, document_id: int, pages: int, is_scanned: bool, missing: list[int]
    ) -> None:
        self.run(
            "UPDATE sds_document SET pages = ?, is_scanned = ?, missing_sections = ? WHERE id = ?",
            pages,
            int(is_scanned),
            json.dumps(missing),
            document_id,
        )

    # Fields
    def fields(self, document_id: int) -> list[Row]:
        rows = self.all("SELECT * FROM field_value WHERE sds_id = ? ORDER BY position", document_id)
        for row in rows:
            row["checks"] = json.loads(row.pop("check_result"))
            row["reasons"] = json.loads(row["reasons"])
            row["extra"] = json.loads(row["extra"])
        return rows

    def field(self, facility_id: int, field_id: int) -> Row | None:
        return self.one(
            "SELECT f.* FROM field_value f JOIN sds_document d ON d.id = f.sds_id WHERE f.id = ? AND"
            " d.facility_id = ?",
            field_id,
            facility_id,
        )

    def resolve_field(self, field_id: int, resolution: str, value: str | None, reviewer: str) -> None:
        self.run(
            "UPDATE field_value SET reviewed = 1, resolution = ?, value = ?, reviewed_by = ?,"
            " reviewed_at = datetime('now')"
            " WHERE id = ?",
            resolution,
            value,
            reviewer,
            field_id,
        )

    # Products
    def products(self, facility_id: int) -> list[Row]:
        products = self.all(
            "SELECT p.*, d.file_name, d.missing_sections, d.status AS document_status FROM chemical_product p"
            " JOIN sds_document d ON d.id = p.sds_id WHERE p.facility_id = ? ORDER BY p.product_name"
            " COLLATE NOCASE",
            facility_id,
        )
        for product in products:
            product["missing_sections"] = json.loads(product["missing_sections"])
            product["ingredients"] = self.all("SELECT * FROM ingredient WHERE product_id = ?", product["id"])
            hazards = self.all("SELECT * FROM hazard WHERE product_id = ? ORDER BY id", product["id"])
            product["h_codes"] = [h for h in hazards if h["h_code"]]
            product["pictograms"] = [h["pictogram"] for h in hazards if h["pictogram"]]
        return products

    def product(self, facility_id: int, product_id: int) -> Row | None:
        return next((p for p in self.products(facility_id) if p["id"] == product_id), None)

    def set_product_note(self, facility_id: int, product_id: int, note: str) -> None:
        self.run(
            "UPDATE chemical_product SET note = ? WHERE id = ? AND facility_id = ?",
            note,
            product_id,
            facility_id,
        )
