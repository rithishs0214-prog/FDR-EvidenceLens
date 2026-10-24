"""Framework-free authentication helpers: password hashing, session tokens, login throttling.
Only the Python standard library is used."""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import threading
import time
from typing import Callable, Optional

PBKDF2_ITERATIONS = 600_000  # OWASP guidance for PBKDF2-HMAC-SHA256
_USERNAME_RE = re.compile(r"[a-z0-9._-]{3,50}")
_COMMON = {"password", "password1", "password123", "1234567890", "12345678910", "qwertyuiop", "letmein123",
           "admin12345", "welcome123", "iloveyou12", "changeme123"}


def normalize_username(raw: Optional[str]) -> Optional[str]:
    u = (raw or "").strip().lower()
    return u if _USERNAME_RE.fullmatch(u) else None


def validate_password(password: str, username: str = "") -> Optional[str]:
    """Return an error message, or None if the password is acceptable."""
    if len(password) < 10:
        return "The password must be at least 10 characters long."
    if len(password) > 128:
        return "The password must be at most 128 characters long."
    if password.lower() in _COMMON or len(set(password)) < 4:
        return "That password is too easy to guess. Choose a less predictable one."
    if username and username.lower() in password.lower():
        return "The password must not contain the username."
    return None


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, dk_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iters)
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(dk_b64)
    except (ValueError, TypeError):
        return False
    calc = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(calc, expected)


_dummy: Optional[str] = None


def dummy_hash() -> str:
    """A hash nobody knows the password of; verified against for unknown usernames so that the
    response time does not reveal whether an account exists."""
    global _dummy
    if _dummy is None:
        _dummy = hash_password(secrets.token_urlsafe(16))
    return _dummy


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Only this hash is stored, so a leaked database does not leak usable session tokens."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class LoginLimiter:
    """In-memory throttle: after `max_failures` failures within `window_seconds` the key is locked
    until the oldest failure ages out. Resets on restart (acceptable for a single-process prototype)."""

    def __init__(self, max_failures: int = 5, window_seconds: int = 900, clock: Callable[[], float] = time.monotonic):
        self.max_failures, self.window, self._clock = max_failures, window_seconds, clock
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> list[float]:
        fresh = [t for t in self._fails.get(key, []) if now - t < self.window]
        if fresh:
            self._fails[key] = fresh
        else:
            self._fails.pop(key, None)
        return fresh

    def is_locked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, self._clock())) >= self.max_failures

    def retry_after(self, key: str) -> int:
        with self._lock:
            now = self._clock()
            fresh = self._prune(key, now)
            return max(1, int(fresh[0] + self.window - now) + 1) if fresh else 0

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            if len(self._fails) > 10_000:
                for k in list(self._fails):
                    self._prune(k, now)
            self._fails.setdefault(key, []).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._fails.pop(key, None)
