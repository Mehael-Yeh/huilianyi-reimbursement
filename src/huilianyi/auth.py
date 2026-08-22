"""Huilianyi OAuth authentication without persistence or secret logging."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

from .exceptions import ErrorCode, HuilianyiError


PUBLIC_KEY_B64 = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkw/T2fELDfM4DN4iXXtsNXLq0f"
    "WgjWY+MuUIwqoLt3aSt2oL/TxmCADtyYvZ4qeiatEpd5grHX+A7+fHAo85VrfEcXWKoLMc7ykfzNP"
    "+o10pmB8IR/vMzDRriU5byp8ejwYmPiQmurBMd9/O1Hxx76VyxrHeG572P3HoJtTl1jaBHEO8SbAH"
    "6sL3FPvy+HW8lLRoD2PcEvsoL5Fg1sEpBR/ZMegZVE+OrEk5WmGByoOVa00kFTrMrhtwiBgM5Nqgx"
    "zVtRdl3gtUDmN6P5wXWutapFwwfngWSpepHqfWfDTRLcTEWxL6BmmkOodXaEtYfj7UaEWyl2Jhh0whq2fnewwIDAQAB"
)


@dataclass(frozen=True)
class AuthSession:
    access_token: str
    api_base_url: str
    raw: dict[str, Any]

    @classmethod
    def from_response(cls, value: dict[str, Any]) -> "AuthSession":
        token = str(value.get("access_token") or "")
        if not token:
            raise HuilianyiError(ErrorCode.AUTH_FAILED, "login response did not contain an access token")
        return cls(
            access_token=token,
            api_base_url=str(value.get("realm_base_service_url") or "https://api-a2.huilianyi.com"),
            raw=value,
        )


def _rsa_encrypt(value: str) -> str:
    key = serialization.load_der_public_key(base64.b64decode(PUBLIC_KEY_B64))
    encrypted = key.encrypt(value.encode("utf-8"), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode("ascii")


def login(
    username: str,
    password: str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
    timeout: float = 30,
) -> dict[str, Any]:
    if not username.strip() or not password:
        raise HuilianyiError(ErrorCode.AUTH_REQUIRED, "Huilianyi account and password are required")
    form = urllib.parse.urlencode({
        "scope": "read write",
        "username": username.strip(),
        "cryptType": "4.0",
        "password": _rsa_encrypt(password),
        "x-helios-client": "web",
        "loginType": "PcWeb",
        "grant_type": "password",
    }).encode("utf-8")
    url = (
        "https://console-a2.huilianyi.com/proxy/oauth/token/v2"
        f"?hlyRequestID=sdk-{int(time.time() * 1000)}&client_id=ArtemisWeb&referUrl="
        + urllib.parse.quote("https://console-a2.huilianyi.com/")
    )
    request = urllib.request.Request(
        url,
        data=form,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with opener(request, timeout=timeout) as response:
            decoded = json.loads(response.read().decode("utf-8"))
            value = decoded[0] if isinstance(decoded, list) and decoded else decoded
            AuthSession.from_response(value)
            return value
    except urllib.error.HTTPError as exc:
        raise HuilianyiError(
            ErrorCode.AUTH_FAILED,
            "Huilianyi rejected the supplied credentials",
            method="POST",
            path="/proxy/oauth/token/v2",
            status=exc.code,
        ) from exc
    except HuilianyiError:
        raise
    except Exception as exc:
        raise HuilianyiError(ErrorCode.NETWORK_ERROR, "could not reach Huilianyi authentication service") from exc
