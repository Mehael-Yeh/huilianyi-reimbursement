# 当前有效 API 端点

仅记录工作流所需端点。所有写操作都限制为草稿创建或编辑。

## 只读校准

- `GET /api/account?roleType=TENANT`
- `POST /api/applications/v4/search?roleType=TENANT&page=0&size=100`
- `GET /api/application/{oid}?showValue=true`
- `POST /api/expense/reports/search/my?roleType=TENANT&page=0&size=100`
- `GET /api/v3/expense/reports/{oid}`
- `GET /api/expense/report/invoices/v2?expenseReportOID={oid}`
- `GET /api/invoices/{invoiceOID}?isDateCombinedUTC=false`
- `GET /api/users/v3/search?roleType=TENANT&size=20&page=0&keyword={name}`
- `GET /api/custom/forms/my/available?roleType=TENANT&formType={101|102}`
- `POST /api/expense/type/byUser`

## 草稿

- `POST /api/travel/applications/draft`
- `POST /api/expense/reports/custom/form/draft?corporateFlag=false`

## 发票落账

- `POST /api/upload/attachment`
- `POST /receipt/api/receipt/ocr/v3`
- `POST /receipt/api/receipt/verify/batch`
- `POST /invoice/api/invoice/defaults`
- `POST /api/expense/default/apportionment`
- `POST /invoice/api/invoice/tax/amount/by/receipts`
- `POST /invoice/api/v5/invoices`
- `POST /invoice/api/validate/invoice/async`
- `POST /invoice/api/v6/invoices`

## 禁止端点

工作流实现中不得出现 submit、delete、close、withdraw 类端点。
