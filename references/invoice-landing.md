# 发票纯 API 落账

2026-08-21 使用 4 张真实 PDF 对差旅报销与个人报销完成端到端验证。

## 顺序

1. 上传：`POST /api/upload/attachment`，multipart 字段 `attachmentType=INVOICE_IMAGES`、`file=<PDF>`。
2. OCR：`POST /receipt/api/receipt/ocr/v3`。
3. 查验：`POST /receipt/api/receipt/verify/batch`，取响应中的富化 `invoiceInfo`。
4. 动态查询费用类型：`POST /api/expense/type/byUser`。
5. 默认值：`POST /invoice/api/invoice/defaults`。
6. 默认分摊：`POST /api/expense/default/apportionment`。
7. 税额/金额：`POST /invoice/api/invoice/tax/amount/by/receipts`。
8. 创建并绑定费用行：`POST /invoice/api/v5/invoices`。
9. 回读：`GET /api/expense/report/invoices/v2?expenseReportOID={oid}`。

## 关键纠错

### receipt.id 可以为空

实测 4 张成功发票均为：

```json
{"id": null, "receiptOID": "<有效OID>"}
```

`receiptOID`、查验结果和完整富化字段是关键，不要求数字 `id`。

### 不得把 tax 的 invoiceOID 传给 v5

`tax/amount` 返回一个临时 `invoiceOID`。若原样合并到 `v5/invoices`，服务器会把请求当成更新不存在/已删除的费用，返回：

```text
invoice.already.deleted / 该费用已被其他人删除
```

最终请求构造：

```python
body = {k: v for k, v in tax_result.items() if v is not None}
body.update(common_fields)
body.pop("invoiceOID", None)
body["valid"] = True
```

### 金额

`amount` 和 `originalAmount` 必须等于本张发票实际报销金额，否则会触发发票可报销额度校验。

### 同类发票关联申请预算

差旅报销先按规范化费用类型查找关联申请的 `budgetDetailDTO.budgetDetail[]`：

- 将所有同类预算行的数值 `id` 组成数组传入默认分摊请求的 `applicationCustomBudgetId`；同类所有发票复用该数组。
- 不得传 `budgetOID`，不得传标量。只读探针验证这两种形式都会返回校验错误。
- 申请没有该类目时传 `[]`，按手录费用新增真实类别。
- 最终费用请求必须携带默认分摊接口返回的 `expenseApportion`；成功匹配时其中含 `relationApplicationApportionmentGroupMd5`。
- 预算类目金额是汇总基线，并非每张发票额度；发票合计可以与申请金额不同。

### v5 是落账真值

`v5/invoices` 成功后会创建费用行、绑定发票并更新报告总额。不再手拼 `expenseReportInvoices`，也不再额外回存整单实体。

实现见 `hly_workflow.add_invoice()`。

## 无票手录费用

已于 2026-08-22 对编辑中差旅报销完成端到端验证：不上传附件、不调用 OCR/查验，创建 1.00 元“出差补贴”后，报告总额和费用行数量均正确增加。

1. 动态查询费用类型，确认 `invoiceRequired=false`、`pasteInvoiceNeeded=false`、允许手工创建。
2. 从历史同类无票费用复制自定义字段结构并清空旧值，填写所有必填项。
3. 调用默认分摊；有同类申请预算时传数值预算行 ID 列表，否则传空列表。
4. 请求设置 `withReceipt=false`、`receiptList=[]`、`receipts=[]`。
5. 先调用 `POST /invoice/api/validate/invoice/async`。
6. 最终调用 `POST /invoice/api/v6/invoices`。本租户 v5 无票请求返回通用 500，v6 成功。
7. 回读 invoices/v2，确认费用 `withReceipt=false` 且 `receiptList` 为空。
