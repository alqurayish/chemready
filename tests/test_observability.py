"""Tests for tracing, cost, logs, request ids, error handling, the eval gate and the PDF fetcher."""

import json
import logging
from datetime import date
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from chemready.app.main import create_app
from chemready.app.observability import JsonFormatter, TracedClient, cost_usd, request_id, usage_summary
from chemready.app.store import Store
from chemready.config import Settings
from chemready.demo.seed import DEMO_EMAIL, DEMO_PASSWORD, seed_demo
from chemready.demo.synthetic_set import build
from chemready.evals.fetch_pdfs import fetch
from chemready.evals.formats import write_json
from chemready.evals.run_evals import main as run_evals
from chemready.evals.run_extraction import run
from chemready.extraction.baseline import RulesClient
from chemready.extraction.llm import FakeClient, LlmError
from chemready.schema import SdsExtraction


def test_cost_is_tokens_times_price_per_million() -> None:
    assert cost_usd(1_000_000, 500_000, 0.30, 2.50) == pytest.approx(0.30 + 1.25)
    assert cost_usd(10_000, 2_000, 0.0, 0.0) == 0.0


def test_every_model_call_is_traced_with_tokens_and_cost(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    facility = store.create_facility("F", 3)
    traced = TracedClient(
        FakeClient(["{}"]),
        store,
        facility_id=facility,
        document_id=7,
        prompt_version="v1",
        price_in=1.0,
        price_out=2.0,
    )

    traced.extract(SdsExtraction, "system", "text")

    calls = store.all("SELECT * FROM model_call")
    assert len(calls) == 1
    assert calls[0]["provider"] == "fake" and calls[0]["document_id"] == 7 and calls[0]["ok"] == 1
    assert calls[0]["prompt_version"] == "v1"


def test_failed_model_calls_are_traced_too(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    traced = TracedClient(
        FakeClient(['{"bad": 1}']),
        store,
        facility_id=None,
        document_id=1,
        prompt_version="v1",
        price_in=0,
        price_out=0,
    )

    with pytest.raises(LlmError):
        traced.extract(SdsExtraction, "s", "t")

    call = store.one("SELECT * FROM model_call")
    assert call is not None and call["ok"] == 0 and "does not match the schema" in call["error"]


def test_json_log_lines_include_request_id_and_extra_fields() -> None:
    record = logging.LogRecord("chemready.trace", logging.INFO, __file__, 1, "model call", (), None)
    record.input_tokens = 120
    token = request_id.set("abc123")
    try:
        line = json.loads(JsonFormatter().format(record))
    finally:
        request_id.reset(token)

    assert line["message"] == "model call" and line["request_id"] == "abc123" and line["input_tokens"] == 120


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_path=tmp_path / "db.sqlite", upload_dir=tmp_path / "up", llm_provider="rules"
    )
    store = Store(settings.database_path)
    seed_demo(settings, store)
    app = create_app(settings, store=store, client_factory=RulesClient, inline_processing=True)
    app.state.chemready.today = date.today

    @app.get("/api/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    return TestClient(app, raise_server_exceptions=False)


def test_responses_carry_a_request_id(client: TestClient) -> None:
    assert len(client.get("/healthz").headers["x-request-id"]) == 16
    assert client.get("/healthz", headers={"X-Request-ID": "mine"}).headers["x-request-id"] == "mine"


def test_unexpected_errors_never_leak_details(client: TestClient) -> None:
    response = client.get("/api/boom")

    assert response.status_code == 500
    assert "secret internal detail" not in response.text
    assert response.json()["request_id"] in response.json()["detail"]


def test_usage_endpoint_and_settings_page_show_this_months_calls(client: TestClient) -> None:
    client.post("/api/auth/signin", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})

    usage = client.get("/api/usage").json()

    assert usage["calls"] == 4  # the demo processed four fictional SDS files
    assert usage["failed"] == 0
    assert "AI usage this month" in client.get("/app/settings").text


def test_usage_summary_is_per_facility(tmp_path: Path) -> None:
    store = Store(tmp_path / "db.sqlite")
    one, two = store.create_facility("One", 3), store.create_facility("Two", 3)
    TracedClient(
        FakeClient(["{}"]),
        store,
        facility_id=one,
        document_id=1,
        prompt_version="v1",
        price_in=0,
        price_out=0,
    ).extract(SdsExtraction, "s", "t")

    assert usage_summary(store, one, "2000-01-01")["calls"] == 1
    assert usage_summary(store, two, "2000-01-01")["calls"] == 0


def test_eval_gate_compares_with_the_baseline(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    build(tmp_path)
    run(tmp_path / "gold", tmp_path / "pdfs", tmp_path / "runs" / "now", RulesClient())
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"field_accuracy": 1.0, "code_recall": 1.0}))
    too_high = tmp_path / "too_high.json"
    too_high.write_text(json.dumps({"field_accuracy": 1.5, "code_recall": 1.0}))
    common = [
        "--gold",
        str(tmp_path / "gold"),
        "--pdfs",
        str(tmp_path / "pdfs"),
        "--predictions",
        str(tmp_path / "runs" / "now"),
    ]

    assert run_evals([*common, "--gate", "--baseline", str(good)]) == 0
    assert run_evals([*common, "--gate", "--baseline", str(too_high)]) == 1
    assert "fell from 150.0%" in capsys.readouterr().out
    assert run_evals([*common, "--limit", "2"]) == 0


def test_fetch_downloads_missing_pdfs_and_reports_problems(tmp_path: Path) -> None:
    records = build(tmp_path)
    for index, record in enumerate(records[:3]):
        record.synthetic = False
        record.file = f"real-{index}.pdf"
        record.source.url = f"https://publisher.test/sds-{index}.pdf" if index < 2 else None
        write_json(record, tmp_path / "gold" / f"{record.sds_id}.json")
    responses = {
        "https://publisher.test/sds-0.pdf": httpx.Response(200, content=b"%PDF-1.7 fake"),
        "https://publisher.test/sds-1.pdf": httpx.Response(200, content=b"<html>not a pdf</html>"),
    }
    client = httpx.Client(transport=httpx.MockTransport(lambda request: responses[str(request.url)]))

    problems = fetch(tmp_path / "gold", tmp_path / "pdfs", client)

    assert (tmp_path / "pdfs" / "real-0.pdf").read_bytes().startswith(b"%PDF")
    assert any("did not return a PDF" in p for p in problems)
    assert any("no source URL" in p for p in problems)
