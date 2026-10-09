"""Format rules that plain code can check with certainty."""

import re
from datetime import date

_CAS = re.compile(r"^(\d{2,7})-(\d{2})-(\d)$")
_H_CODE = re.compile(r"^H\d{3}$")
_PICTOGRAM = re.compile(r"^GHS0[1-9]$")
SIGNAL_WORDS = ("Danger", "Warning")


def cas_check_digit_ok(cas: str) -> bool:
    """True when a CAS number has the right shape and a correct check digit.

    CAS numbers look like 7732-18-5. Take the digits before the last one, from
    right to left, multiply them by 1, 2, 3 and so on, and add them up. The total
    modulo 10 must equal the last digit. Water: 8x1 + 1x2 + 2x3 + 3x4 + 7x5 + 7x6 = 105, and 105 mod 10 = 5.
    """
    match = _CAS.match(cas.strip())
    if not match:
        return False
    digits = (match.group(1) + match.group(2))[::-1]
    total = sum(int(digit) * position for position, digit in enumerate(digits, start=1))
    return total % 10 == int(match.group(3))


def h_code_ok(code: str) -> bool:
    """GHS hazard statement codes are H plus exactly three digits, for example H315."""
    return bool(_H_CODE.match(code.strip()))


def pictogram_ok(code: str) -> bool:
    """GHS has nine pictograms, GHS01 to GHS09."""
    return bool(_PICTOGRAM.match(code.strip()))


def signal_word_ok(word: str) -> bool:
    return word.strip() in SIGNAL_WORDS


def iso_date_ok(value: str) -> bool:
    """Dates are stored as YYYY-MM-DD and must be real calendar dates."""
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return len(value) == 10
