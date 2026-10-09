"""Tests for the `chemready` command."""

import pytest

from chemready import __version__
from chemready.__main__ import main


def test_prints_version_and_safe_summary(capsys: pytest.CaptureFixture[str]) -> None:
    main()

    output = capsys.readouterr().out
    assert f"ChemReady {__version__}" in output
    assert "Model provider:        ollama" in output
    assert "Private files allowed: yes" in output


def test_never_prints_the_api_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CHEMREADY_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("CHEMREADY_GEMINI_API_KEY", "super-secret-value")
    monkeypatch.setenv("CHEMREADY_GEMINI_MODEL", "test-model")

    main()

    output = capsys.readouterr().out
    assert "super-secret-value" not in output
    assert "Private files allowed: no (public SDS only)" in output


def test_invalid_settings_exit_with_a_clear_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CHEMREADY_LLM_PROVIDER", "gemini")

    with pytest.raises(SystemExit) as exit_info:
        main()

    assert exit_info.value.code == 1
    assert "Settings are not valid" in capsys.readouterr().out
