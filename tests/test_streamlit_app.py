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


def test_opens_on_upload_without_a_landing_page(app: AppTest) -> None:
    app.run()

    assert not app.exception
    assert [header.value for header in app.header] == ["Upload SDS files"]
    upload = next(button for button in app.button if button.label == "Upload and process")
    assert upload.disabled  # nothing chosen yet


def test_sign_in_opens_as_a_popup(app: AppTest) -> None:
    app.run()
    next(button for button in app.button if button.key == "header_sign_in").click().run()

    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Use the demo account" in labels
    assert "Create account" in labels


def test_signed_in_user_sees_their_name(app: AppTest) -> None:
    app.run()
    app.session_state["user_id"] = 1  # the seeded demo user
    app.run()

    assert not app.exception
    assert not any(button.key == "header_sign_in" for button in app.button)
    assert any("Rahima Akter" in markdown.value for markdown in app.markdown)
