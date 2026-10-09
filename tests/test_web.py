"""Tests for the server-rendered pages: public pages, sign-in redirects and the main forms."""

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chemready.app.main import create_app
from chemready.app.store import Store
from chemready.app.web import highlight, nice_date, safe_next
from chemready.config import Settings
from chemready.demo.seed import DEMO_EMAIL, DEMO_PASSWORD, seed_demo
from chemready.demo.synthetic import make_sds_pdf
from chemready.demo.synthetic_set import SPECS
from chemready.extraction.baseline import RulesClient


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_path=tmp_path / "db.sqlite", upload_dir=tmp_path / "uploads", llm_provider="rules"
    )
    store = Store(settings.database_path)
    seed_demo(settings, store)
    app = create_app(settings, store=store, client_factory=RulesClient, inline_processing=True)
    app.state.chemready.today = lambda: date(2026, 10, 9)
    return TestClient(app)


def _sign_in(client: TestClient) -> None:
    response = client.post(
        "/signin", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "next": "/app/inventory"}
    )
    assert response.status_code == 200 and "Inventory" in response.text


def test_website_is_public_and_shows_branding(client: TestClient) -> None:
    page = client.get("/")
    assert page.status_code == 200
    assert "A D-SAi Product" in page.text
    assert "Md. Alqurayish Sharkar" in page.text
    assert client.get("/static/app.css").status_code == 200


@pytest.mark.parametrize(
    "path", ["/app/upload", "/app/review", "/app/inventory", "/app/actions", "/app/settings", "/app/profile"]
)
def test_app_pages_redirect_to_sign_in_with_intent(client: TestClient, path: str) -> None:
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/signin?next={path}"


def test_sign_in_returns_to_the_intended_page(client: TestClient) -> None:
    response = client.post(
        "/signin", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "next": "/app/upload"}
    )
    assert response.url.path == "/app/upload"
    assert "Upload SDS files" in response.text


def test_wrong_password_shows_a_clear_message(client: TestClient) -> None:
    response = client.post("/signin", data={"email": DEMO_EMAIL, "password": "wrong-password"})
    assert "That email and password do not match." in response.text


def test_redirects_never_leave_the_site() -> None:
    assert safe_next("https://evil.example") == "/app/inventory"
    assert safe_next("//evil.example") == "/app/inventory"
    assert safe_next("/app/review") == "/app/review"


def test_demo_button_signs_in(client: TestClient) -> None:
    assert client.post("/demo").url.path == "/app/inventory"


def test_sign_up_page_flow(client: TestClient) -> None:
    response = client.post(
        "/signup",
        data={
            "name": "New User",
            "email": "new@factory.test",
            "facility_name": "New Mill",
            "password": "long enough",
        },
    )
    assert response.url.path == "/app/inventory" and "Your inventory is empty" in response.text
    again = client.post(
        "/signup",
        data={"name": "X", "email": "new@factory.test", "facility_name": "Y", "password": "long enough"},
    )
    assert "already exists" in again.text


def test_upload_review_and_approve_through_pages(client: TestClient) -> None:
    _sign_in(client)
    spec = SPECS["synthetic-001"][0]
    pdf = make_sds_pdf(type(spec)(**{**spec.__dict__, "product_name": "Demowhite OB"}))

    upload = client.post("/app/upload", files=[("files", ("new.pdf", pdf, "application/pdf"))])
    assert "Added. Processing has started." in upload.text

    review_list = client.get("/app/review?tab=in_review")
    assert "Demowhite OB" in review_list.text
    documents = client.app.state.chemready.store.documents(1)  # type: ignore[attr-defined]
    target = next(d for d in documents if d["product_name"] == "Demowhite OB")

    page = client.get(f"/app/review/{target['id']}")
    assert '<mark class="q">Product name: Demowhite OB</mark>' in page.text

    approved = client.post(f"/app/review/{target['id']}/approve")
    assert "Demowhite OB added to inventory." in approved.text


def test_field_edit_rules_are_enforced_on_the_page(client: TestClient) -> None:
    _sign_in(client)
    store = client.app.state.chemready.store  # type: ignore[attr-defined]
    document = next(d for d in store.documents(1) if d["open_reviews"])
    field = next(f for f in store.fields(document["id"]) if f["status"] == "needs_review")

    bad = client.post(
        f"/app/fields/{field['id']}", data={"action": "edit", "value": "H3l9", "document_id": document["id"]}
    )
    assert "H plus 3 digits" in bad.text
    good = client.post(
        f"/app/fields/{field['id']}", data={"action": "edit", "value": "h319", "document_id": document["id"]}
    )
    assert "Saved your edit." in good.text


def test_inventory_product_actions_settings_profile_pages(client: TestClient) -> None:
    _sign_in(client)
    inventory = client.get("/app/inventory?status=action")
    assert "Needs action: SDS too old" in inventory.text
    product_id = client.app.state.chemready.store.products(1)[0]["id"]  # type: ignore[attr-defined]
    assert "Approved by Rahima Akter" in client.get(f"/app/products/{product_id}").text

    actions = client.get("/app/actions")
    assert "Missing CAS" in actions.text
    assert (
        "Note saved." in client.post(f"/app/products/{product_id}/note", data={"note": "Asked supplier"}).text
    )

    bad = client.post("/app/settings", data={"name": "Demo Washing Ltd", "sds_max_age_years": "11"})
    assert "Enter a whole number of years from 1 to 10." in bad.text
    ok = client.post("/app/settings", data={"name": "Demo Washing Ltd", "sds_max_age_years": "10"})
    assert "Settings saved." in ok.text
    assert "years old" not in client.get("/app/actions").text  # the old SDS flag closed

    assert (
        "Profile saved."
        in client.post("/app/profile", data={"name": "Rahima A.", "role": "EHS manager"}).text
    )
    wrong = client.post("/app/profile/password", data={"current": "nope", "new": "brand new pass"})
    assert "current password is not right" in wrong.text


def test_export_and_sign_out_everywhere(client: TestClient) -> None:
    _sign_in(client)
    assert client.get("/api/export.xlsx").status_code == 200
    client.post("/app/profile/signout-all")
    assert client.get("/app/inventory", follow_redirects=False).status_code == 303


def test_helpers() -> None:
    assert nice_date("2025-03-01") == "1 Mar 2025"
    assert nice_date(None) == "—"
    marked = highlight("a <b>\n\nProduct name: X", "Product name: X")
    assert str(marked) == 'a &lt;b&gt;\n<mark class="q">Product name: X</mark>'
