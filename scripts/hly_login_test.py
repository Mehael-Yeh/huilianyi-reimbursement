# -*- coding: utf-8 -*-
"""Test 汇联易 pure-API login: RSA-encrypt password -> OAuth2 password grant -> token."""
import base64
import json
import urllib.parse
import urllib.request
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

PUB_KEY_B64 = ("MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkw/T2fELDfM4DN4iXXtsNXLq0f"
               "WgjWY+MuUIwqoLt3aSt2oL/TxmCADtyYvZ4qeiatEpd5grHX+A7+fHAo85VrfEcXWKoLMc7ykfzNP"
               "+o10pmB8IR/vMzDRriU5byp8ejwYmPiQmurBMd9/O1Hxx76VyxrHeG572P3HoJtTl1jaBHEO8SbAH"
               "6sL3FPvy+HW8lLRoD2PcEvsoL5Fg1sEpBR/ZMegZVE+OrEk5WmGByoOVa00kFTrMrhtwiBgM5Nqgx"
               "zVtRdl3gtUDmN6P5wXWutapFwwfngWSpepHqfWfDTRLcTEWxL6BmmkOodXaEtYfj7UaEWyl2Jhh0whq2fnewwIDAQAB")
USERNAME = "138xxxxxxxx"
PASSWORD = "Yale549319"


def rsa_encrypt(plain: str) -> str:
    key = RSA.import_key(base64.b64decode(PUB_KEY_B64))
    cipher = PKCS1_v1_5.new(key)
    enc = cipher.encrypt(plain.encode("utf-8"))
    return base64.b64encode(enc).decode("ascii")


def login():
    enc_pwd = rsa_encrypt(PASSWORD)
    print("encrypted password (head):", enc_pwd[:40], "... len", len(enc_pwd))

    params = {
        "scope": "read write",
        "username": USERNAME,
        "cryptType": "4.0",
        "password": enc_pwd,
        "x-helios-client": "web",
        "loginType": "PcWeb",
        "grant_type": "password",
    }
    body = urllib.parse.urlencode(params)
    import time
    ts = str(int(time.time() * 1000))
    rid = "rwebc7zgdZ-test" + ts
    url = ("https://console-a2.huilianyi.com/proxy/oauth/token/v2"
           "?hlyRequestID=" + rid + "&client_id=ArtemisWeb&referUrl="
           + urllib.parse.quote("https://console-a2.huilianyi.com/"))

    req = urllib.request.Request(url, data=body.encode("utf-8"),
                                 headers={"Content-Type": "application/x-www-form-urlencoded",
                                          "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            txt = resp.read().decode("utf-8")
            print("HTTP", resp.status)
            print("body:", txt[:500])
            return txt
    except urllib.error.HTTPError as e:
        print("HTTPError", e.code)
        print(e.read().decode("utf-8", "ignore")[:500])
        return None
    except Exception as e:
        print("ERR", type(e).__name__, e)
        return None


if __name__ == "__main__":
    login()
