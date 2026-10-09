"""HTML pages, rendered on the server with Jinja2.

Why server-rendered pages: the whole app stays in Python, the founder can
maintain it without a JavaScript framework, and each page is a plain HTML form
that works on slow factory connections. The look is the approved Phase 1 design.
"""

import json
from datetime import date
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote as url_quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from chemready.app import auth
from chemready.app.main import AppState, State, optional_user, start_session
from chemready.app.service import (
    ServiceError,
    accept_uploads,
    all_flags,
    approve_document,
    filter_inventory,
    flags_for,
    open_review_count,
    page_text,
    reopen_document,
    resolve_field,
)
from chemready.app.store import Row

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
PICTOGRAMS = {
    "GHS01": "Exploding bomb",
    "GHS02": "Flame",
    "GHS03": "Flame over circle",
    "GHS04": "Gas cylinder",
    "GHS05": "Corrosion",
    "GHS06": "Skull and crossbones",
    "GHS07": "Exclamation mark",
    "GHS08": "Health hazard",
    "GHS09": "Environment",
}


def nice_date(value: str | None) -> str:
    """2025-03-01 → 1 Mar 2025 (the format in the design system)."""
    if not value:
        return "—"
    try:
        day = date.fromisoformat(value[:10])
    except ValueError:
        return value
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def initials(name: str) -> str:
    return "".join(word[0].upper() for word in name.split()[:2]) or "?"


def highlight(text: str, quote: str | None) -> Markup:
    """Escape page text and mark the quote, so the reviewer sees exactly where a value came from."""
    text = "\n".join(line for line in text.splitlines() if line.strip())  # PDF text has many blank lines
    safe = str(escape(text))
    if quote:
        target = str(escape(quote))
        if target in safe:
            safe = safe.replace(target, f'<mark class="q">{target}</mark>', 1)
    return Markup(safe)  # noqa: S704 - built only from escaped text


TEMPLATES.env.filters["nice_date"] = nice_date
TEMPLATES.env.filters["initials"] = initials
TEMPLATES.env.globals["PICTOGRAMS"] = PICTOGRAMS


class SignInRequiredError(Exception):
    def __init__(self, next_path: str):
        self.next_path = next_path


def page_user(request: Request, user: Annotated[Row | None, Depends(optional_user)]) -> Row:
    if user is None:
        raise SignInRequiredError(request.url.path)
    return user


PageUser = Annotated[Row, Depends(page_user)]


def flash(request: Request, message: str, kind: str = "success") -> None:
    request.session.setdefault("flash", []).append({"message": message, "kind": kind})


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def safe_next(path: str | None) -> str:
    """Only allow redirects to our own pages (no open redirect to other sites)."""
    if path and path.startswith("/") and not path.startswith("//"):
        return path
    return "/app/inventory"


def render(request: Request, name: str, s: AppState, user: Row | None, **context: Any) -> HTMLResponse:
    nav: dict[str, int] = {}
    facility = None
    if user is not None:
        documents = s.store.documents(user["facility_id"])
        nav = {
            "review": sum(1 for d in documents if d["status"] == "in_review"),
            "actions": len(all_flags(s.store, user["facility_id"], s.today())),
        }
        facility = s.store.facility(user["facility_id"])
    messages = request.session.pop("flash", [])
    return TEMPLATES.TemplateResponse(
        request,
        name,
        {
            "user": user,
            "facility": facility,
            "nav": nav,
            "messages": messages,
            "settings": s.settings,
            **context,
        },
    )


router = APIRouter()


# ---------- Public pages ----------


@router.get("/", response_class=HTMLResponse)
def landing(request: Request, s: State, user: Annotated[Row | None, Depends(optional_user)]) -> HTMLResponse:
    return render(request, "landing.html", s, user)


@router.get("/signin", response_class=HTMLResponse)
def signin_page(request: Request, s: State, next: str = "") -> HTMLResponse:
    return render(request, "auth.html", s, None, mode="signin", next=safe_next(next), error=None, values={})


@router.post("/signin")
def signin_submit(
    request: Request,
    s: State,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "",
) -> Response:
    try:
        user = auth.sign_in(s.store, s.throttle, email=email, password=password)
    except auth.AuthError as error:
        values = {"email": email}
        return render(
            request,
            "auth.html",
            s,
            None,
            mode="signin",
            next=safe_next(next),
            error=str(error),
            values=values,
        )
    start_session(request, user)
    flash(request, f"Signed in as {user['name']}.")
    return redirect(safe_next(next))


@router.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request, s: State, next: str = "") -> HTMLResponse:
    return render(request, "auth.html", s, None, mode="signup", next=safe_next(next), error=None, values={})


@router.post("/signup")
def signup_submit(
    request: Request,
    s: State,
    name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    facility_name: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "",
) -> Response:
    try:
        user = auth.sign_up(
            s.store,
            name=name,
            email=email,
            password=password,
            facility_name=facility_name,
            max_age=s.settings.sds_max_age_years,
        )
    except auth.AuthError as error:
        values = {"name": name, "email": email, "facility_name": facility_name}
        return render(
            request,
            "auth.html",
            s,
            None,
            mode="signup",
            next=safe_next(next),
            error=str(error),
            values=values,
        )
    start_session(request, user)
    flash(request, f"Account created. Welcome, {user['name']}.")
    return redirect(safe_next(next))


@router.get("/reset", response_class=HTMLResponse)
def reset_page(request: Request, s: State, token: str = "") -> HTMLResponse:
    mode = "reset-confirm" if token else "reset"
    return render(request, "auth.html", s, None, mode=mode, token=token, next="", error=None, values={})


@router.post("/reset")
def reset_submit(request: Request, s: State, email: Annotated[str, Form()]) -> HTMLResponse:
    token = auth.start_password_reset(s.store, email)
    if token:
        import logging

        logging.getLogger("chemready.app").warning("password reset requested; link: /reset?token=%s", token)
    return render(
        request, "auth.html", s, None, mode="reset-sent", next="", error=None, values={"email": email}
    )


@router.post("/reset/confirm")
def reset_confirm(
    request: Request, s: State, token: Annotated[str, Form()], password: Annotated[str, Form()]
) -> Response:
    try:
        auth.finish_password_reset(s.store, token, password)
    except auth.AuthError as error:
        return render(
            request,
            "auth.html",
            s,
            None,
            mode="reset-confirm",
            token=token,
            next="",
            error=str(error),
            values={},
        )
    flash(request, "Password changed. Sign in with your new password.")
    return redirect("/signin")


@router.post("/demo")
def demo_signin(request: Request, s: State) -> Response:
    """One-click sign-in to the demo account (only if it was created with `chemready seed-demo`)."""
    from chemready.demo.seed import DEMO_EMAIL

    user = s.store.user_by_email(DEMO_EMAIL)
    if user is None:
        flash(request, "The demo account is not set up on this server. Run `chemready seed-demo`.", "error")
        return redirect("/")
    start_session(request, user)
    flash(request, f"Signed in to the demo as {user['name']}.")
    return redirect("/app/inventory")


@router.post("/signout")
def signout(request: Request) -> Response:
    request.session.clear()
    request.session["flash"] = [{"message": "Signed out.", "kind": "success"}]
    return redirect("/")


# ---------- App pages ----------


@router.get("/app/upload", response_class=HTMLResponse)
def upload_page(request: Request, s: State, user: PageUser) -> HTMLResponse:
    return render(request, "upload.html", s, user, active="upload", results=[])


@router.post("/app/upload", response_class=HTMLResponse)
async def upload_submit(
    request: Request,
    s: State,
    user: PageUser,
    files: Annotated[list[UploadFile], File()],
    public_sds: Annotated[bool, Form()] = False,
) -> HTMLResponse:
    contents = [(f.filename or "file", await f.read()) for f in files if f.filename]
    try:
        results = accept_uploads(
            s.store,
            s.settings,
            facility_id=user["facility_id"],
            user_id=user["id"],
            files=contents,
            private=not public_sds,
        )
    except ServiceError as error:
        flash(request, str(error), "error")
        results = []
    for result in results:
        if result.document_id is not None:
            s.enqueue(result.document_id)
    added = sum(r.accepted for r in results)
    if added:
        flash(request, f"{added} file{'s' if added != 1 else ''} added. Processing has started.")
    return render(request, "upload.html", s, user, active="upload", results=results)


@router.get("/app/review", response_class=HTMLResponse)
def documents_page(request: Request, s: State, user: PageUser, tab: str = "all") -> HTMLResponse:
    documents = s.store.documents(user["facility_id"])
    groups = {
        "all": documents,
        "in_review": [d for d in documents if d["status"] == "in_review"],
        "processing": [d for d in documents if d["status"] in ("queued", "extracting")],
        "approved": [d for d in documents if d["status"] == "approved"],
        "failed": [d for d in documents if d["status"] == "failed"],
    }
    order = {"in_review": 0, "extracting": 1, "queued": 1, "failed": 2, "approved": 3}
    rows = sorted(groups.get(tab, documents), key=lambda d: order[d["status"]])
    return render(
        request,
        "documents.html",
        s,
        user,
        active="review",
        tab=tab,
        groups=groups,
        rows=rows,
        processing=len(groups["processing"]),
    )


@router.get("/app/review/{document_id}", response_class=HTMLResponse)
def review_page(
    request: Request, s: State, user: PageUser, document_id: int, field: int | None = None
) -> Response:
    document = s.store.document(user["facility_id"], document_id)
    if document is None:
        flash(request, "That document does not exist.", "error")
        return redirect("/app/review")
    fields = s.store.fields(document_id)
    open_fields = [f for f in fields if f["status"] == "needs_review" and not f["reviewed"]]
    missing = [
        f for f in fields if (f["status"] == "missing" and not f["reviewed"]) or f["resolution"] == "missing"
    ]
    done = [f for f in fields if f not in open_fields and f not in missing]
    chosen = next((f for f in fields if f["id"] == field), None)
    active: Row | None = chosen or (open_fields[0] if open_fields else (fields[0] if fields else None))
    page_no = (active or {}).get("page") or 1
    try:
        text = page_text(document, page_no) if document["status"] != "failed" else ""
    except ServiceError:
        text = ""
    quote = active["quote"] if active and active["resolution"] != "missing" else None
    return render(
        request,
        "review.html",
        s,
        user,
        active="review",
        document=document,
        open_fields=open_fields,
        missing=missing,
        done=done,
        current=active,
        page_no=page_no,
        page_html=highlight(text, quote),
        open_count=open_review_count(fields),
        editable=document["status"] == "in_review",
    )


@router.post("/app/fields/{field_id}")
def field_submit(
    request: Request,
    s: State,
    user: PageUser,
    field_id: int,
    action: Annotated[str, Form()],
    document_id: Annotated[int, Form()],
    value: Annotated[str | None, Form()] = None,
) -> Response:
    try:
        resolve_field(
            s.store,
            facility_id=user["facility_id"],
            field_id=field_id,
            action=action,
            value=value,
            reviewer=user["name"],
        )
        flash(
            request,
            {"approve": "Approved.", "edit": "Saved your edit.", "missing": "Marked as missing."}[action],
        )
    except (ServiceError, KeyError) as error:
        flash(request, str(error), "error")
        return redirect(f"/app/review/{document_id}?field={field_id}")
    return redirect(f"/app/review/{document_id}")


@router.post("/app/review/{document_id}/approve")
def approve_submit(request: Request, s: State, user: PageUser, document_id: int) -> Response:
    try:
        product_id = approve_document(
            s.store, facility_id=user["facility_id"], document_id=document_id, approver=user["name"]
        )
    except ServiceError as error:
        flash(request, str(error), "error")
        return redirect(f"/app/review/{document_id}")
    product = s.store.product(user["facility_id"], product_id)
    flash(request, f"{product['product_name'] if product else 'Product'} added to inventory.")
    waiting = [d for d in s.store.documents(user["facility_id"]) if d["status"] == "in_review"]
    return redirect(f"/app/review/{waiting[0]['id']}" if waiting else "/app/inventory")


@router.post("/app/review/{document_id}/retry")
def retry_submit(request: Request, s: State, user: PageUser, document_id: int) -> Response:
    document = s.store.document(user["facility_id"], document_id)
    if document and document["status"] == "failed":
        s.store.set_status(document_id, "queued", "Queued")
        s.enqueue(document_id)
        flash(request, f"Retrying {document['file_name']}.")
    return redirect("/app/review")


@router.post("/app/review/{document_id}/remove")
def remove_submit(request: Request, s: State, user: PageUser, document_id: int) -> Response:
    if s.store.document(user["facility_id"], document_id):
        s.store.delete_document(user["facility_id"], document_id)
        flash(request, "File removed.")
    return redirect("/app/review")


def _flagged(s: AppState, user: Row) -> tuple[list[dict[str, Any]], set[int]]:
    flags = all_flags(s.store, user["facility_id"], s.today())
    return flags, {f["product"]["id"] for f in flags if "product" in f}


@router.get("/app/inventory", response_class=HTMLResponse)
def inventory_page(
    request: Request,
    s: State,
    user: PageUser,
    q: str = "",
    supplier: str = "",
    hazard: str = "",
    status: str = "",
) -> HTMLResponse:
    products = s.store.products(user["facility_id"])
    flags, flagged = _flagged(s, user)
    first_flag = {f["product"]["id"]: f["label"] for f in reversed(flags) if "product" in f}
    rows = filter_inventory(
        products, query=q, supplier=supplier, hazard=hazard, status=status, flagged=flagged
    )
    suppliers = sorted({p["supplier"] for p in products if p["supplier"]})
    hazards = sorted({h["h_code"] for p in products for h in p["h_codes"]})
    return render(
        request,
        "inventory.html",
        s,
        user,
        active="inventory",
        rows=rows,
        total=len(products),
        suppliers=suppliers,
        hazards=hazards,
        first_flag=first_flag,
        filters={"q": q, "supplier": supplier, "hazard": hazard, "status": status},
    )


@router.get("/app/products/{product_id}", response_class=HTMLResponse)
def product_page(
    request: Request, s: State, user: PageUser, product_id: int, field: int | None = None
) -> Response:
    product = s.store.product(user["facility_id"], product_id)
    if product is None:
        flash(request, "That product does not exist.", "error")
        return redirect("/app/inventory")
    document = s.store.document(user["facility_id"], product["sds_id"])
    fields = s.store.fields(product["sds_id"])
    current: Row | None = next((f for f in fields if f["id"] == field), None) or (
        fields[0] if fields else None
    )
    page_no = (current or {}).get("page") or 1
    try:
        text = page_text(document, page_no) if document else ""
    except (ServiceError, OSError):
        text = ""
    facility = s.store.facility(user["facility_id"]) or {"sds_max_age_years": 3}
    return render(
        request,
        "product.html",
        s,
        user,
        active="inventory",
        product=product,
        fields=fields,
        current=current,
        page_no=page_no,
        document=document,
        flags=flags_for(product, facility["sds_max_age_years"], s.today()),
        page_html=highlight(text, current["quote"] if current and current["value"] else None),
    )


@router.post("/app/products/{product_id}/reopen")
def reopen_submit(request: Request, s: State, user: PageUser, product_id: int) -> Response:
    try:
        document_id = reopen_document(s.store, facility_id=user["facility_id"], product_id=product_id)
    except ServiceError as error:
        flash(request, str(error), "error")
        return redirect("/app/inventory")
    flash(request, "Review reopened. The product stays in the inventory until you approve it again.")
    return redirect(f"/app/review/{document_id}")


@router.post("/app/products/{product_id}/note")
def note_submit(
    request: Request, s: State, user: PageUser, product_id: int, note: Annotated[str, Form()]
) -> Response:
    s.store.set_product_note(user["facility_id"], product_id, note.strip()[:1000])
    flash(request, "Note saved.")
    return redirect("/app/actions")


@router.get("/app/actions", response_class=HTMLResponse)
def actions_page(request: Request, s: State, user: PageUser, kind: str = "all") -> HTMLResponse:
    flags, _ = _flagged(s, user)
    kinds = {
        "all": "All",
        "old_sds": "SDS too old",
        "missing_cas": "Missing CAS",
        "missing_sections": "Missing sections",
        "unreadable": "Unreadable file",
    }
    counts = {k: (len(flags) if k == "all" else sum(f["kind"] == k for f in flags)) for k in kinds}
    rows = flags if kind == "all" else [f for f in flags if f["kind"] == kind]
    return render(
        request, "actions.html", s, user, active="action", rows=rows, kinds=kinds, counts=counts, kind=kind
    )


@router.get("/app/settings", response_class=HTMLResponse)
def settings_page(request: Request, s: State, user: PageUser) -> HTMLResponse:
    return render(request, "settings.html", s, user, active="settings", error=None)


@router.post("/app/settings")
def settings_submit(
    request: Request,
    s: State,
    user: PageUser,
    name: Annotated[str, Form()],
    sds_max_age_years: Annotated[str, Form()],
    location: Annotated[str, Form()] = "",
    solution_provider: Annotated[str, Form()] = "",
) -> Response:
    if not sds_max_age_years.isdigit() or not 1 <= int(sds_max_age_years) <= 10:
        return render(
            request,
            "settings.html",
            s,
            user,
            active="settings",
            error="Enter a whole number of years from 1 to 10.",
        )
    s.store.update_facility(
        user["facility_id"],
        name=name.strip() or "Facility",
        location=location.strip(),
        solution_provider=solution_provider.strip(),
        sds_max_age_years=int(sds_max_age_years),
    )
    flash(request, "Settings saved. Action flags updated.")
    return redirect("/app/settings")


@router.get("/app/profile", response_class=HTMLResponse)
def profile_page(request: Request, s: State, user: PageUser) -> HTMLResponse:
    approvals = sum(1 for p in s.store.products(user["facility_id"]) if p["approved_by"] == user["name"])
    return render(request, "profile.html", s, user, active="profile", approvals=approvals)


@router.post("/app/profile")
def profile_submit(
    request: Request,
    s: State,
    user: PageUser,
    name: Annotated[str, Form()],
    role: Annotated[str, Form()] = "",
) -> Response:
    if not name.strip():
        flash(request, "Enter your name.", "error")
        return redirect("/app/profile")
    s.store.run(
        "UPDATE app_user SET name = ?, role = ? WHERE id = ?",
        name.strip(),
        role.strip() or "Chemical manager",
        user["id"],
    )
    flash(request, "Profile saved.")
    return redirect("/app/profile")


@router.post("/app/profile/password")
def password_submit(
    request: Request, s: State, user: PageUser, current: Annotated[str, Form()], new: Annotated[str, Form()]
) -> Response:
    try:
        auth.change_password(s.store, user, current, new)
    except auth.AuthError as error:
        flash(request, str(error), "error")
        return redirect("/app/profile")
    fresh = s.store.user(user["id"])
    if fresh:
        start_session(request, fresh)  # stay signed in here; other devices are signed out
    flash(request, "Password updated. Other devices were signed out.")
    return redirect("/app/profile")


@router.post("/app/profile/signout-all")
def signout_all_submit(request: Request, s: State, user: PageUser) -> Response:
    auth.sign_out_everywhere(s.store, user["id"])
    request.session.clear()
    request.session["flash"] = [{"message": "Signed out of all devices.", "kind": "success"}]
    return redirect("/")


def signin_redirect(next_path: str) -> RedirectResponse:
    return redirect(f"/signin?next={url_quote(next_path)}")


def as_json(value: Any) -> str:
    return json.dumps(value)
