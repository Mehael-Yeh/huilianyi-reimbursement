"""Stable, sanitized error model shared by the SDK and MCP server."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    AUTH_FAILED = "AUTH_FAILED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    API_ERROR = "API_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNSAFE_OPERATION = "UNSAFE_OPERATION"


_SENSITIVE_KEYS = {
    "access_token", "refresh_token", "authorization", "cookie", "password",
    "token", "tokenvalue", "clientsecret", "set-cookie", "signedurl", "downloadurl", "fileurl", "pdfurl",
}


def sanitize(value: Any) -> Any:
    """Redact credentials and signed URLs before an error crosses the SDK boundary."""
    if isinstance(value, dict):
        return {
            key: "<redacted>" if key.lower().replace("_", "") in {
                item.replace("_", "") for item in _SENSITIVE_KEYS
            } else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


class HuilianyiError(RuntimeError):
    def __init__(
        self,
        code: ErrorCode | str,
        message: str,
        *legacy: Any,
        method: str | None = None,
        path: str | None = None,
        status: int | None = None,
        details: Any = None,
    ):
        if legacy:
            # Compatibility with the former HLYError(method, path, status, body).
            method, path = str(code), message
            status = int(legacy[0])
            details = legacy[1] if len(legacy) > 1 else None
            code = error_code_for_status(status)
            message = "Huilianyi API request failed"
        self.code = ErrorCode(code)
        self.method = method
        self.path = path
        self.status = status
        self.details = sanitize(details)
        self.body = self.details
        context = " ".join(part for part in (method, path) if part)
        suffix = f" ({context})" if context else ""
        super().__init__(f"{self.code.value}: {message}{suffix}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": {
                "code": self.code.value,
                "message": str(self).split(": ", 1)[-1],
                "status": self.status,
                "details": self.details,
            },
        }


def error_code_for_status(status: int) -> ErrorCode:
    if status == 401:
        return ErrorCode.AUTH_EXPIRED
    if status == 403:
        return ErrorCode.PERMISSION_DENIED
    if status == 404:
        return ErrorCode.NOT_FOUND
    if status == 429:
        return ErrorCode.RATE_LIMITED
    if status in (400, 409, 422):
        return ErrorCode.VALIDATION_ERROR
    return ErrorCode.API_ERROR
