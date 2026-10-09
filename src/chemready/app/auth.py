"""Accounts: password hashing, sign-in throttling and password reset tokens.

* Passwords are stored only as Argon2 hashes (a slow, salted hash made for passwords).
* Repeated failed sign-ins for one email are slowed down.
* Reset tokens are random, stored only as a hash, work once and expire in 30 minutes.
* "Sign out of all devices" bumps session_version, which ends every old session.
"""

import hashlib
import re
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from chemready.app.store import Row, Store

MIN_PASSWORD_LENGTH = 8
MAX_FAILED_SIGN_INS = 5
LOCK_SECONDS = 15 * 60
RESET_MINUTES = 30
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_hasher = PasswordHasher()


class AuthError(Exception):
    """A sign-in or sign-up problem. The message is safe to show."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def password_matches(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def valid_email(email: str) -> bool:
    return bool(_EMAIL.match(email.strip()))


@dataclass
class SignInThrottle:
    """Counts failed sign-ins per email in memory. Enough for one server; use Redis if you scale out."""

    failures: dict[str, list[float]]
    lock: threading.Lock

    @classmethod
    def create(cls) -> "SignInThrottle":
        return cls(failures={}, lock=threading.Lock())

    def is_locked(self, email: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self.lock:
            recent = [t for t in self.failures.get(email, []) if now - t < LOCK_SECONDS]
            self.failures[email] = recent
            return len(recent) >= MAX_FAILED_SIGN_INS

    def record_failure(self, email: str, now: float | None = None) -> None:
        with self.lock:
            self.failures.setdefault(email, []).append(time.monotonic() if now is None else now)

    def clear(self, email: str) -> None:
        with self.lock:
            self.failures.pop(email, None)


def sign_up(store: Store, *, name: str, email: str, password: str, facility_name: str, max_age: int) -> Row:
    name, email, facility_name = name.strip(), email.strip().lower(), facility_name.strip()
    if not name:
        raise AuthError("Enter your name.")
    if not valid_email(email):
        raise AuthError("Enter a valid email address, for example name@factory.com.")
    if not facility_name:
        raise AuthError("Enter your facility name.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    if store.user_by_email(email):
        raise AuthError("An account with this email already exists. Sign in instead.")
    facility_id = store.create_facility(facility_name, max_age)
    user_id = store.create_user(facility_id, name, email, hash_password(password))
    user = store.user(user_id)
    assert user is not None  # noqa: S101 - just inserted
    return user


def sign_in(store: Store, throttle: SignInThrottle, *, email: str, password: str) -> Row:
    email = email.strip().lower()
    if throttle.is_locked(email):
        raise AuthError("Too many attempts. Wait 15 minutes, or reset your password.")
    user = store.user_by_email(email)
    if user is None or not password_matches(user["password_hash"], password):
        throttle.record_failure(email)
        raise AuthError("That email and password do not match.")
    throttle.clear(email)
    return user


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_password_reset(store: Store, email: str) -> str | None:
    """Return a reset token to send by email, or None if there is no such account.

    The caller must show the same message either way, so nobody can find out who has an account.
    """
    user = store.user_by_email(email.strip())
    if user is None:
        return None
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(UTC) + timedelta(minutes=RESET_MINUTES)).isoformat()
    store.run(
        "INSERT INTO password_reset (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
        user["id"],
        _token_hash(token),
        expires,
    )
    return token


def finish_password_reset(store: Store, token: str, new_password: str) -> None:
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    reset = store.one("SELECT * FROM password_reset WHERE token_hash = ?", _token_hash(token))
    if reset is None or reset["used_at"] or datetime.fromisoformat(reset["expires_at"]) < datetime.now(UTC):
        raise AuthError("This reset link is invalid or has expired. Ask for a new one.")
    with store.transaction() as db:
        db.execute("UPDATE password_reset SET used_at = datetime('now') WHERE id = ?", (reset["id"],))
        db.execute(
            "UPDATE app_user SET password_hash = ?, session_version = session_version + 1 WHERE id = ?",
            (hash_password(new_password), reset["user_id"]),
        )


def change_password(store: Store, user: Row, current: str, new_password: str) -> None:
    if not password_matches(user["password_hash"], current):
        raise AuthError("Your current password is not right.")
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Use at least {MIN_PASSWORD_LENGTH} characters.")
    store.run(
        "UPDATE app_user SET password_hash = ?, session_version = session_version + 1 WHERE id = ?",
        hash_password(new_password),
        user["id"],
    )


def sign_out_everywhere(store: Store, user_id: int) -> None:
    store.run("UPDATE app_user SET session_version = session_version + 1 WHERE id = ?", user_id)
