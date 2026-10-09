"""Unit tests for the plain-code format rules."""

import pytest

from chemready.validation.rules import (
    cas_check_digit_ok,
    h_code_ok,
    iso_date_ok,
    pictogram_ok,
    signal_word_ok,
)


@pytest.mark.parametrize("cas", ["7732-18-5", "1310-73-2", "64-19-7", "67-63-0", "7647-14-5", " 7732-18-5 "])
def test_valid_cas_numbers_pass(cas: str) -> None:
    assert cas_check_digit_ok(cas)


@pytest.mark.parametrize(
    "cas", ["7732-18-6", "1310-73-3", "7732185", "7732-18", "77-32-18-5", "abc-de-f", ""]
)
def test_invalid_cas_numbers_fail(cas: str) -> None:
    assert not cas_check_digit_ok(cas)


@pytest.mark.parametrize(
    ("code", "ok"), [("H315", True), ("H3l9", False), ("H31", False), ("EUH031", False), ("h315", False)]
)
def test_h_code_format(code: str, ok: bool) -> None:
    assert h_code_ok(code) is ok


@pytest.mark.parametrize(
    ("code", "ok"), [("GHS01", True), ("GHS09", True), ("GHS10", False), ("GHS00", False)]
)
def test_pictogram_format(code: str, ok: bool) -> None:
    assert pictogram_ok(code) is ok


@pytest.mark.parametrize(("word", "ok"), [("Danger", True), ("Warning", True), ("Caution", False)])
def test_signal_word(word: str, ok: bool) -> None:
    assert signal_word_ok(word) is ok


@pytest.mark.parametrize(
    ("value", "ok"), [("2025-03-01", True), ("2025-02-30", False), ("01.03.2025", False)]
)
def test_iso_date(value: str, ok: bool) -> None:
    assert iso_date_ok(value) is ok
