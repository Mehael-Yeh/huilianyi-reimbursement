#!/usr/bin/env python3
"""Small cross-platform client for the Huilianyi A2 APIs.

Credentials are accepted by callers and are never persisted or printed.
Only generic HTTP primitives live here; workflow safety is enforced by
``hly_workflow.py``.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding


PUBLIC_KEY_B64 = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkw/T2fELDfM4DN4iXXtsNXLq0f"
    "WgjWY+MuUIwqoLt3aSt2oL/TxmCADtyYvZ4qeiatEpd5grHX+A7+fHAo85VrfEcXWKoLMc7ykfzNP"
    "+o10pmB8IR/vMzDRriU5byp8ejwYmPiQmurBMd9/O1Hxx76VyxrHeG572P3HoJtTl1jaBHEO8SbAH"
    "6sL3FPvy+HW8lLRoD2PcEvsoL5Fg1sEpBR/ZMegZVE+OrEk5WmGByoOVa00kFTrMrhtwiBgM5Nqgx"
    "zVtRdl3gtUDmN6P5wXWutapFwwfngWSpepHqfWfDTRLcTEWxL6BmmkOodXaEtYfj7UaEWyl2Jhh0whq2fnewwIDAQAB"
)


class HLYError(RuntimeError):
    def __init__(self, method: str, path: str, status: int, body: Any):
        self.method = method
        self.path = path
        self.status = status
        self.body = body
        preview = json.dumps(body, ensure_ascii=False)[:1000]
        super().__init__(f"{method} {path} -> HTTP {status}: {preview}")


def _rsa_encrypt(value: str) -> str:
    key = serialization.load_der_public_key(base64.b64decode(PUBLIC_KEY_B64))
    encrypted = key.encrypt(value.encode("utf-8"), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode("ascii")


def login(username: str, password: str) -> dict[str, Any]:
    """Return the OAuth response without logging or persisting secrets."""
    form = urllib.parse.urlencode(
        {
            "scope": "read write",
            "username": username,
            "cryptType": "4.0",
            "password": _rsa_encrypt(password),
            "x-helios-client": "web",
            "loginType": "PcWeb",
            "grant_type": "password",
        }
    ).encode("utf-8")
    request_id = f"agent-{int(time.time() * 1000)}"
    url = (
        "https://console-a2.huilianyi.com/proxy/oauth/token/v2"
        f"?hlyRequestID={request_id}&client_id=ArtemisWeb&referUrl="
        + urllib.parse.quote("https://console-a2.huilianyi.com/")
    )
    request = urllib.request.Request(
        url,
        data=form,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))[0]


def unwrap_row(value: Any) -> Any:
    if isinstance(value, dict) and isinstance(value.get("rows"), dict):
        return value["rows"]
    return value


def unwrap_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return value
    if not isinstance(value, dict):
        return []
    for key in ("rows", "content", "data", "list"):
        candidate = value.get(key)
        if isinstance(candidate, list):
            return candidate
        if isinstance(candidate, dict):
            nested = unwrap_rows(candidate)
            if nested:
                return nested
    return []


class Client:
    def __init__(self, token: str, base_url: str):
        self.token = token
        self.base_url = base_url.rstrip("/")

    def request(self, path: str, method: str = "GET", payload: Any = None) -> Any:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8")
                value = json.loads(raw) if raw else None
                if not 200 <= response.status < 300:
                    raise HLYError(method, path, response.status, value)
                return value
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                value = raw
            raise HLYError(method, path, exc.code, value) from exc

    def upload_invoice(self, file_path: str | Path) -> dict[str, Any]:
        path = Path(file_path)
        boundary = "----HLYAgent" + uuid.uuid4().hex
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = b"".join(
            [
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"attachmentType\"\r\n\r\nINVOICE_IMAGES\r\n".encode(),
                (
                    f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
                    f"Content-Type: {mime}\r\n\r\n"
                ).encode("utf-8"),
                path.read_bytes(),
                b"\r\n",
                f"--{boundary}--\r\n".encode(),
            ]
        )
        request = urllib.request.Request(
            self.base_url + "/api/upload/attachment",
            data=body,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                value = json.loads(response.read().decode("utf-8"))
                return unwrap_row(value)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                value = raw
            raise HLYError("POST", "/api/upload/attachment", exc.code, value) from exc


def clients_from_auth(auth: dict[str, Any]) -> tuple[Client, Client]:
    token = auth["access_token"]
    api = Client(token, auth.get("realm_base_service_url", "https://api-a2.huilianyi.com"))
    gateway = Client(token, "https://console-a2.huilianyi.com")
    return api, gateway
