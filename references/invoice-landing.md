# 纯API发票落账·完整序列（2026-08-21 实测全200通过）
> 目标：任意发票以任意类别落进任意报销单。所有POST基址 console-a2.huilianyi.com，带 `Authorization: Bearer <token>`。
> 实测落账： 小杨生煎B(49) → invoiceOID **2a43d9b4** → ERxxxxx(58b691d8)，3496 现3张(139+134+49=322)。

## 序列（每步都写文件，下一步引用）
```text
1. POST /api/upload/attachment  multipart/form-data
      fields: attachmentType=INVOICE_IMAGES, file=<PDF bytes>
      resp.rows: {attachmentOID, fileURL(OSS签名URL,1h), attachmentContentType}
2. POST /receipt/api/receipt/ocr/v3?hlyRequestID=&roleType=TENANT&client=WEB&isInternationalOCR=false&reportOID=<报销单OID>
      json body: [{"oriAttachment":<upload.rows>, "attachmentType":"INVOICE_IMAGES","autoCountSent":"TRUE"}]
      resp.rows.receiptList[0] = 原始识别rc; 需补 rc["pdfUrl"]=upload.fileURL
3. POST /receipt/api/receipt/verify/batch?roleType=TENANT
      json body: [{"invoiceInfo": rc(带pdfUrl)}]
      resp[0].invoiceInfo = 富化receipt（含 receiptOID, R_0000查验成功, beginTime/endTime）★关键：id=None即可
4. POST /invoice/api/invoice/defaults?roleType=TENANT   body: ← 携带 receiptList=[富化receipt]
5. POST /invoice/api/receipt/cal/total_amount?roleType=TENANT  body ↑
6. POST /invoice/api/invoice/tax/amount/by/receipts?roleType=TENANT  body ↑ → resp.rows.invoiceOID,  expenseTypeId
7. POST /invoice/api/v5/invoices?hlyRequestID=&roleType=TENANT&isDateCombinedUTC=false&utcTime=true&recalculatePolicy=false&shieldTax=false&distrit=true
      body: {expenseReportOID, expenseTypeName/Id/OID, ownerOID, amount:<发票实付金额>, currencyCode:"CNY", receiptList:[富化receipt], attachments:[], data:<invoice data>}
      ★★ v5["amount"] 必须=发票实付金额(如49)，否则400"费用金额超出发票本次报销金额之和"
      resp.rows.invoiceOID → 落账成功，该票绑定报销单
```

## 要点
- 费用类别三件套：`expenseTypeName`/`expenseTypeId`(数字)/`expenseTypeOID`，见 references/expense-types.md（差旅/个人各自清单）
- 删除：`DELETE /api/expense/reports/delete/invoice/{报销单OID}/{invoiceOID}`
- 重复上传：v5 对已绑定票返回 E_DUP；删后即可重加
- receiptOID 是 settle 关键，id 无需数字