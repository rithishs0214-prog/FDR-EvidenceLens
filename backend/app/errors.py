from __future__ import annotations

from typing import Any, Optional


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.status_code, self.code, self.message, self.details = status_code, code, message, details


def not_found(what: str) -> ApiError:
    return ApiError(404, "not_found", f"{what} was not found.")
