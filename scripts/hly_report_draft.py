# -*- coding: utf-8 -*-
"""Create 个人报销单 draft — body = full entity, custFormValues as ARRAY of full objects."""
import base64, json, time, urllib.parse, urllib.request
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
PUB_KEY_B64=("MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkw/T2fELDfM4DN4iXXtsNXLq0fWgjWY+MuUIwqoLt3aSt2oL/TxmCADtyYvZ4qeiatEpd5grHX+A7+fHAo85VrfEcXWKoLMc7ykfzNP+o10pmB8IR/vMzDRriU5byp8ejwYmPiQmurBMd9/O1Hxx76VyxrHeG572P3HoJtTl1jaBHEO8SbAH6sL3FPvy+HW8lLRoD2PcEvsoL5Fg1sEpBR/ZMegZVE+OrEk5WmGByoOVa00kFTrMrhtwiBgM5NqgxzVtRdl3gtUDmN6P5wXWutapFwwfngWSpepHqfWfDTRLcTEWxL6BmmkOodXaEtYfj7UaEWyl2Jhh0whq2fnewwIDAQAB")
U,P="138xxxxxxxx","Yale549319"; API="https://api-a2.huilianyi.com"
def enc(s): return base64.b64encode(PKCS1_v1_5.new(RSA.import_key(base64.b64decode(PUB_KEY_B64))).encrypt(s.encode())).decode()
def login():
    b=urllib.parse.urlencode({"scope":"read write","username":U,"cryptType":"4.0","password":enc(P),"x-helios-client":"web","loginType":"PcWeb","grant_type":"password"})
    url="https://console-a2.huilianyi.com/proxy/oauth/token/v2?hlyRequestID=rwebc7zgdZ-p"+str(int(time.time()*1000))+"&client_id=ArtemisWeb&referUrl="+urllib.parse.quote("https://console-a2.huilianyi.com/")
    with urllib.request.urlopen(urllib.request.Request(url,data=b.encode(),headers={"Content-Type":"application/x-www-form-urlencoded"}),timeout=30) as r: return json.loads(r.read())[0]
def api(path,tok,pl):
    try:
        with urllib.request.urlopen(urllib.request.Request(API+path,data=json.dumps(pl,ensure_ascii=False).encode(),headers={"Authorization":"Bearer "+tok,"Content-Type":"application/json","Accept":"application/json"}),timeout=40) as r: return r.status,r.read().decode()
    except urllib.error.HTTPError as e: return e.code,e.read().decode()
t=login()["access_token"]
# Base = full saved row (report entity shape). custFormValues = ARRAY. Null out server-assigned ids for a NEW draft.
row=json.loads(open('/tmp/hly_js/saved_ERxxxxxx.json').read())['rows']
# adjust field values to a fresh 客户拜访 personal report
cf=row['custFormValues']
for f in cf:
    f['id']=None; f['formValueOID']=None; f['bizOID']=None; f['createdDate']=None; f['lastModifiedDate']=None
    mk=f.get('messageKey')
    if mk=='title':
        f['value']="客户拜访"; f['name']="客户拜访"; f['showValue']="客户拜访"
    if mk=='select_cost_center': f['value']=None; f['name']=None; f['showValue']=""
row['custFormValues']=cf  # ARRAY, not string
row['title']="客户拜访"
# null server-assigned ids for new draft (keep structure)
for k in ['expenseReportOID','entityOID','applicationOID','businessCode','id','expenseReportId','applicationId',
          'createdBy','createdName','createdDate','lastModifiedBy','lastModifiedDate']:
    if k in row: row[k]=None
row['expenseReportDetailDTOList']=[]
row['expenseReportApplicationDTOS']=[]
row['expenseReportInvoices']=[]
row['expenseReportLabels']=[]
row['recalculateSubsidy']=False
row['isDateCombinedUTC']=False
row['showValidatePopUp']=True
for ep in ["/api/expense/reports/custom/form/draft","/api/expense/reports/custom/form/draft?corporateFlag=false"]:
    s,b=api(ep,t,row)
    print(f"### {ep} -> {s}: {b[:300]}")
    if 200<=s<300:
        print("  >>> SUCCESS"); open('/tmp/hly_js/created_personal.json','w').write(b); break
