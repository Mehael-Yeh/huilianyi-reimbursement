# -*- coding: utf-8 -*-
"""Resolve refs + first attempt to create 差旅申请单 draft via pure API."""
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
COMPANY = "OID_1"
YEHAO = "OID_2"
def enc(s): return base64.b64encode(PKCS1_v1_5.new(RSA.import_key(base64.b64decode(PUB_KEY_B64))).encrypt(s.encode())).decode()
def login():
    b = urllib.parse.urlencode({"scope":"read write","username":U,"cryptType":"4.0","password":enc(P),"x-helios-client":"web","loginType":"PcWeb","grant_type":"password"})
    url = "https://console-a2.huilianyi.com/proxy/oauth/token/v2?hlyRequestID=rwebc7zgdZ-p"+str(int(time.time()*1000))+"&client_id=ArtemisWeb&referUrl="+urllib.parse.quote("https://console-a2.huilianyi.com/")
    with urllib.request.urlopen(urllib.request.Request(url,data=b.encode(),headers={"Content-Type":"application/x-www-form-urlencoded"}),timeout=30) as r:
        return json.loads(r.read())[0]
def api(path, tok, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    h = {"Authorization":"Bearer "+tok,"Accept":"application/json"}
    if data is not None: h["Content-Type"]="application/json"
    try:
        with urllib.request.urlopen(urllib.request.Request(API+path,data=data,headers=h,method=method),timeout=40) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e: return e.code, e.read().decode()
    except Exception as e: return 0, f"ERR {e}"

if __name__ == "__main__":
    t = login()["access_token"]
    # resolve agent 审批人甲 userOID
    s, b = api("/api/users/v3/search?roleType=TENANT&size=10&page=0&keyword="+urllib.parse.quote("审批人甲"), t)
    zengle = json.loads(b)
    zengle_oid = zengle[0].get("userOID") if zengle else None
    print("审批人甲 userOID:", zengle_oid, "| dept:", (zengle[0].get("departmentOID") if zengle else None), "| fullName:", (zengle[0].get("fullName") if zengle else None))

    # 费用承担部门 - resolve 树脂销售 dept/cost-center. Try department opt tenant (find path containing 树脂销售)
    s, b = api("/api/department/opt/tenant?roleType=TENANT", t)
    print("\n### department/opt/tenant ->", s, b[:600])
