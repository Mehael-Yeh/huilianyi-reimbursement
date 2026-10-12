# Huilianyi API capability map

Last researched: 2026-10-12. Status terms are strict: **verified** means a successful request or write/read-back is evidenced; **observed** means a normal client or maintained repository reference exposed the endpoint; **partially verified** means evidence is incomplete; **unknown** means no endpoint claim is being made.

| Domain | Verified | Observed / partial | Unknown / research backlog | MCP policy |
|---|---|---|---|---|
| Auth | OAuth login, realm base URL | token expiry semantics partial | refresh/revocation | internal only |
| Users & organization | current account/company, sanitized company ledgers, user search, cost centers | project values require a budget structure; current-tenant budget probe fails | legal-entity/department/role schemas and methods | READ; raw company security config hidden |
| Configuration | expense types, available forms, currencies/rates | international-area endpoint observed but current tenant returns 404 | custom fields, policies, standards, city/hotel/transport tiers, approval templates | READ after verification |
| Travel | list/detail, create draft | itinerary, itinerary-budget orders, air/hotel/rail/car families observed | schemas/methods, draft update semantics | READ + status-1001 draft only |
| Reimbursements | list/detail, create draft, expense list, submit-or-check (report DTO body; `ignoreBudgetWarningFlag` accepts a budget warning) | save endpoint may also update when identity exists; line removal, receipt release and partial-claim cap recorded in `docs/api-research/2026-10-12-write-path-and-approval-routing.md` | explicit update endpoint, links to loans | READ + status-1001 draft only |
| Invoices & receipts | upload (PDF/OFD/ZIP/XML/Excel), OCR, verify, detail, defaults (bare field list), tax, V5/V6 expense creation, invoice-pool list, current-user expense list; receipts correlate to files through `ocrOriginAttachmentOID` | receipt occupation/remaining balance embedded in verification; orphaned invoice record delete (`/api/v2/invoice/{oid}?confirm=Y`) releases a removed expense's receipts | independent OCR type schemas | READ + guarded draft attach |
| Loans | amount/count summary, repayment summary, business-code search | operation-history path observed; write-off list currently fails | stable detail schema and reimbursement-offset semantics | READ only |
| Approvals | status embedded in application/report, rule-route preview (`/api/approvals/next/all/ruleApprovalNodeOID`) | reimbursement approval history, withdrawal and broad approval families observed; expense types can add rule nodes (私车公用 inserts a 总务 pre-approval) | method/schema/current approver/todo/done | READ only; all state changes disabled |
| Payments | report payment fields and sanitized payment schedules | bank-account query verified but deliberately unexposed | broader payment record schemas | sanitized READ only; accounts/actions disabled |
| Budgets | application budget detail | budget-service prefix, structure/project and balance families observed; structure query returns system exception | safe query parameters and tenant permissions | no new MCP exposure |
| Other | none | none | corporate payment, procurement, contracts, corporate cards, suppliers, journals, ERP, exports | case-by-case |

## Safety boundary

The MCP server exposes an allowlist, never a path/method/body executor. Registry risks are `READ`, `DRAFT_WRITE`, `STATE_CHANGE`, `DESTRUCTIVE`, and `FINANCIAL`. Only `READ` and guarded `DRAFT_WRITE` are eligible for default exposure. Submit, approve, reject, delete, withdraw, close, and payment capabilities remain unexposed even when future research records their endpoints.

## Evidence rules

Each newly claimed endpoint must be added in the same change to:

1. `data/api_registry.yaml` with source and verification status;
2. this map and a dated record under `docs/api-research/`;
3. a unit test for registry integrity and the relevant SDK/MCP operation.

An endpoint string found in a minified bundle is `observed`, never `verified`, until a permitted request establishes its behavior. A field name inside a response is not evidence of an independent endpoint.
