"""Shared test setup: every test starts with a clean environment."""

import os
from collections.abc import Iterator

import pytest

from chemready.config import get_settings


@pytest.fixture(autouse=True)
def clean_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[None]:
    """Remove CHEMREADY_ variables and run from an empty folder, so a developer's .env never leaks in."""
    for name in list(os.environ):
        if name.startswith("CHEMREADY_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
