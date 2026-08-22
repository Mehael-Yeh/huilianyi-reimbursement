# Current API inventory

Audited from `origin/main` on 2026-08-23. This document covers APIs already used or explicitly documented by the repository. The machine-readable source of truth is [`data/api_registry.yaml`](../data/api_registry.yaml).

## Authentication and transport

The client RSA-encrypts the password and sends an OAuth password grant to `POST /proxy/oauth/token/v2`. The response supplies a Bearer token and the tenant-specific `realm_base_service_url`. Business requests use that tenant URL; receipt/invoice gateway calls use `https://console-a2.huilianyi.com`. Passwords are stored only in the OS credential vault; the username may be stored in a local config outside the repository.

All responses are JSON. List endpoints have historically returned one of `rows`, `content`, `data`, or `list`; the SDK normalizes these shapes. Every endpoint requires Bearer auth except login.

## Read relationships

| Method and path | Purpose | Request | Key response | Call site | Scenario | Mutation | Risk |
|---|---|---|---|---|---|---:|---|
| `GET /api/account` | Current account/company | `roleType` | account, tenant/company fields | documented; SDK | profile/MCP | no | READ |
| `GET /api/users/v3/search` | User lookup | keyword/page/size | user/job/department rows | workflow, SDK | agent/participant selection | no | READ |
| `POST /api/applications/v4/search` | Travel application list | page/size + `{}` | application summaries | workflow, SDK | history/template lookup | no | READ |
| `GET /api/application/{oid}` | Travel application detail | OID, `showValue` | status, travel dates, budget, fields | workflow, SDK | linking/audit/template | no | READ |
| `POST /api/expense/reports/search/my` | Reimbursement list | page/size + `{}` | report summaries | workflow, SDK | history/template lookup | no | READ |
| `GET /api/v3/expense/reports/{oid}` | Reimbursement detail | OID | report, linkage, totals | workflow, SDK | draft guard/audit | no | READ |
| `GET /api/expense/report/invoices/v2` | Expense lines on a report | expenseReportOID | invoice views and totals | CLI/workflow, SDK | verification/Excel | no | READ |
| `GET /api/invoices/{oid}` | Expense/invoice detail | invoice OID | expense fields and receipts | workflow, SDK | receipt reconciliation | no | READ |
| `GET /api/custom/forms/my/available` | Available forms | formType 101/102 | form rows | documentation only | form discovery | no | READ |
| `POST /api/expense/type/byUser` | Available expense types | report/applicant/form | type rows and receipt rules | workflow, SDK | expense construction | no | READ |
| `GET /api/widget/company/all` | Visible company ledgers | enabled | company/legal entity/ledger rows; raw DTO is sensitive | SDK | ledger selection | no | READ |
| `GET /api/currency/rate/list/all` | Currency and exchange-rate list | ledger/language/enabled | currency/rate rows | SDK | currency lookup | no | READ |
| `GET /api/receipt/pool/query/v2` | Current-user invoice pool | page/size | paged receipts | SDK | invoice selection | no | READ |
| `POST /api/invoices/my` | Current-user reusable expense items | page/size | paged expense items | SDK | expense lookup | no | READ |
| `GET /api/loanBill/repayment/summary` | Loan repayment summary | none | currency amount/count groups | SDK | loan overview | no | READ |
| `GET /api/loanBill/query/business/code/by/keyword` | Loan search | keyword | visible loan rows or empty | SDK | loan lookup | no | READ |
| `GET /api/payment/schedule/query/by/expOid` | Reimbursement payment status | report OID | payment schedule rows | SDK | read-only payment status | no | READ |

## Draft creation and expense landing

| Method and path | Purpose | Request | Key response | Call site | Mutation | Risk |
|---|---|---|---|---|---:|---|
| `POST /api/travel/applications/draft` | Save travel draft | complete status-1001 DTO | OID/business code | workflow, SDK | yes | DRAFT_WRITE |
| `POST /api/expense/reports/custom/form/draft` | Save reimbursement draft | complete status-1001 DTO | OID/business code | workflow, SDK | yes | DRAFT_WRITE |
| `POST /api/upload/attachment` | Upload original file | multipart file/type | attachment metadata | former API module, SDK | yes | DRAFT_WRITE |
| `POST /receipt/api/receipt/ocr/v3` | OCR uploaded receipts | attachment list/report | receipt candidates | workflow | yes/intermediate | DRAFT_WRITE |
| `POST /receipt/api/receipt/verify/batch` | Verify receipts | invoiceInfo list | status/remaining balance | workflow | yes/intermediate | DRAFT_WRITE |
| `POST /invoice/api/invoice/defaults` | Expense defaults | type + receipts | data/default fields | workflow | no | READ |
| `POST /api/expense/default/apportionment` | Default apportionment | report/type/amount/owner | allocation rows | workflow | no | READ |
| `POST /invoice/api/invoice/tax/amount/by/receipts` | Tax calculation | expense + receipts | calculated tax fields | workflow | no | READ |
| `POST /invoice/api/v5/invoices` | Receipt-backed expense | complete V5 DTO | invoiceOID | workflow | yes | DRAFT_WRITE |
| `POST /invoice/api/validate/invoice/async` | Manual expense preflight | complete V6 DTO | validation errors | workflow | no | READ |
| `POST /invoice/api/v6/invoices` | Manual expense | complete V6 DTO | invoiceOID/save status | workflow | yes | DRAFT_WRITE |

## Business graph

```text
authenticated user
  -> tenant/company + job/department
  -> available forms + expense types
  -> travel application (dates, people, budget lines)
      -> linked reimbursement report
          -> expense item
              -> attachment -> OCR -> verification
              -> defaults -> apportionment -> tax
              -> V5 receipt expense / V6 manual expense
          -> API read-back -> amount and receipt reconciliation -> Excel
```

## Additional 2026-08-23 research

Read-only live verification added `GET /api/widget/company/all`, `GET /api/cost/centers/search`, `GET /api/loanBill/my/amountAndCount`, `GET /api/travel/applications/itinerarys`, and `GET /api/v2/expense/reports/approval/history`. The company DTO is intentionally not exposed raw because it contains broad tenant/security configuration fields. Cost-center, loan summary, itinerary, and approval-history reads are exposed through curated SDK/MCP methods.

Production Bundle and live reads now verify currency rates, invoice-pool listing, current-user expense listing, loan repayment summary/search, and reimbursement payment schedules. MCP returns allowlisted fields for invoice-pool and payment responses; it does not return the raw DTOs.

The Web bundle shows budget calls under `/budget-service`, including structure and project queries. Current-tenant read probes reached the service but returned a system exception, so budget structures and projects remain `partially_verified` and unexposed. The international-area path returned 404. The current-user bank-account query succeeded, but it remains `FINANCIAL` and unexposed because its raw rows contain account number, IBAN, SWIFT, and related sensitive fields.
