# 发票纯 API 落账

2026-08-21 使用 4 张真实 PDF 对差旅报销与个人报销完成端到端验证。2026-08-22 又验证了格式白名单、OFD 最终保存和无票费用异步终态。

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

2026-08-22 复核证明早先“创建 1.00 元出差补贴成功”的结论错误：费用虽进入列表并增加总额，但 `invoiceSaveStatus=100`，带 `INVOICE_ASYNC_ERROR/费用保存失败`，不能算成功。

1. 动态查询费用类型，确认 `invoiceRequired=false`、`pasteInvoiceNeeded=false`、允许手工创建。
2. 从无异步错误的历史同类无票费用读取 `/api/invoices/{oid}` 完整详情；列表摘要缺少保存上下文，不能作为模板。历史 `FINISHED` DTO 可能没有任职岗位，必须用当前报销单的 `applicantJobId`。
3. 出差补贴强制 `金额 = 补贴天数 × 100`。
4. 调用默认分摊；该接口返回的是分摊骨架，必须补齐 `amount`、`baseCurrencyAmount`、`currency`、`expenseTypeId`、人员以及单据公司字段。有同类申请预算时传数值预算行 ID 列表，否则传空列表。
5. 请求设置 `withReceipt=false`、`receiptList=[]`、`receipts=[]`。
6. 先调用 `POST /invoice/api/validate/invoice/async`；预校验报错时停止，不创建。
7. 仅在预校验无错时调用 `POST /invoice/api/v6/invoices`。
8. 轮询 invoices/v2；编辑中报销单的费用可以正常停在 `SUBMITTED`，也可能为 `FINISHED`。`invoiceSaveStatus=101` 表示仍在处理，`100` 表示失败，`102` 表示异步保存成功；网页同步保存可能为 `null`。成功状态还必须没有异步失败标签。

用户在网页成功保存的 `EXP1321459248` 实证：16 天、1600 元、客户名称为空，状态 `SUBMITTED`，无异步失败。空客户不是失败原因。API 失败请求与网页成功 DTO 的关键差异包括任职/草稿语义，以及默认分摊骨架中的金额、费用类型、人员和单据公司字段未补齐；异步保存不会替客户端补全这些字段。

补齐分摊 DTO 后，API 实测 `EXP1321459863`：1 天、100 元、客户名称为空，最终 `invoiceStatus=SUBMITTED`、`invoiceSaveStatus=102`，正常生成“必填未输、无票”标签，分摊金额、费用类型、人员和嘉兴锐石单据公司字段全部落库。无票出差补贴 API 全链路通过。

## OFD

真实 OFD `25322000000577483943` 可完成上传、OCR、查验、费用类型和税额计算，但最终 `v5/invoices` 返回 `SYSTEM_EXCEPTION` 500，未新增费用行。OFD 当前状态是“识别链路通过、费用落账失败”；不要用 OCR 成功替代全链路成功。
