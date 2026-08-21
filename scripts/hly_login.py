#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汇联易纯 API 登录：RSA-2048 加密密码 -> OAuth2 密码模式 -> access_token。
依赖: pycryptodome。用法: python hly_login.py [账号] [密码]
输出 access_token / refresh_token / api base。
"""
import base64
import json
import sys
import time
import urllib.parse
import urllib.request

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

PUB_KEY_B64 = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkw/T2fELDfM4DN4iXXtsNXLq0f"
    "WgjWY+MuUIwqoLt3aSt2oL/TxmCADtyYvZ4qeiatEpd5grHX+A7+fHAo85VrfEcXWKoLMc7ykfzNP"
    "+o10pmB8IR/vMzDRriU5byp8ejwYmPiQmurBMd9/O1Hxx76VyxrHeG572P3HoJtTl1jaBHEO8SbAH"
    "6sL3FPvy+HW8lLRoD2PcEvsoL5Fg1sEpBR/ZMegZVE+OrEk5WmGByoOVa00kFTrMrhtwiBgM5Nqgx"
    "zVtRdl3gtUDmN6P5wXWutapFwwfngWSpepHqfWfDTRLcTEWxL6BmmkOodXaEtYfj7UaEWyl2Jhh0whq2fnewwIDAQAB"
)
DEFAULT_USER = "138xxxxxxxx"


def rsa_encrypt(plain: str) -> str:
    key = RSA.import_key(base64.b64decode(PUB_KEY_B64))
    enc = PKCS1_v1_5.new(key).encrypt(plain.encode("utf-8"))
    return base64.b64encode(enc).decode("ascii")


def login(username: str, password: str) -> dict:
    params = {
        "scope": "read write",
        "username": username,
        "cryptType": "4.0",
        "password": rsa_encrypt(password),
        "x-helios-client": "web",
        "loginType": "PcWeb",
        "grant_type": "password",
    }
    body = urllib.parse.urlencode(params)
    rid = "rwebc7zgdZ-" + str(int(time.time() * 1000))
    url = (
        "https://console-a2.huilianyi.com/proxy/oauth/token/v2"
        "?hlyRequestID=" + rid + "&client_id=ArtemisWeb&referUrl="
        + urllib.parse.quote("https://console-a2.huilianyi.com/")
    )
    req = urllib.request.Request(
        url, data=body.encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))[0]


if __name__ == "__main__":
    user = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_USER
    pwd = sys.argv[2] if len(sys.argv) > 2 else None
    if pwd is None:
        pwd = input("password: ")
    info = login(user, pwd)
    print(json.dumps({
        "access_token": info["access_token"],
        "refresh_token": info["refresh_token"],
        "api_base": info.get("realm_base_service_url", "https://api-a2.huilianyi.com"),
        "realm_id": info.get("realm_id"),
    }, ensure_ascii=False, indent=2))
