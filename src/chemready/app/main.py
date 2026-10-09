"""FastAPI application: JSON API under /api (the HTML pages are added in web.py).

Run it:  uv run chemready serve   (or)   uv run uvicorn chemready.app.main:app --reload
"""

import logging
import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from chemready import __version__
from chemready.app import auth
from chemready.app.service import (
    ServiceError,
    Worker,
    accept_uploads,
    all_flags,
    approve_document,
    export_cil,
    filter_inventory,
    flags_for,
    open_review_count,
    page_text,
    process_document,
    reopen_document,
    resolve_field,
)
from chemready.app.store import Row, Store
from chemready.config import Settings, get_settings
from chemready.extraction.llm import LlmClient, make_client

log = logging.getLogger("chemready.app")


class AppState:
    """Everything a request needs, created once per app."""

    def __init__(
        self, settings: Settings, store: Store, client_factory: Callable[[], LlmClient], inline: bool
    ):
        self.settings = settings
        self.store = store
        self.client_factory = client_factory
        self.inline = inline
        self.throttle = auth.SignInThrottle.create()
        self.worker = Worker(store, client_factory)
        self.today: Callable[[], date] = date.today

    def enqueue(self, document_id: int) -> None:
        if self.inline:
            process_document(self.store, document_id, self.client_factory)
        else:
            self.worker.submit(document_id)


def state(request: Request) -> AppState:
    app_state: AppState = request.app.state.chemready
    return app_state


State = Annotated[AppState, Depends(state)]


def optional_user(request: Request, app_state: State) -> Row | None:
    user_id, version = request.session.get("uid"), request.session.get("ver")
    if user_id is None:
        return None
    user = app_state.store.user(int(user_id))
    if user is None or user["session_version"] != version:
        request.session.clear()
        return None
    return user


def current_user(user: Annotated[Row | None, Depends(optional_user)]) -> Row:
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in.")
    return user


User = Annotated[Row, Depends(current_user)]


def start_session(request: Request, user: Row) -> None:
    request.session.clear()
    request.session.update({"uid": user["id"], "ver": user["session_version"]})


def public_user(user: Row) -> dict[str, Any]:
    return {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}


# ---------- Request bodies ----------


class SignUpBody(BaseModel):
    name: str
    email: str
    password: str
    facility_name: str


class SignInBody(BaseModel):
    email: str
    password: str


class ResetStartBody(BaseModel):
    email: str


class ResetFinishBody(BaseModel):
    token: str
    new_password: str


class FieldAction(BaseModel):
    action: str = Field(pattern="^(approve|edit|missing)$")
    value: str | None = None


class NoteBody(BaseModel):
    note: str = Field(max_length=1000)


class SettingsBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    location: str = Field(default="", max_length=200)
    solution_provider: str = Field(default="", max_length=200)
    sds_max_age_years: int = Field(ge=1, le=10)


def _bad_request(error: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(error))


def create_app(
    settings: Settings | None = None,
    *,
    store: Store | None = None,
    client_factory: Callable[[], LlmClient] | None = None,
    inline_processing: bool = False,
) -> FastAPI:
    settings = settings or get_settings()
    store = store or Store(settings.database_path)
    factory = client_factory or (lambda: make_client(settings))
    app_state = AppState(settings, store, factory, inline_processing)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if not inline_processing:
            app_state.worker.start()
        yield
        if not inline_processing:
            app_state.worker.stop()

    app = FastAPI(title="ChemReady", version=__version__, lifespan=lifespan)
    app.state.chemready = app_state
    secret = settings.secret_key.get_secret_value() if settings.secret_key else secrets.token_urlsafe(48)
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret,
        session_cookie="chemready_session",
        same_site="lax",
        https_only=settings.environment == "production",
        max_age=60 * 60 * 12,
    )

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, error: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(error)})

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    # ----- Accounts -----

    @app.post("/api/auth/signup", status_code=201)
    def sign_up(body: SignUpBody, request: Request, s: State) -> dict[str, Any]:
        try:
            user = auth.sign_up(
                s.store,
                name=body.name,
                email=body.email,
                password=body.password,
                facility_name=body.facility_name,
                max_age=s.settings.sds_max_age_years,
            )
        except auth.AuthError as error:
            raise _bad_request(error) from error
        start_session(request, user)
        return public_user(user)

    @app.post("/api/auth/signin")
    def sign_in(body: SignInBody, request: Request, s: State) -> dict[str, Any]:
        try:
            user = auth.sign_in(s.store, s.throttle, email=body.email, password=body.password)
        except auth.AuthError as error:
            raise HTTPException(status_code=401, detail=str(error)) from error
        start_session(request, user)
        return public_user(user)

    @app.post("/api/auth/signout")
    def sign_out(request: Request) -> dict[str, bool]:
        request.session.clear()
        return {"signed_out": True}

    @app.post("/api/auth/signout-all")
    def sign_out_all(request: Request, user: User, s: State) -> dict[str, bool]:
        auth.sign_out_everywhere(s.store, user["id"])
        request.session.clear()
        return {"signed_out": True}

    @app.post("/api/auth/reset")
    def reset_start(body: ResetStartBody, s: State) -> dict[str, str]:
        token = auth.start_password_reset(s.store, body.email)
        if token:
            # No email service in the MVP (zero cost). Connect one before production use.
            log.warning("password reset requested; link: /reset?token=%s", token)
        return {"message": "If an account exists for this email, we have sent a link to reset the password."}

    @app.post("/api/auth/reset/confirm")
    def reset_finish(body: ResetFinishBody, s: State) -> dict[str, bool]:
        try:
            auth.finish_password_reset(s.store, body.token, body.new_password)
        except auth.AuthError as error:
            raise _bad_request(error) from error
        return {"reset": True}

    @app.get("/api/me")
    def me(user: User, s: State) -> dict[str, Any]:
        return {**public_user(user), "facility": s.store.facility(user["facility_id"])}

    # ----- Documents and review -----

    @app.get("/api/documents")
    def documents(user: User, s: State) -> list[Row]:
        return s.store.documents(user["facility_id"])

    @app.post("/api/documents")
    async def upload(
        user: User,
        s: State,
        files: Annotated[list[UploadFile], File()],
        public_sds: Annotated[bool, Form()] = False,
    ) -> dict[str, Any]:
        contents = [(f.filename or "file", await f.read()) for f in files]
        results = accept_uploads(
            s.store,
            s.settings,
            facility_id=user["facility_id"],
            user_id=user["id"],
            files=contents,
            private=not public_sds,
        )
        for result in results:
            if result.document_id is not None:
                s.enqueue(result.document_id)
        return {"results": [result.__dict__ for result in results]}

    def _document(s: AppState, user: Row, document_id: int) -> Row:
        document = s.store.document(user["facility_id"], document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found.")
        return document

    @app.post("/api/documents/{document_id}/retry")
    def retry(document_id: int, user: User, s: State) -> dict[str, str]:
        document = _document(s, user, document_id)
        if document["status"] != "failed":
            raise HTTPException(status_code=409, detail="Only failed documents can be retried.")
        s.store.set_status(document_id, "queued", "Queued")
        s.enqueue(document_id)
        return {"status": "queued"}

    @app.delete("/api/documents/{document_id}", status_code=204)
    def delete(document_id: int, user: User, s: State) -> Response:
        _document(s, user, document_id)
        s.store.delete_document(user["facility_id"], document_id)
        return Response(status_code=204)

    @app.get("/api/documents/{document_id}/review")
    def review(document_id: int, user: User, s: State) -> dict[str, Any]:
        document = _document(s, user, document_id)
        fields = s.store.fields(document_id)
        return {"document": document, "fields": fields, "open_reviews": open_review_count(fields)}

    @app.get("/api/documents/{document_id}/pages/{page}")
    def page(document_id: int, page: int, user: User, s: State) -> dict[str, Any]:
        return {"page": page, "text": page_text(_document(s, user, document_id), page)}

    @app.post("/api/fields/{field_id}")
    def field_action(field_id: int, body: FieldAction, user: User, s: State) -> dict[str, str]:
        resolve_field(
            s.store,
            facility_id=user["facility_id"],
            field_id=field_id,
            action=body.action,
            value=body.value,
            reviewer=user["name"],
        )
        return {"status": "saved"}

    @app.post("/api/documents/{document_id}/approve")
    def approve(document_id: int, user: User, s: State) -> dict[str, int]:
        product_id = approve_document(
            s.store, facility_id=user["facility_id"], document_id=document_id, approver=user["name"]
        )
        return {"product_id": product_id}

    # ----- Inventory, actions, settings, export -----

    def _flagged_ids(s: AppState, user: Row) -> set[int]:
        return {
            f["product"]["id"] for f in all_flags(s.store, user["facility_id"], s.today()) if "product" in f
        }

    @app.get("/api/inventory")
    def inventory(
        user: User, s: State, q: str = "", supplier: str = "", hazard: str = "", status: str = ""
    ) -> dict[str, Any]:
        products = s.store.products(user["facility_id"])
        flagged = _flagged_ids(s, user)
        rows = filter_inventory(
            products, query=q, supplier=supplier, hazard=hazard, status=status, flagged=flagged
        )
        return {"total": len(products), "products": rows}

    @app.get("/api/products/{product_id}")
    def product(product_id: int, user: User, s: State) -> dict[str, Any]:
        item = s.store.product(user["facility_id"], product_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Product not found.")
        facility = s.store.facility(user["facility_id"]) or {"sds_max_age_years": 3}
        flags = [f.__dict__ for f in flags_for(item, facility["sds_max_age_years"], s.today())]
        return {"product": item, "fields": s.store.fields(item["sds_id"]), "flags": flags}

    @app.post("/api/products/{product_id}/reopen")
    def reopen(product_id: int, user: User, s: State) -> dict[str, int]:
        return {
            "document_id": reopen_document(s.store, facility_id=user["facility_id"], product_id=product_id)
        }

    @app.put("/api/products/{product_id}/note")
    def note(product_id: int, body: NoteBody, user: User, s: State) -> dict[str, str]:
        s.store.set_product_note(user["facility_id"], product_id, body.note.strip())
        return {"status": "saved"}

    @app.get("/api/actions")
    def actions(user: User, s: State) -> list[dict[str, Any]]:
        return all_flags(s.store, user["facility_id"], s.today())

    @app.get("/api/settings")
    def get_facility(user: User, s: State) -> Row | None:
        return s.store.facility(user["facility_id"])

    @app.put("/api/settings")
    def put_facility(body: SettingsBody, user: User, s: State) -> Row | None:
        s.store.update_facility(user["facility_id"], **body.model_dump())
        return s.store.facility(user["facility_id"])

    @app.get("/api/export.xlsx")
    def export(user: User, s: State) -> Response:
        facility = s.store.facility(user["facility_id"]) or {"name": "facility"}
        name = "".join(ch for ch in facility["name"] if ch.isalnum()) or "facility"
        filename = f"ChemReady_CIL_{name}_{s.today():%Y-%m}.xlsx"
        return Response(
            export_cil(s.store, user["facility_id"], s.today()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return app


def app_factory() -> FastAPI:
    """Used by `uvicorn --factory chemready.app.main:app_factory`."""
    return create_app()
