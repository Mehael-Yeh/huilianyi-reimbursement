# 建行落账终极源码（发票生成费用→提交入单）— 2026-08-21 用户真实 HAR 破解

## 决定性真相（之前一直找错）
**真正的"生成费用/建行落账" 不是 `custom/form/draft`，而是 `POST /invoice/api/v5/invoices`**。
它直接创建发票行并绑定进报销单（请求体带 expenseReportOID + 费用类型 + 完整识别发票 receiptList → 返回 invoiceOID）。
真实浏览器流程里**没有** custom/form/draft 这条（那是编辑表单整单保存；发票行走 v5/invoices）。

## 端点
- **`POST https://console-a2.huilianyi.com/invoice/api/v5/invoices`**
- URL query：`hlyRequestID=<rand>&roleType=TENANT&isDateCombinedUTC=false&utcTime=true&recalculatePolicy=false&shieldTax=false&distrit=true`（还有更多，非关键）
- auth：`Authorization: Bearer <access_token>`（console-a2 base，同 oauth token）

## 请求体（关键字段，其余为 invoice 对象）
```
expenseReportOID: 58b691d8...   # 目标报销单 OID
ownerOID: 64f5f43a...           # 报销人(示例用户)
expenseTypeId: 1704675864861536258   # 费用类型数值id(其他招待费用)
expenseTypeOID: ed64b608...          # 费用类型OID
expenseTypeName: "其他招待费用"
currencyCode / invoiceCurrencyCode: CNY
amount: 49.0
receiptList: [ <完整富化识别发票> ]   # 关键：份内的 receipt 必须带 数字 id(收据池DB主键)
```

## 响应
`{"success":true,"code":"0000","rows":{"id":"2090770713450651649","invoiceOID":"<新发票OID>",...}}`
→ 发票行创建成功；随后报告自动刷新（GET report/invoices/v2）。

## 纯 API 全链路（每张发票）
1. **upload** `POST /api/upload/attachment`（attachmentType=INVOICE_IMAGES+file）→ attachmentOID
2. **OCR** `POST /receipt/api/receipt/ocr/v3` → rc（id=null）
3. **verify** `POST /receipt/api/receipt/verify/batch` body=`[{"invoiceInfo": rc}]`（**最小参数**，勿加多余字段）→ 响应 list，取 `invoiceInfo` = **真正的富化 receipt**（带 receiptOID + **数字 id** + cardsignType + checkPlatform + invoiceGoods + companyOID）
4. **apportion** `POST /api/expense/default/apportionment` {expenseReportOID, expenseTypeId, amount, currency, ownerOID, merge, paymentCompanyOID}
5. **tax/amount** `POST /invoice/api/invoice/tax/amount/by/receipts`（用 **verify 的 invoiceInfo**，不是原始 OCR rc）→ invoiceOID
6. **v5/invoices** `POST /invoice/api/v5/invoices`（body 见上，receiptList=[verify 的 invoiceInfo]）→ **落账绑定** ✅

## 关键坑（实测踩过）
- **tax/amount 与 v5 都必须用 verify 返回的 invoiceInfo，绝不能用原始 OCR rc**（缺 receiptOID/数字id/富化字段 → 500/400）
- **receipt 的数字 `id`（如 2090769160341794817）来自"查验成功"建收据池记录**。我的 verify 对小杨生煎B 返回 id=null（recessOID 每次有，数字id无）——需发票成功勾稽 NATION 才生成 id
- verify 请求**别加多余参数**（我又加 requireConfirm/isInternationalOCR/v2/checkParams → id 不生成）；真实 body 就是 `[{invoiceInfo}]`
- 复投已绑发票 → 400 业务校验"发票可报销总额不足，费用金额超出X"（E_DUP_INVOICES_RECEIPTS_AMOUNT_01）= 防重复，说明发票已在该报告里
- 报告绑定核实：`GET /api/expense/report/invoices/v2?expenseReportOID=<oid>` → rows.expenseReportInvoices[]

## 登录（API，避开浏览器登录限流）
oauth token：POST /proxy/oauth/token/v2，form 需含 `x-helios-client:web` + `loginType:PcWeb`（缺则 400）。PUB 以 fetch_token.py 为准（RSA-2048 PKCS1 v1.5）。

## 浏览器自动化技巧（本 skill 的测试/验证通道）
- **token 注入绕过登录**：playwright `page.addInitScript((tok)=>{localStorage.setItem('hly.token',JSON.stringify(tok))}, TOK)` → 直达 /main，不再触发网页登录限流
- **非 headless 渲染**：机器有 `/usr/bin/weston`，headless backend 起虚拟 Wayland 显示；chromium 用 `--ozone-platform=wayland` + env `WAYLAND_DISPLAY`，antd 渲染正常
- **视觉定位按钮**：截图后调 qwen 视觉模型（env `QWEN_FREE_API_KEY`，base `https://dashscope.aliyuncs.com/compatible-mode/v1`，model `qwen-vl-max`，image=base64 data-url）→ 让模型给出按钮坐标与画面说明（坐标是估计值，仅作引导；精确坐标仍以 DOM getBoundingClientRect 为准）
- 向导「保存」有**两个**：识别发票文件面板里的向导保存（触发必填校验）与报告底部保存（整单存）——别弄混