"""One small interface for every model: llm.extract(schema, system, text).

Switching from Gemini to a local model (or anything else) is a settings change,
and the evals tell us which one wins. Every call returns the parsed output plus
usage (tokens and time) for tracing and cost.
"""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx
from pydantic import BaseModel, ValidationError

from chemready.config import Settings

RETRY_DELAYS_SECONDS = (2.0, 4.0, 8.0, 16.0)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class LlmError(Exception):
    """The model call failed or returned output that does not match the schema."""


@dataclass(frozen=True)
class LlmUsage:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    attempts: int = 1


@dataclass(frozen=True)
class LlmResult[T: BaseModel]:
    output: T
    usage: LlmUsage


class LlmClient(Protocol):
    """Anything that can fill a Pydantic schema from text."""

    provider: str
    model: str
    allows_private_data: bool

    def extract[T: BaseModel](self, schema: type[T], system: str, text: str) -> LlmResult[T]: ...


def parse_output[T: BaseModel](schema: type[T], raw: str) -> T:
    """Reject any output that is not valid JSON for the schema. Never repair or guess."""
    try:
        return schema.model_validate_json(raw)
    except ValidationError as error:
        raise LlmError(f"Model output does not match the schema: {error.error_count()} problem(s)") from error


def _with_retries[R](
    call: Callable[[], R], is_retryable: Callable[[Exception], bool], sleep: Callable[[float], None]
) -> tuple[R, int]:
    """Retry rate limits and server errors with growing waits (free tiers are rate limited)."""
    for attempt, delay in enumerate((*RETRY_DELAYS_SECONDS, None), start=1):
        try:
            return call(), attempt
        except Exception as error:
            if delay is None or not is_retryable(error):
                raise
            sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


class GeminiClient:
    """Google Gemini with structured output. Public SDS files only while on the free tier."""

    provider = "gemini"

    def __init__(
        self, api_key: str, model: str, free_tier: bool, sleep: Callable[[float], None] = time.sleep
    ):
        from google import genai  # imported here so tests and offline use do not need it

        self.model = model
        self.allows_private_data = not free_tier
        self._client = genai.Client(api_key=api_key)
        self._sleep = sleep

    def extract[T: BaseModel](self, schema: type[T], system: str, text: str) -> LlmResult[T]:
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=schema,
        )

        def call() -> types.GenerateContentResponse:
            return self._client.models.generate_content(model=self.model, contents=text, config=config)

        def retryable(error: Exception) -> bool:
            return isinstance(error, errors.APIError) and error.code in RETRYABLE_STATUS

        start = time.perf_counter()
        try:
            response, attempts = _with_retries(call, retryable, self._sleep)
        except errors.APIError as error:
            raise LlmError(f"Gemini call failed ({error.code}): {error.message}") from error
        latency = (time.perf_counter() - start) * 1000
        usage = response.usage_metadata
        output_tokens = (
            (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0) if usage else 0
        )
        return LlmResult(
            output=parse_output(schema, response.text or ""),
            usage=LlmUsage(
                provider=self.provider,
                model=self.model,
                input_tokens=(usage.prompt_token_count or 0) if usage else 0,
                output_tokens=output_tokens,
                latency_ms=latency,
                attempts=attempts,
            ),
        )


class OllamaClient:
    """A local open-weight model through Ollama. Files never leave the machine."""

    provider = "ollama"
    allows_private_data = True

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 300.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.model = model
        self._http = httpx.Client(base_url=base_url, timeout=timeout_seconds, transport=transport)
        self._sleep = sleep

    def extract[T: BaseModel](self, schema: type[T], system: str, text: str) -> LlmResult[T]:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": text}],
            "format": schema.model_json_schema(),
            "stream": False,
            "options": {"temperature": 0},
        }

        def call() -> httpx.Response:
            response = self._http.post("/api/chat", json=body)
            response.raise_for_status()
            return response

        def retryable(error: Exception) -> bool:
            return isinstance(error, httpx.HTTPStatusError) and error.response.status_code in RETRYABLE_STATUS

        start = time.perf_counter()
        try:
            response, attempts = _with_retries(call, retryable, self._sleep)
        except httpx.HTTPError as error:
            raise LlmError(f"Ollama call failed: {error}") from error
        latency = (time.perf_counter() - start) * 1000
        data = response.json()
        return LlmResult(
            output=parse_output(schema, data.get("message", {}).get("content", "")),
            usage=LlmUsage(
                provider=self.provider,
                model=self.model,
                input_tokens=int(data.get("prompt_eval_count", 0)),
                output_tokens=int(data.get("eval_count", 0)),
                latency_ms=latency,
                attempts=attempts,
            ),
        )


class FakeClient:
    """Returns prepared JSON. For tests only."""

    provider = "fake"
    allows_private_data = True

    def __init__(self, responses: list[str], model: str = "fake-model"):
        self.model = model
        self.calls: list[tuple[str, str]] = []
        self._responses = list(responses)

    def extract[T: BaseModel](self, schema: type[T], system: str, text: str) -> LlmResult[T]:
        self.calls.append((system, text))
        raw = self._responses.pop(0) if self._responses else json.dumps({})
        return LlmResult(
            output=parse_output(schema, raw), usage=LlmUsage(self.provider, self.model, 0, 0, 0.0)
        )


def make_client(settings: Settings) -> LlmClient:
    """Build the client chosen in settings."""
    if settings.llm_provider == "gemini":
        if settings.gemini_api_key is None or settings.gemini_model is None:  # Settings already checks this
            raise LlmError("Gemini needs CHEMREADY_GEMINI_API_KEY and CHEMREADY_GEMINI_MODEL.")
        return GeminiClient(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
            free_tier=settings.gemini_free_tier,
        )
    if settings.llm_provider == "rules":
        from chemready.extraction.baseline import RulesClient

        return RulesClient()
    if not settings.ollama_model:
        raise LlmError("Set CHEMREADY_OLLAMA_MODEL to a model you have pulled with `ollama pull`.")
    return OllamaClient(base_url=settings.ollama_base_url, model=settings.ollama_model)


def extract[S: BaseModel](schema: type[S], system: str, text: str, client: LlmClient) -> LlmResult[S]:
    """The one entry point the rest of the code uses."""
    return client.extract(schema, system, text)
