"""ChemReady on Streamlit Community Cloud.

A Streamlit front end for the same engine the FastAPI app uses: PDF parsing,
extraction, validation, review, inventory, action flags and Excel export all come
from the `chemready` package. Only the screens are different.

Run locally:  uv run streamlit run streamlit_app.py
Public demo:  fictional data and the rules baseline by default. Never upload a
factory's private files to a public deployment.
"""

import html
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# ---------- Settings from Streamlit secrets (set in the Cloud "Secrets" box) ----------


def _load_secrets_into_environment() -> None:
    """Copy CHEMREADY_* secrets into environment variables, which the Settings class reads."""
    try:
        secrets = dict(st.secrets)
    except Exception:  # no secrets file locally: fine, defaults apply
        secrets = {}
    for key, value in secrets.items():
        if key.startswith("CHEMREADY_") and isinstance(value, str | int | float | bool):
            os.environ.setdefault(key, str(value))
    data_dir = Path(tempfile.gettempdir()) / "chemready"
    os.environ.setdefault("CHEMREADY_LLM_PROVIDER", "rules")  # no AI account needed for the demo
    os.environ.setdefault("CHEMREADY_DATABASE_PATH", str(data_dir / "chemready.sqlite"))
    os.environ.setdefault("CHEMREADY_UPLOAD_DIR", str(data_dir / "uploads"))
    os.environ.setdefault("CHEMREADY_ENVIRONMENT", "development")  # no session cookies used here


_load_secrets_into_environment()

from chemready.app import auth  # noqa: E402  (settings must be in the environment first)
from chemready.app.observability import usage_summary  # noqa: E402
from chemready.app.service import (  # noqa: E402
    ServiceError,
    accept_uploads,
    all_flags,
    approve_document,
    export_cil,
    filter_inventory,
    open_review_count,
    page_text,
    process_document,
    resolve_field,
)
from chemready.app.store import Row, Store  # noqa: E402
from chemready.config import Settings  # noqa: E402
from chemready.demo.seed import DEMO_EMAIL, DEMO_PASSWORD, seed_demo  # noqa: E402
from chemready.extraction.llm import make_client  # noqa: E402

st.set_page_config(page_title="ChemReady · A D-SAi Product", page_icon="🧪", layout="wide")

STYLE = """
<style>
  .stApp { background: #FFFFFF; }
  [data-testid="stHeader"] { background: rgba(255,255,255,0.72); backdrop-filter: saturate(180%) blur(18px); }
  div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 14px; box-shadow: inset 0 1px 0 rgba(255,255,255,0.9), 0 0 0 1px rgba(15,23,42,0.06),
    0 10px 30px rgba(30,64,175,0.07);
  }
  .brand { display:flex; align-items:center; gap:10px; font-weight:600; font-size:18px; }
  .brand-mark { width:16px; height:16px; border:2px solid #1D4ED8; transform:rotate(45deg);
    border-radius:3px; }
  .tag { font-size:11px; color:#58677D; border:1px solid #E2E8F0; border-radius:999px; padding:0 7px; }
  .pill { display:inline-block; padding:1px 8px; border-radius:999px; font-size:13px; font-weight:500; }
  .p-verified { background:#DCFCE7; color:#166534; } .p-review { background:#FEF3C7; color:#92400E; }
  .p-missing { background:#FEE2E2; color:#991B1B; } .p-passed { background:#F1F5F9; color:#334155; }
  .paper { background:#fff; border:1px solid #E2E8F0; border-radius:10px; padding:20px 22px;
    font-family:Georgia,serif;
    font-size:13px; line-height:1.7; white-space:pre-wrap; max-height:560px; overflow:auto; }
  mark.q { background:#BFDBFE; outline:2px solid #1D4ED8; border-radius:2px; }
  .muted { color:#58677D; font-size:13px; }
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)

PILL = {
    "verified": ("p-verified", "✓"),
    "review": ("p-review", "!"),
    "missing": ("p-missing", "○"),
    "passed": ("p-passed", "•"),
}


def pill(kind: str, label: str) -> str:
    css, icon = PILL[kind]
    return f'<span class="pill {css}">{icon} {html.escape(label)}</span>'


def highlighted(text: str, quote: str | None) -> str:
    text = "\n".join(line for line in text.splitlines() if line.strip())
    safe = html.escape(text)
    if quote and html.escape(quote) in safe:
        safe = safe.replace(html.escape(quote), f'<mark class="q">{html.escape(quote)}</mark>', 1)
    return f'<div class="paper">{safe}</div>'


# ---------- Shared resources (created once per server) ----------


@st.cache_resource
def get_settings() -> Settings:
    return Settings()


@st.cache_resource
def get_store() -> Store:
    settings = get_settings()
    store = Store(settings.database_path)
    seed_demo(settings, store)  # demo account with fictional SDS files; safe to call again
    return store


@st.cache_resource
def get_throttle() -> auth.SignInThrottle:
    return auth.SignInThrottle.create()


settings = get_settings()
store = get_store()


def current_user() -> Row | None:
    user_id = st.session_state.get("user_id")
    return store.user(user_id) if user_id else None


def sign_in_as(user: Row) -> None:
    st.session_state["user_id"] = user["id"]
    st.rerun()  # also closes the sign-in popup


@st.dialog("Sign in to continue")
def sign_in_dialog(reason: str) -> None:
    """Pop-up sign-in. Shown only when someone needs an account, never as a landing page."""
    st.caption(reason)
    sign_in_tab, sign_up_tab = st.tabs(["Sign in", "Create account"])
    with sign_in_tab, st.form("sign_in"):
        email = st.text_input("Work email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in", type="primary", use_container_width=True):
            try:
                sign_in_as(auth.sign_in(store, get_throttle(), email=email, password=password))
            except auth.AuthError as error:
                st.error(str(error))
    with sign_up_tab, st.form("sign_up"):
        name = st.text_input("Full name")
        new_email = st.text_input("Work email")
        facility = st.text_input("Facility name")
        new_password = st.text_input("Password (8+ characters)", type="password")
        if st.form_submit_button("Create account", type="primary", use_container_width=True):
            try:
                user = auth.sign_up(
                    store,
                    name=name,
                    email=new_email,
                    password=new_password,
                    facility_name=facility,
                    max_age=settings.sds_max_age_years,
                )
                sign_in_as(user)
            except auth.AuthError as error:
                st.error(str(error))
    st.divider()
    if st.button("Use the demo account", use_container_width=True):
        demo = store.user_by_email(DEMO_EMAIL)
        if demo:
            sign_in_as(demo)
    st.caption(f"Demo: {DEMO_EMAIL} / {DEMO_PASSWORD}. Fictional data only.")


def header(user: Row | None, sign_in_button: bool = True) -> None:
    left, right = st.columns([3, 2])
    left.markdown(
        '<div class="brand"><span class="brand-mark"></span>ChemReady'
        ' <span class="tag">Prototype</span></div>',
        unsafe_allow_html=True,
    )
    if user:
        mode = "Local model" if settings.llm_provider != "gemini" else "Gemini · public only"
        right.markdown(
            f'<div style="text-align:right" class="muted">● {mode} · {html.escape(user["name"])}</div>',
            unsafe_allow_html=True,
        )
    elif sign_in_button:
        with right:
            _, button = st.columns([3, 1])
            if button.button("Sign in", key="header_sign_in", use_container_width=True):
                sign_in_dialog("Sign in to see your documents and inventory.")


def footer() -> None:
    st.caption(
        "ChemReady Prototype · A D-SAi Product · designed and built by Md. Alqurayish Sharkar, "
        "AI Product Engineer · © 2026 D-SAi"
    )


# ---------- Pages ----------


def upload_page() -> None:
    """The first page everyone sees. Signing in is asked for only when they upload."""
    user = current_user()
    header(user)
    st.header("Upload SDS files")
    st.caption(
        "ChemReady reads your safety data sheets, checks every value in code, and asks you to approve only "
        "what is doubtful. Every value links back to its page and quote."
    )
    st.warning("Public demo: upload fictional or public SDS files only, never a factory's private files.")
    round_no = st.session_state.get("upload_round", 0)
    with st.container(border=True):
        files = st.file_uploader(
            "SDS PDF files (up to 20 MB each)",
            type=["pdf"],
            accept_multiple_files=True,
            key=f"files-{round_no}",
        )
        public = st.checkbox(
            "These are public SDS files downloaded from the supplier's website",
            value=True,
            key=f"public-{round_no}",
        )
        clicked = st.button("Upload and process", type="primary", disabled=not files)

    if clicked and user is None:
        # Remember the files (the uploader keeps them) and ask the person to sign in first.
        st.session_state["pending_upload"] = True
        sign_in_dialog("Sign in to upload. You will go straight back to your files.")
        return
    pending = user is not None and st.session_state.pop("pending_upload", False)
    if user is not None and files and (clicked or pending):
        _process_uploads(user, files, public)
        st.session_state["upload_round"] = round_no + 1  # empty the uploader for the next batch
    footer()


def _process_uploads(user: Row, files: list[Any], public: bool) -> None:
    try:
        results = accept_uploads(
            store,
            settings,
            facility_id=user["facility_id"],
            user_id=user["id"],
            files=[(f.name, f.getvalue()) for f in files],
            private=not public,
        )
    except ServiceError as error:
        st.error(str(error))
        return
    prices = (settings.price_input_per_million, settings.price_output_per_million)
    with st.status("Processing…", expanded=True) as status:
        for result in results:
            if result.document_id is None:
                st.write(f"✕ {result.file_name}: {result.message}")
                continue
            st.write(f"Reading, extracting and checking {result.file_name}…")
            process_document(store, result.document_id, lambda: make_client(settings), prices)
            document = store.document(user["facility_id"], result.document_id)
            outcome = document["error"] if document and document["status"] == "failed" else "ready for review"
            st.write(f"✓ {result.file_name}: {outcome}")
        status.update(label="Done. Open Review to check the results.", state="complete")


def review_page() -> None:
    user = _gate("your documents to review")
    if user is None:
        return
    header(user)
    st.header("Review")
    documents = store.documents(user["facility_id"])
    waiting = [d for d in documents if d["status"] == "in_review"]
    failed = [d for d in documents if d["status"] == "failed"]
    if failed:
        with st.expander(f"{len(failed)} file(s) could not be read"):
            for doc in failed:
                st.write(f"**{doc['file_name']}**: {doc['error']}")
    if not waiting:
        st.success("All caught up. Nothing waiting for review.")
        return
    labels = {
        d["id"]: f"{d['product_name'] or d['file_name']} · {d['open_reviews']} to review" for d in waiting
    }
    document_id = st.selectbox("Document", options=list(labels), format_func=labels.get)
    document = store.document(user["facility_id"], int(document_id))
    if document is None:
        return
    fields = store.fields(document["id"])
    open_count = open_review_count(fields)

    left, right = st.columns([5, 6], gap="large")
    with left:
        st.caption(
            f"{open_count} field(s) need review" if open_count else "All doubtful fields are resolved."
        )
        if st.button("Approve product", type="primary", disabled=bool(open_count)):
            try:
                approve_document(
                    store, facility_id=user["facility_id"], document_id=document["id"], approver=user["name"]
                )
                st.toast("Added to inventory.")
                st.rerun()
            except ServiceError as error:
                st.error(str(error))
        ordered = sorted(
            fields, key=lambda f: (f["status"] != "needs_review" or f["reviewed"], f["position"])
        )
        choices = {f["id"]: f"{f['label']}{' · p.' + str(f['page']) if f['page'] else ''}" for f in ordered}
        selected = st.radio(
            "Field", options=list(choices), format_func=choices.get, label_visibility="collapsed"
        )
        for field in ordered:
            if field["id"] != selected:
                continue
            with st.container(border=True):
                kind = (
                    "missing"
                    if field["resolution"] == "missing" or field["status"] == "missing"
                    else "review"
                    if field["status"] == "needs_review" and not field["reviewed"]
                    else "passed"
                )
                label = {"missing": "Missing", "review": "Needs review", "passed": "Passed checks"}[kind]
                st.markdown(f"**{html.escape(field['label'])}** {pill(kind, label)}", unsafe_allow_html=True)
                st.write(field["value"] if field["value"] is not None else "—")
                for reason in field["reasons"]:
                    st.caption(reason)
                actions = st.columns(2)
                if field["value"] is not None and kind == "review" and actions[0].button("Approve value"):
                    _resolve(user, field, "approve", None)
                if actions[1].button("Not in SDS"):
                    _resolve(user, field, "missing", None)
                with st.form(f"edit-{field['id']}"):
                    value = st.text_input("Correct value", value=field["value"] or "")
                    if st.form_submit_button("Save edit"):
                        _resolve(user, field, "edit", value)
    with right:
        current = next((f for f in fields if f["id"] == selected), None)
        page_no = (current or {}).get("page") or 1
        st.caption(f"{document['file_name']} · page {page_no} of {document['pages']}")
        try:
            text = page_text(document, page_no)
        except (ServiceError, OSError):
            text = "This page could not be shown."
        quote = current["quote"] if current and current["value"] is not None else None
        st.markdown(highlighted(text, quote), unsafe_allow_html=True)


def _resolve(user: Row, field: Row, action: str, value: str | None) -> None:
    try:
        resolve_field(
            store, facility_id=user["facility_id"], field_id=field["id"], action=action, value=value,
            reviewer=user["name"],
        )  # fmt: skip
        st.toast("Saved.")
        st.rerun()
    except ServiceError as error:
        st.error(str(error))


def inventory_page() -> None:
    user = _gate("your inventory")
    if user is None:
        return
    header(user)
    products = store.products(user["facility_id"])
    flags = all_flags(store, user["facility_id"], date.today())
    flagged = {f["product"]["id"] for f in flags if "product" in f}
    title, button = st.columns([4, 1])
    title.header("Inventory")
    button.download_button(
        "Export CIL",
        data=export_cil(store, user["facility_id"], date.today()),
        file_name=f"ChemReady_CIL_{date.today():%Y-%m}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
    if not products:
        st.info("Your inventory is empty. Approve reviewed SDS files and they will appear here.")
        return
    q, supplier, status = st.columns([3, 2, 2])
    query = q.text_input("Search", placeholder="Name, supplier, CAS, H code")
    suppliers = sorted({p["supplier"] for p in products if p["supplier"]})
    chosen_supplier = supplier.selectbox("Supplier", ["All suppliers", *suppliers])
    chosen_status = status.selectbox("Status", ["All statuses", "Verified", "Needs action"])
    rows = filter_inventory(
        products,
        query=query,
        supplier="" if chosen_supplier == "All suppliers" else chosen_supplier,
        status={"Verified": "verified", "Needs action": "action"}.get(chosen_status, ""),
        flagged=flagged,
    )
    table = pd.DataFrame(
        [
            {
                "Product": p["product_name"],
                "Supplier": p["supplier"],
                "Signal word": p["signal_word"] or "—",
                "H codes": " ".join(h["h_code"] for h in p["h_codes"]) or "None listed",
                "Pictograms": " ".join(p["pictograms"]) or "—",
                "SDS date": p["revision_date"] or "—",
                "Status": "Needs action" if p["id"] in flagged else "Verified",
                "Approved by": p["approved_by"],
            }
            for p in rows
        ]
    )
    st.caption(f"Showing {len(rows)} of {len(products)} products")
    st.dataframe(table, hide_index=True, use_container_width=True)
    st.caption(
        "ChemReady checks that your data matches your SDS files. It does not decide MRSL conformance. "
        "Use the ZDHC Gateway and your solution provider for that."
    )


def actions_page() -> None:
    user = _gate("what needs action")
    if user is None:
        return
    header(user)
    st.header("Actions")
    flags = all_flags(store, user["facility_id"], date.today())
    if not flags:
        st.success("Nothing needs action. Your inventory data is complete.")
        return
    st.caption(f"Fix these before your monthly report. {len(flags)} open.")
    table = pd.DataFrame(
        [
            {
                "Product or file": (f.get("product") or {}).get("product_name")
                or (f.get("document") or {}).get("file_name"),
                "Problem": f["label"],
                "Detail": f["detail"],
                "Note": (f.get("product") or {}).get("note", ""),
            }
            for f in flags
        ]
    )
    st.dataframe(table, hide_index=True, use_container_width=True)
    products = {f["product"]["id"]: f["product"] for f in flags if "product" in f}
    if products:
        with st.form("note"):
            product_id = st.selectbox(
                "Add a note for the auditor",
                options=list(products),
                format_func=lambda i: products[i]["product_name"],
            )
            note = st.text_input("Note", placeholder="Supplier says CAS is a trade secret, asked on…")
            if st.form_submit_button("Save note"):
                store.set_product_note(user["facility_id"], int(product_id), note.strip()[:1000])
                st.toast("Note saved.")
                st.rerun()


def settings_page() -> None:
    user = _gate("your settings")
    if user is None:
        return
    header(user)
    st.header("Settings")
    facility = store.facility(user["facility_id"]) or {}
    with st.form("settings"):
        name = st.text_input("Facility name", value=facility.get("name", ""))
        location = st.text_input("Location", value=facility.get("location", ""))
        provider = st.text_input("Solution provider", value=facility.get("solution_provider", ""))
        age = st.number_input("SDS maximum age (years)", 1, 10, int(facility.get("sds_max_age_years", 3)))
        if st.form_submit_button("Save settings", type="primary"):
            store.update_facility(
                user["facility_id"], name=name.strip() or "Facility", location=location.strip(),
                solution_provider=provider.strip(), sds_max_age_years=int(age),
            )  # fmt: skip
            st.toast("Settings saved. Action flags updated.")
    usage = usage_summary(store, user["facility_id"], f"{date.today():%Y-%m}-01")
    st.subheader("AI usage this month")
    a, b, c = st.columns(3)
    a.metric("Model calls", usage.get("calls", 0))
    b.metric("Tokens in / out", f"{usage.get('input_tokens', 0)} / {usage.get('output_tokens', 0)}")
    c.metric("Cost (USD)", f"{usage.get('cost_usd', 0):.4f}")
    st.caption(
        f"Processing mode: {settings.llm_provider}. "
        "Private factory files are never sent to a free AI service."
    )


def profile_page() -> None:
    user = _gate("your profile")
    if user is None:
        return
    header(user)
    st.header("Profile")
    st.write(f"**{user['name']}** · {user['email']} · {user['role']}")
    if st.button("Sign out"):
        st.session_state.pop("user_id", None)
        st.rerun()


def _gate(what: str) -> Row | None:
    """Return the signed-in user, or show a short sign-in prompt for this page."""
    user = current_user()
    if user is None:
        header(None, sign_in_button=False)  # the card below has its own button
        with st.container(border=True):
            st.markdown(f"**Sign in to see {what}.**")
            st.caption("Or start on the Upload page: you will be asked to sign in when you upload.")
            if st.button("Sign in", type="primary", key=f"gate-{what}"):
                sign_in_dialog(f"Sign in to see {what}.")
    return user


# ---------- Navigation: a top bar, no sidebar ----------

pages = [
    st.Page(upload_page, title="Upload", icon=":material/upload:", url_path="upload", default=True),
    st.Page(review_page, title="Review", icon=":material/fact_check:", url_path="review"),
    st.Page(inventory_page, title="Inventory", icon=":material/table:", url_path="inventory"),
    st.Page(actions_page, title="Actions", icon=":material/flag:", url_path="actions"),
    st.Page(settings_page, title="Settings", icon=":material/tune:", url_path="settings"),
    st.Page(profile_page, title="Profile", icon=":material/person:", url_path="profile"),
]
st.navigation(pages, position="top").run()
