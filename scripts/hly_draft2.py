# -*- coding: utf-8 -*-
"""Attempt to create 差旅申请单 draft via pure API (learn payload contract)."""
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
ZENGLE = "OID_3"
FORM = "OID_4"
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

def field(fieldOID, fieldCode, fieldName, value, ft, req):
    return {"id":None,"fieldOID":fieldOID,"sequence":0,"messageKey":None,"fieldName":fieldName,
            "fieldType":"TEXT" if ft==101 else ("DATE" if ft==103 else "SELECT"),
            "fieldTypeId":ft,"required":req,"promptInfo":None,"fieldCode":fieldCode,
            "value":value,"isRequired":req,"fieldContent":"","formOID":FORM,"hidden":False}

if __name__ == "__main__":
    t = login()["access_token"]
    fields = [
        field("OID_5","field_3917","费用承担公司",COMPANY,101,True),
        field("OID_6","field_0001","费用承担部门","",101,True),
        field("OID_7","DLR","代理人",ZENGLE,101,True),
        field("OID_8","KSRQ","开始日期","2026-05-19",103,True),
        field("OID_9","JSRQ","结束日期","2026-07-19",103,True),
        field("OID_10","field_4963","是否总务订机票","否",106,True),
        field("OID_11","field_2572","单程/往返","往返",106,True),
        field("OID_12","field_8159","交通工具","私车",101,True),
        field("OID_13","field_0004","参与人",YEHAO,101,True),
        field("OID_14","field_1819","事由","客户拜访",101,True),
    ]
    # Try envelope A: customFormValueDTOList directly
    payloadA = {"formOID":FORM,"applicantOID":YEHAO,"customFormValueDTOList":fields}
    # try different date formats for KSRQ
    for fmt, val in [("iso", "2026-05-19T00:00:00.000Z"), ("epochms", "1781712000000"), ("date", "2026-05-19")]:
        for f in fields:
            if f["fieldCode"] in ("KSRQ","JSRQ"):
                f["value"] = val
        s, b = api("/api/travel/applications/draft", t, "POST", payloadA)
        print(f"### date={fmt} -> {s}: {b[:200]}")
        if s == 200:
            print("DRAFT CREATED SUCCESS")
            break
