"""Tests for typed settings and the privacy rule."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from chemready.config import Settings, get_settings


def test_defaults_use_local_model_and_allow_private_data() -> None:
    settings = Settings()

    assert settings.llm_provider == "ollama"
    assert settings.allows_private_data is True
    assert settings.sds_max_age_years == 3
    assert settings.database_path == Path("data/private/chemready.sqlite")


def test_gemini_without_key_and_model_fails_at_start_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHEMREADY_LLM_PROVIDER", "gemini")

    with pytest.raises(ValidationError) as error:
        Settings()

    assert "CHEMREADY_GEMINI_API_KEY" in str(error.value)
    assert "CHEMREADY_GEMINI_MODEL" in str(error.value)


def test_gemini_free_tier_never_allows_private_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHEMREADY_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("CHEMREADY_GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("CHEMREADY_GEMINI_MODEL", "test-model")

    settings = Settings()

    assert settings.gemini_free_tier is True
    assert settings.allows_private_data is False


def test_paid_gemini_allows_private_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHEMREADY_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("CHEMREADY_GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("CHEMREADY_GEMINI_MODEL", "test-model")
    monkeypatch.setenv("CHEMREADY_GEMINI_FREE_TIER", "false")

    assert Settings().allows_private_data is True


def test_api_key_is_hidden_when_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHEMREADY_GEMINI_API_KEY", "super-secret-value")

    settings = Settings()

    assert "super-secret-value" not in str(settings.gemini_api_key)
    assert "super-secret-value" not in repr(settings)
    assert settings.gemini_api_key is not None
    assert settings.gemini_api_key.get_secret_value() == "super-secret-value"


@pytest.mark.parametrize("years", ["0", "11", "-1"])
def test_sds_max_age_outside_1_to_10_is_rejected(monkeypatch: pytest.MonkeyPatch, years: str) -> None:
    monkeypatch.setenv("CHEMREADY_SDS_MAX_AGE_YEARS", years)

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("years", ["1", "10"])
def test_sds_max_age_edges_are_accepted(monkeypatch: pytest.MonkeyPatch, years: str) -> None:
    monkeypatch.setenv("CHEMREADY_SDS_MAX_AGE_YEARS", years)

    assert Settings().sds_max_age_years == int(years)


def test_unknown_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHEMREADY_LLM_PROVIDER", "some-other-ai")

    with pytest.raises(ValidationError):
        Settings()


def test_empty_values_count_as_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHEMREADY_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("CHEMREADY_GEMINI_API_KEY", "")
    monkeypatch.setenv("CHEMREADY_GEMINI_MODEL", "")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_are_read_from_env_file() -> None:
    Path(".env").write_text("CHEMREADY_SDS_MAX_AGE_YEARS=5\n", encoding="utf-8")

    assert Settings().sds_max_age_years == 5


def test_get_settings_returns_the_same_object() -> None:
    assert get_settings() is get_settings()
