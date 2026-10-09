"""Create the demo account with fictional SDS files.

    uv run chemready seed-demo

Sign in with demo@chemready.app / demo1234. Two products are approved and two
SDS files wait for review, so every screen has something to show. The files are
fictional and processed by the rules baseline, so no AI account is needed.
"""

from chemready.app import auth
from chemready.app.service import accept_uploads, approve_document, process_document
from chemready.app.store import Store
from chemready.config import Settings
from chemready.demo.synthetic import make_sds_pdf
from chemready.demo.synthetic_set import SPECS
from chemready.extraction.baseline import RulesClient

DEMO_EMAIL = "demo@chemready.app"
DEMO_PASSWORD = "demo1234"  # noqa: S105 - public demo account with fictional data only
DEMO_NAME = "Rahima Akter"
APPROVE = ("synthetic-002", "synthetic-003")


def seed_demo(settings: Settings, store: Store | None = None) -> str:
    store = store or Store(settings.database_path)
    if store.user_by_email(DEMO_EMAIL):
        return f"Demo account already exists. Sign in with {DEMO_EMAIL} / {DEMO_PASSWORD}."
    user = auth.sign_up(
        store,
        name=DEMO_NAME,
        email=DEMO_EMAIL,
        password=DEMO_PASSWORD,
        facility_name="Demo Washing Ltd",
        max_age=settings.sds_max_age_years,
    )
    store.update_facility(user["facility_id"], location="Gazipur")
    files = [(f"{spec.product_name} SDS.pdf", make_sds_pdf(spec)) for spec, _ in SPECS.values()]
    results = accept_uploads(
        store, settings, facility_id=user["facility_id"], user_id=user["id"], files=files, private=False
    )
    for (sds_id, _), result in zip(SPECS.items(), results, strict=True):
        if result.document_id is None:
            continue
        process_document(store, result.document_id, RulesClient)
        if sds_id in APPROVE:
            approve_document(
                store, facility_id=user["facility_id"], document_id=result.document_id, approver=DEMO_NAME
            )
    return f"Demo account created. Sign in with {DEMO_EMAIL} / {DEMO_PASSWORD}."
