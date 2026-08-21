# -*- coding: utf-8 -*-
"""Dump full field definitions for the 3 reimbursement forms."""
import base64, json, time, urllib.parse, urllib.request
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

PUB_KEY_B64 = ("MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkw/T2fELDfM4DN4iXXtsNXLq0f"
               "WgjWY+MuUIwqoLt3aSt2oL/TxmCADtyYvZ4qeiatEpd5grHX+A7+fHAo85VrfEcXWKoLMc7ykfzNP"
               "+o10pmB8IR/vMzDRriU5byp8ejwYmPiQmurBMd9/O1Hxx76VyxrHeG572P3HoJtTl1jaBHEO8SbAH"
               "6sL3FPvy+HW8lLRoD2PcEvsoL5Fg1sEpBR/ZMegZVE+OrEk5WmGByoOVa00kFTrMrhtwiBgM5Nqgx"
               "zVtRdl3gtUDmN6P5wXWutapFwwfngWSpepHqfWfDTRLcTEWxL6BmmkOodXaEtYfj7UaEWyl2Jhh0whq2fnewwIDAQAB")
U, P = "138xxxxxxxx", "Yale549319"
API = "https://api-a2.huilianyi.com"
def enc(s): return base64.b64encode(PKCS1_v1_5.new(RSA.import_key(base64.b64decode(PUB_KEY_B64))).encrypt(s.encode())).decode()
def login():
    b = urllib.parse.urlencode({"scope":"read write","username":U,"cryptType":"4.0","password":enc(P),"x-helios-client":"web","loginType":"PcWeb","grant_type":"password"})
    url = "https://console-a2.huilianyi.com/proxy/oauth/token/v2?hlyRequestID=rwebc7zgdZ-p"+str(int(time.time()*1000))+"&client_id=ArtemisWeb&referUrl="+urllib.parse.quote("https://console-a2.huilianyi.com/")
    with urllib.request.urlopen(urllib.request.Request(url,data=b.encode(),headers={"Content-Type":"application/x-www-form-urlencoded"}),timeout=30) as r:
        return json.loads(r.read())[0]
def api(path, tok):
    h = {"Authorization":"Bearer "+tok,"Accept":"application/json"}
    with urllib.request.urlopen(urllib.request.Request(API+path,headers=h),timeout=40) as r:
        return r.status, r.read().decode()

FORMS = {
    "差旅申请单": "OID_1",
    "差旅报销单": "OID_2",
    "个人报销单": "OID_3",
}
if __name__ == "__main__":
    t = login()["access_token"]
    for name, oid in FORMS.items():
        s, b = api(f"/api/custom/forms/field/list?formOID={oid}", t)
        print(f"\n========== {name} ({oid}) ==========")
        try:
            d = json.loads(b)
            for f in d.get("customFormFields", []):
                req = "REQ" if f.get("required") else "opt"
                print(f"  {f.get('sequence'):>3} | {req:>3} | ft={f.get('fieldTypeId'):<4} | {f.get('fieldCode'):<14} | {f.get('fieldName'):<8} | fieldOID={f.get('fieldOID')}")
        except Exception as e:
            print("  parse err", e, b[:200])
