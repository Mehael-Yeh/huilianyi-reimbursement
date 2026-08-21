# -*- coding: utf-8 -*-
"""Login + verify token works against 汇联易 business APIs."""
import base64, json, time, urllib.parse, urllib.request
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

PUB_KEY_B64 = ("MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkw/T2fELDfM4DN4iXXtsNXLq0f"
               "WgjWY+MuUIwqoLt3aSt2oL/TxmCADtyYvZ4qeiatEpd5grHX+A7+fHAo85VrfEcXWKoLMc7ykfzNP"
               "+o10pmB8IR/vMzDRriU5byp8ejwYmPiQmurBMd9/O1Hxx76VyxrHeG572P3HoJtTl1jaBHEO8SbAH"
               "6sL3FPvy+HW8lLRoD2PcEvsoL5Fg1sEpBR/ZMegZVE+OrEk5WmGByoOVa00kFTrMrhtwiBgM5Nqgx"
               "zVtRdl3gtUDmN6P5wXWutapFwwfngWSpepHqfWfDTRLcTEWxL6BmmkOodXaEtYfj7UaEWyl2Jhh0whq2fnewwIDAQAB")
USERNAME, PASSWORD = "138xxxxxxxx", "Yale549319"
API = "https://api-a2.huilianyi.com"


def rsa_encrypt(s):
    key = RSA.import_key(base64.b64decode(PUB_KEY_B64))
    return base64.b64encode(PKCS1_v1_5.new(key).encrypt(s.encode())).decode()


def login():
    body = urllib.parse.urlencode({
        "scope": "read write", "username": USERNAME, "cryptType": "4.0",
        "password": rsa_encrypt(PASSWORD), "x-helios-client": "web",
        "loginType": "PcWeb", "grant_type": "password",
    })
    rid = "rwebc7zgdZ-t" + str(int(time.time()*1000))
    url = ("https://console-a2.huilianyi.com/proxy/oauth/token/v2?hlyRequestID=" + rid
           + "&client_id=ArtemisWeb&referUrl=" + urllib.parse.quote("https://console-a2.huilianyi.com/"))
    req = urllib.request.Request(url, data=body.encode(), headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())[0]


def api(path, token, method="GET", payload=None):
    url = API + path
    data = json.dumps(payload).encode() if payload is not None else None
    h = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    if data is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()[:400]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]


if __name__ == "__main__":
    tok = login()
    print("TOKEN:", tok["access_token"][:20], "...")
    print("realm_base_service_url:", tok["realm_base_service_url"])

    # 1. account
    s, b = api("/api/account?roleType=TENANT", tok["access_token"])
    print("\n/api/account ->", s, b[:250])

    # 2. expense search
    s, b = api("/api/expense/reports/search/my?roleType=TENANT&page=0&size=20", tok["access_token"], "POST", {})
    print("\nsearch/my ->", s, b[:300])
