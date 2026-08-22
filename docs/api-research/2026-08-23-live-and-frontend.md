# Live read-only and production front-end research — 2026-08-23

## Authorization and safety

Used the user-provided test account through the repository's normal OAuth flow. Credentials were persisted only by the existing OS keyring provider. Live calls were limited to already known read endpoints. No draft, receipt, submit, approval, deletion, withdrawal, close, or payment request was sent.

## Live verification

Successful, sanitized structural checks verified:

- `GET /api/account?roleType=TENANT`: account object including current company, corporation, department, authority, country, and job-related fields.
- `POST /api/applications/v4/search`: non-empty paged travel-application list.
- `POST /api/expense/reports/search/my`: non-empty paged reimbursement list.
- `GET /api/custom/forms/my/available?formType=101`: available application forms.
- `GET /api/custom/forms/my/available?formType=102`: available reimbursement forms.
- `GET /api/widget/company/all?enabled=true`: visible companies; raw DTO intentionally withheld from MCP.
- `GET /api/cost/centers/search`: successful empty result for this account.
- `GET /api/loanBill/my/amountAndCount`: loan count/currency/outstanding write-off summary.
- `GET /api/travel/applications/itinerarys`: successful empty itinerary result for the sampled application.
- `GET /api/v2/expense/reports/approval/history`: approval-history response for a visible report.

The research artifact records only shapes, row counts, and field names. It excludes values, OIDs, tokens, cookies, signed URLs, and account identifiers.

## Static front-end evidence

Downloaded the current console HTML and same-origin production bundles from the normal Huilianyi CDN. Approximately 23 MB across 21 fetched assets yielded literal endpoint paths. A literal is evidence that the shipped client references a path, but does not establish HTTP method, request schema, permission, or stability.

Representative observed domains added to the Registry:

- Organization/configuration: company widget, cost-center search, project assignment values, currencies, countries.
- Travel: application itineraries and linked itinerary-budget orders.
- Loans: user amount/count summary verified; loan operation history observed.
- Approvals: reimbursement approval history verified.
- Budgets: budget explanation/balance query.
- Payments: current-user bank accounts and payment-schedule mutation.
- Explicitly blocked state changes: travel/reimbursement submit, approval rejection, invoice deletion, reimbursement withdrawal, application close.

Thousands of unrelated administrative, archive, procurement, contract, supplier, and finance literals were not copied wholesale into the first-round Registry. They remain reproducible through `scripts/research_api_map.py` and should be curated domain-by-domain with method/schema evidence before SDK or MCP exposure.

## Stability

Bundle context can establish a method without establishing callability. Entries remain `observed` and `mcp_exposed: false` until an authorized live read verifies their request/response behavior. State-changing and financial entries remain unexposed regardless.
