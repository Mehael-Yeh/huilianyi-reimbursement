# Huilianyi API capability map

Last researched: 2026-08-23. Status terms are strict: **verified** means a successful request or write/read-back is evidenced; **observed** means a normal client or maintained repository reference exposed the endpoint; **partially verified** means evidence is incomplete; **unknown** means no endpoint claim is being made.

| Domain | Verified | Observed / partial | Unknown / research backlog | MCP policy |
|---|---|---|---|---|
| Auth | OAuth login, realm base URL | token expiry semantics partial | refresh/revocation | internal only |
| Users & organization | current account/company, user search | company list, cost-center search, project values, currency and country paths observed | legal-entity/department/role schemas and methods | READ after verification |
| Configuration | expense types, available forms | currency/country and form configuration paths observed | custom fields, policies, standards, city/hotel/transport tiers, approval templates | READ after verification |
| Travel | list/detail, create draft | itinerary, itinerary-budget orders, air/hotel/rail/car families observed | schemas/methods, draft update semantics | READ + status-1001 draft only |
| Reimbursements | list/detail, create draft, expense list | save endpoint may also update when identity exists | explicit update endpoint, delete, links to loans | READ + status-1001 draft only |
| Invoices & receipts | upload, OCR, verify, detail, defaults, tax, V5/V6 expense creation | receipt occupation/remaining balance embedded in verification | invoice pool/list, release, delete, independent OCR types | READ + guarded draft attach |
| Loans | none | amount/count summary and operation-history paths observed | list/detail/balance/write-off/reimbursement offset schemas | READ only after verification |
| Approvals | status embedded in application/report | reimbursement approval history and broad approval families observed | method/schema/current approver/todo/done | READ only; all state changes disabled |
| Payments | report payment fields | user bank-account and payment-schedule paths observed | status/records/account schemas | READ only; financial actions disabled |
| Budgets | application budget detail | balance/explanation, items, departments, projects and control-rule families observed | safe query schemas and permissions | READ only |
| Other | none | none | corporate payment, procurement, contracts, corporate cards, suppliers, journals, ERP, exports | case-by-case |

## Safety boundary

The MCP server exposes an allowlist, never a path/method/body executor. Registry risks are `READ`, `DRAFT_WRITE`, `STATE_CHANGE`, `DESTRUCTIVE`, and `FINANCIAL`. Only `READ` and guarded `DRAFT_WRITE` are eligible for default exposure. Submit, approve, reject, delete, withdraw, close, and payment capabilities remain unexposed even when future research records their endpoints.

## Evidence rules

Each newly claimed endpoint must be added in the same change to:

1. `data/api_registry.yaml` with source and verification status;
2. this map and a dated record under `docs/api-research/`;
3. a unit test for registry integrity and the relevant SDK/MCP operation.

An endpoint string found in a minified bundle is `observed`, never `verified`, until a permitted request establishes its behavior. A field name inside a response is not evidence of an independent endpoint.
