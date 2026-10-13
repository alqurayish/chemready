"""Smoke test for the Streamlit front end, using Streamlit's own headless test runner."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[1] / "streamlit_app.py")


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.setenv("CHEMREADY_DATABASE_PATH", str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("CHEMREADY_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("CHEMREADY_LLM_PROVIDER", "rules")
    import streamlit as st

    st.cache_resource.clear()
    return AppTest.from_file(APP, default_timeout=60)


def test_public_page_then_demo_sign_in_shows_the_inventory(app: AppTest) -> None:
    app.run()
    assert not app.exception
    assert "audit-ready chemical inventory" in app.title[0].value

    next(button for button in app.button if button.label == "Try the demo").click().run()

    assert not app.exception
    assert any(header.value == "Inventory" for header in app.header)
    table = app.dataframe[0].value
    assert set(table["Product"]) == {"Demo Caustic Flakes", "Demobind XL"}


def test_wrong_password_shows_an_error(app: AppTest) -> None:
    app.run()
    app.text_input[0].input("demo@chemready.app")
    app.text_input[1].input("wrong-password")
    app.button[1].click().run()  # the "Sign in" form button

    assert any("do not match" in error.value for error in app.error)
