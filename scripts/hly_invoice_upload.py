# -*- coding: utf-8 -*-
"""Upload real invoice PDFs via pure API, capture attachmentOIDs, then OCR."""
import base64, json, time, urllib.parse, urllib.request, uuid, os, glob
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
PUB_KEY_B64=("MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkw/T2fELDfM4DN4iXXtsNXLq0fWgjWY+MuUIwqoLt3aSt2oL/TxmCADtyYvZ4qeiatEpd5grHX+A7+fHAo85VrfEcXWKoLMc7ykfzNP+o10pmB8IR/vMzDRriU5byp8ejwYmPiQmurBMd9/O1Hxx76VyxrHeG572P3HoJtTl1jaBHEO8SbAH6sL3FPvy+HW8lLRoD2PcEvsoL5Fg1sEpBR/ZMegZVE+OrEk5WmGByoOVa00kFTrMrhtwiBgM5NqgxzVtRdl3gtUDmN6P5wXWutapFwwfngWSpepHqfWfDTRLcTEWxL6BmmkOodXaEtYfj7UaEWyl2Jhh0whq2fnewwIDAQAB")
U,P="138xxxxxxxx","Yale549319"; API="https://api-a2.huilianyi.com"
def enc(s): return base64.b64encode(PKCS1_v1_5.new(RSA.import_key(base64.b64decode(PUB_KEY_B64))).encrypt(s.encode())).decode()
def login():
    b=urllib.parse.urlencode({"scope":"read write","username":U,"cryptType":"4.0","password":enc(P),"x-helios-client":"web","loginType":"PcWeb","grant_type":"password"})
    url="https://console-a2.huilianyi.com/proxy/oauth/token/v2?hlyRequestID=rwebc7zgdZ-p"+str(int(time.time()*1000))+"&client_id=ArtemisWeb&referUrl="+urllib.parse.quote("https://console-a2.huilianyi.com/")
    with urllib.request.urlopen(urllib.request.Request(url,data=b.encode(),headers={"Content-Type":"application/x-www-form-urlencoded"}),timeout=30) as r: return json.loads(r.read())[0]
def multipart(filepath):
    boundary="----WebKitFormBoundary"+uuid.uuid4().hex
    fn=os.path.basename(filepath)
    with open(filepath,'rb') as f: fdata=f.read()
    parts=[]
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"attachmentType\"\r\n\r\nINVOICE_IMAGES\r\n".encode())
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{fn}\"\r\nContent-Type: application/pdf\r\n\r\n".encode()+fdata+b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), boundary, fn
t=login()["access_token"]
clean='/vol1/@appdata/trim.hermes/workspace/hly_invoices/clean'
results={}
for fp in sorted(glob.glob(clean+'/*.pdf')):
    body,bd,fn=multipart(fp)
    try:
        with urllib.request.urlopen(urllib.request.Request(API+"/api/upload/attachment",data=body,headers={"Authorization":"Bearer "+t,"Content-Type":f"multipart/form-data; boundary={bd}","Accept":"application/json"}),timeout=60) as r:
            resp=json.loads(r.read())
        oid=resp.get('attachmentOID'); 
        results[fp]=resp
        print(f"OK  {fn}  -> attachmentOID={oid} id={resp.get('id')}")
    except urllib.error.HTTPError as e:
        results[fp]={"err":e.code,"body":e.read().decode()[:200]}
        print(f"ERR {fn} -> {e.code}")
json.dump(results, open('/tmp/hly_js/upload_results.json','w'), ensure_ascii=False, indent=1)
print("\nattachmentOIDs:")
for fp,r in results.items():
    print(f"  {os.path.basename(fp)}: {r.get('attachmentOID')}")
