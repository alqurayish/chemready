"""Observability: structured logs, request ids, and a trace of every model call.

* Every log line can be JSON, with the request id, so one problem can be followed
  through all its log lines.
* Every model call is saved in the model_call table: provider, model, prompt
  version, tokens, time, retries, cost and any error. This answers "how much did
  this month cost?", "is it getting slower?" and "which document failed and why?".
"""

import contextvars
import json
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from chemready.app.store import Row, Store
from chemready.extraction.llm import LlmClient, LlmError, LlmResult

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
log = logging.getLogger("chemready.trace")

_STANDARD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """One JSON object per line: time, level, logger, message, request id and any extra fields."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id.get(),
        }
        entry.update({key: value for key, value in record.__dict__.items() if key not in _STANDARD})
        if record.exc_info:
            entry["error"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def setup_logging(log_format: str, level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if log_format == "json"
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger("chemready")
    root.handlers[:] = [handler]
    root.setLevel(level)
    root.propagate = False


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Give every request an id (or reuse the caller's X-Request-ID) and return it in the response."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get("x-request-id", "")[:64] or uuid.uuid4().hex[:16]
        token = request_id.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            logging.getLogger("chemready.http").info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "ms": round((time.perf_counter() - start) * 1000, 1),
                },
            )
            return response
        finally:
            request_id.reset(token)


def cost_usd(input_tokens: int, output_tokens: int, price_in: float, price_out: float) -> float:
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


class TracedClient:
    """Wraps any LlmClient and records every call, successful or not."""

    def __init__(
        self,
        inner: LlmClient,
        store: Store,
        *,
        facility_id: int | None,
        document_id: int | None,
        prompt_version: str,
        price_in: float,
        price_out: float,
    ):
        self.inner = inner
        self.provider = inner.provider
        self.model = inner.model
        self.allows_private_data = inner.allows_private_data
        self._store = store
        self._context = (facility_id, document_id, prompt_version)
        self._prices = (price_in, price_out)

    def extract[T: BaseModel](self, schema: type[T], system: str, text: str) -> LlmResult[T]:
        trace_id = uuid.uuid4().hex[:16]
        start = time.perf_counter()
        try:
            result = self.inner.extract(schema, system, text)
        except LlmError as error:
            self._record(trace_id, 0, 0, (time.perf_counter() - start) * 1000, 1, ok=False, error=str(error))
            raise
        usage = result.usage
        self._record(
            trace_id, usage.input_tokens, usage.output_tokens, usage.latency_ms, usage.attempts, ok=True
        )
        return result

    def _record(
        self,
        trace_id: str,
        tokens_in: int,
        tokens_out: int,
        ms: float,
        attempts: int,
        *,
        ok: bool,
        error: str = "",
    ) -> None:
        facility_id, document_id, prompt_version = self._context
        cost = cost_usd(tokens_in, tokens_out, *self._prices)
        self._store.run(
            "INSERT INTO model_call (facility_id, document_id, trace_id, provider, model, prompt_version,"
            " input_tokens, output_tokens, latency_ms, attempts, cost_usd, ok, error)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            facility_id,
            document_id,
            trace_id,
            self.provider,
            self.model,
            prompt_version,
            tokens_in,
            tokens_out,
            ms,
            attempts,
            cost,
            int(ok),
            error or None,
        )
        log.info(
            "model call",
            extra={
                "trace_id": trace_id,
                "document_id": document_id,
                "provider": self.provider,
                "model": self.model,
                "prompt_version": prompt_version,
                "input_tokens": tokens_in,
                "output_tokens": tokens_out,
                "latency_ms": round(ms, 1),
                "attempts": attempts,
                "cost_usd": round(cost, 6),
                "ok": ok,
            },
        )


def usage_summary(store: Store, facility_id: int, since: str) -> Row:
    """Calls, tokens, cost and failures for a facility since a date (YYYY-MM-DD)."""
    row = store.one(
        "SELECT COUNT(*) AS calls, COALESCE(SUM(input_tokens), 0) AS input_tokens,"
        " COALESCE(SUM(output_tokens), 0) AS output_tokens, COALESCE(SUM(cost_usd), 0) AS cost_usd,"
        " COALESCE(AVG(latency_ms), 0) AS mean_latency_ms, COALESCE(SUM(1 - ok), 0) AS failed"
        " FROM model_call WHERE facility_id = ? AND created_at >= ?",
        facility_id,
        since,
    )
    return row or {}
