# Write path and approval routing (2026-10-12)

This note summarizes observed API behavior. All amounts, entity identifiers, supplier names,
people, dates of business activity, and approval-route examples below are synthetic or omitted.
They are not a record of any user's reimbursements or an organization's internal approval policy.
Endpoint paths, field names, and generic error codes are retained for technical reference.
Tenant-specific identifiers and configuration must be queried at runtime; never copy example
values into a real request. This research note does not authorize submission or deletion; the
Skill and MCP remain limited to their documented draft-only operations.

## 1. Receipts are not returned in upload order

`POST /receipt/api/receipt/ocr/v3` and `POST /receipt/api/receipt/verify/batch` answer in their
own order (observed: reversed). Every receipt carries `ocrOriginAttachmentOID` (and
`attachmentOID`) pointing at the uploaded attachment, plus `originAttachment.fileName`, so the
receipt is matched back to its file through the upload result.

Zipping positionally mislabels the invoice number, amount, `pdfUrl` and the per-item report of a
batch. Symptom before the fix: `provided amount 120.50 differs from verified invoice amount 180.75`
for a hotel batch, and a single receipt could be reported as another file.

* Fixed in `scripts/hly_workflow.py::align_receipts`; used for both the OCR and the verify answer.
* Receipts without any attachment link keep the legacy positional behaviour.
* A file whose OCR produced no receipt is reported by name instead of a bare count mismatch.
* Multi-invoice single files (for example 通行费汇总单, which yields an empty + a 250.00 receipt)
  are refused with `OCR returned 2 receipts for one file: <name>`.

## 2. `POST /invoice/api/invoice/defaults` answers with a bare field list

The body is `{expenseTypeId, receipts}`; the answer is a raw list of field definitions
(`fieldOID`, `fieldLabel`, `fieldType`, `fieldTypeEnum`, `value`, `showValue`, `config`) — not a
`{"data": [...]}` envelope. Treating it as a dict silently produced `data = []`, so the created
line kept the field structure with empty values and the platform flagged 必填未输
(`入住城市,开始结束日期,客户名称 字段为空`).

* The receipts must be the **verified** `invoiceInfo` rows: raw OCR rows carry
  `sellerCityCode: null` and the endpoint then answers `[]`; verification fills
  `sellerCityCode`/`sellerCityName` (synthetic example: 示例酒店 resolves to 示例城市 with `<city-code>`).
* Fixed in `add_invoice_batch` (list → `{"data": list}`).

## 3. The apportionment shell must be completed

`POST /api/expense/default/apportionment` answers with a template whose ids and amounts are null
(`amount`, `baseCurrencyAmount`, `currency`, `expenseTypeId`, `expenseReportId`,
`apportionmentCompany*`, `proportion`). For expense types with `erApportionEnabled: true`
(其他招待费用, 酒店) a create that still carries that shell fails with
`HTTP 500 {"message": "系统异常", "errorCode": "SYSTEM_EXCEPTION"}` — reproduced for every
available 招待 invoice, single or batched. Types without apportionment ignore the shell, which is
why 过路费 and 里程补贴 appeared to work.

Fill each row with `amount`/`baseCurrencyAmount` = line amount, `originTaxAmount`/`baseTaxAmount` =
tax, `currency` CNY, `expenseTypeId`, `expenseReportId` (report `id`), `apportionmentCompanyOID/
Name/Code` of `docCompany*`, `proportion` 1, `defaultApportion` true. See
`populate_apportionment`. The endpoint itself refuses to be re-queried for an existing expense
(`VALIDATION_ERROR` on `POST /api/expense/default/apportionment`), so when an existing line must be
updated its stored `expenseApportion` rows are reused and rescaled.

## 4. Required form values can be added from a saved line

`客户名称` is not derivable from a receipt, so `defaults` never returns a value for it, and the
personal/差旅 templates differ per expense type. Field definitions are cloned from the newest saved
expense of the same type (`GET /api/invoices/{invoice_oid}?isDateCombinedUTC=false` →
`data[]`), then written with value **and** showValue (`apply_field_values`, CLI `--field
NAME=VALUE`). Missing definitions raise `expense field not available: <name>` instead of writing a
placeholder.

## 5. Partial claims permanently cap a line

When the requested amount is lower than the receipts' face value the platform stores the line as
部分报销 and rewrites each receipt's `invoicedReceiptAmount` (本次报销金额) proportionally — a
200.00 receipt could be reduced to 150.00 for a 900.00 request against 1200.00 of receipts
(synthetic proportional example). Raising the
line afterwards fails with
`er-167974@INVOICES_RECEIPTS_AMOUNT_ABS_POSITIVE 费用金额超出发票的本次报销金额之和，可报销范围为0～900之间`,
and removing the claim without touching the receipts fails with
`er-167974@INVOICES_RECEIPTS_AMOUNT_ABS_ZERO 可报销金额为0`. Recovery: restore every receipt's
`invoicedReceiptAmount` to `totalAmount`/`fee` (drop `actualReimbursementAmount`) and re-post the V5
body.

## 6. Removing a line and releasing its receipts

* `DELETE /api/expense/reports/remove/invoice/{expense_report_oid}/{invoice_oid}` detaches one
  expense from an editing draft (the report id comes first; the reversed order answers
  `VALIDATION_ERROR`). The route preview drops the affected approval nodes immediately.
* Removing the line does **not** release the receipts it claimed: `verify/batch` then reports
  `unUsedAmount 0` for every one of them and any create answers
  `er-167974@...ABS_ZERO` / `E_DUP_INVOICES_RECEIPTS_AMOUNT_01 发票可报销总额不足`.
  `/receipt/api/query/all/receipt/unused/amount`, `/receipt/api/receipt/recheck` and
  `/invoice/api/recovery/amount` do not release them either.
* Release works only for the **orphaned invoice record**:
  `DELETE /api/v2/invoice/{invoice_oid}?confirm=Y` (without `confirm=Y`:
  `er-148959@status.del 当前费用状态在账本无法删除`). Order: remove the line, then delete the
  record; only then can the receipts be booked again.
* `DELETE /api/expense/reports/delete/invoice/{a}/{b}` answers
  `单据:ER...内不存在费用编码:EXP...,不允许删除` once the expense is gone.

## 7. Submission, withdrawal and route preview (not exposed by the skill)

* `POST /api/v3/expense/report/submit?roleType=TENANT` with the **report DTO** is a
  submit-or-check: it answers `{passFlag, submitSuccess, needConfirm, checkResultList}`. Without a
  warning the call submits the report (`submitSuccess: true`); with a warning it returns
  `needConfirm: true` and the check list (for example
  `TOTAL_AMOUNT_OVER_APPLICATION 超出 CNY 300.00：本次可关联费用金额 CNY 900.00，实际关联费用金额 CNY 1200.00`).
  Sending the same DTO again with `ignoreBudgetWarningFlag: true` submits it. None of
  `needConfirm`/`confirmFlag`/`ignoreWarn`/… flags, query switches or alternative paths
  (`/submit/{oid}`, `/submit/confirm`, `/api/v3/expense/reports/submit`, `/api/approvals/submit/...`)
  worked; `/api/expense/report/submit` 404s and `PUT` is 405.
* Already-paid reports answer `11882@BILL_STATUS_EDIT 该单据为非编辑状态`.
* `POST /api/approvals/withdraw` (body `{entityType, entityOID}`) is the observed withdrawal;
  a withdrawn report returns to `status 1001` with `withdrawFlag: 'Y'` and its lines stay editable.
* `POST /api/approvals/next/all/ruleApprovalNodeOID` with `{entityType: 1002, entityOID}` previews
  the route (`name`, `nodeApproverDescription`, `ruleApprovers`), and
  `GET /api/v2/expense/reports/approval/history?expenseReportOID=<oid>` returns
  `rows.approvalHistoryDTOs` (`operation 1001` submit, `1002` withdraw).

## 8. Expense types are immutable, and some of them add approval nodes

* Changing the expense type of an existing line is refused:
  `VALIDATION_ERROR validationErrors: [{"attributeName": "ExpenseType", "message": "费用类型不可切换"}], bizErrorCode 9001`.
  A different type requires removing the line and creating a new one.
* Available expense types and retired historical types can differ even when their display names
  are similar. Synthetic example: a current mileage type has id `<current-expense-type-id>`
  and classification CAR; a retired type has id `<retired-expense-type-id>` and classification
  OTHER. Query the current tenant's available types instead of reusing historical IDs or codes.
* Approval routing is tenant-configured and may depend on the selected expense type. A
  synthetic route might be `示例审批节点 A → 示例审批节点 B`; a configured expense condition
  might insert `示例附加审批节点（示例审批人）`. This example does not describe any real
  person's role, rule priority, node count, or reporting chain.
* Confirm the appropriate expense category against the actual expense and current policy.
  Preview the authorized report's route when needed; do not choose a different category merely
  to avoid an approval step.

## 9. Supporting documents

Expense-level `attachments` accept EXCEL as well as PDF/OFD/ZIP/XML (`upload_attachment` returns
`{id, attachmentOID, fileName, fileType, fileURL}`); a synthetic supporting workbook is named
`私车公用报销清单-示例.xlsx`. The skill now allows xlsx for 过路费, 里程补贴 and 油费, and
auto-attaches a `私车公用报销清单*.xls*` / `*里程截图*.xls*` workbook found next to a 里程补贴/油费
batch (`default_mileage_sheets`).

## 10. Code touched

`scripts/hly_workflow.py`: `align_receipts`, `validate_attachment_file`,
`default_mileage_sheets`, `apply_field_values`, `hotel_field_values(templates=…)`,
`expense_field_templates`, `populate_apportionment`, defaults list handling, `field_values`
parameter. `scripts/hly.py`: `--field NAME=VALUE` on `add-invoice` and `add-invoice-batch`.
Regression tests: `tests/test_workflow_fixes.py`.
