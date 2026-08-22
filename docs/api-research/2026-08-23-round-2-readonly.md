# Round 2 read-only API research — 2026-08-23

## Scope and safeguards

This round investigated projects, loans, budgets, invoice pool, payments, currencies, countries, and bank accounts. All live calls were either GET or front-end-evidenced semantic query POSTs. No draft, document, invoice, approval, payment, or account state was changed. The research script emits only response shape, count, and field names; it does not persist values, OIDs, account numbers, tokens, or signed URLs.

## Production Web evidence

| Capability | Web call evidence | Method/parameters established |
|---|---|---|
| Currency rates | `getValueCurrency` | `GET /api/currency/rate/list/all`, `setOfBooksId`, `language`, `enable` |
| Invoice pool | `getInvoicePoolList` | `GET /api/receipt/pool/query/v2`, caller-supplied query object |
| My expense items | `getExpenseList` | `POST /api/invoices/my`, body includes `page`, `size` and filters |
| Loan repayment summary | dashboard `getBorrowList` | `GET /api/loanBill/repayment/summary` |
| Loan search | selector `business_code_borrow` | `GET /api/loanBill/query/business/code/by/keyword`, `keyword` |
| Payment schedules | `queryPayingBank` | `GET /api/payment/schedule/query/by/expOid`, `expOid` |
| Bank accounts | `getBankCards` | `GET /api/contact/bank/account/my`, `userOID`, `enable`, `sourceType` |
| Budget structures | `getBudgetStructures` plus runtime config | `GET /budget-service/api/budget/structures/query`, caller-supplied query object |
| Projects | `getRuleParamDIM` | `GET /budget-service/api/budget/structure/assign/project/queryAll`, `structureId` |
| International areas | `getAllStates` | `GET /api/areas/international/list?type=internation` |

Bundle literals were static evidence only. They were not classified as verified until an allowed live read succeeded.

## Live structural verification

Successful reads:

- currency rates returned rows with currency, base currency, rate, precision, enable, and effective-date fields;
- invoice pool returned a paged receipt DTO;
- current-user expense query returned a valid empty paged response;
- loan repayment summary returned currency amount/count groups;
- loan business-code search returned a valid empty result;
- reimbursement payment lookup returned payment schedule rows;
- current-user bank-account lookup returned rows.

Sensitive response handling:

- the invoice-pool DTO contains bank-account, identity, attachment URL, and broad OCR metadata fields; MCP exposes a strict receipt-field allowlist;
- payment schedules contain payee and bank-account fields; MCP exposes status, dates, amount, currency, and payment-method summary only;
- bank-account rows contain account number, IBAN, SWIFT, and account-name fields; the API is registered as `FINANCIAL` and is not exposed through MCP;
- company rows contain client secret/token configuration fields; `list_ledgers` exposes only company/legal-entity/ledger/currency identifiers and names.

Unsuccessful or incomplete reads:

- `/api/areas/international/list?type=internation` returned 404 for this environment and remains observed;
- `/budget-service/api/budget/structures/query` reached the budget service but returned `SYSTEM_EXCEPTION` with tested pagination and ledger context;
- project lookup was not called because no verified budget structure identifier was available;
- `/api/loan/line/my/writeOff` returned a system exception and was not added as a stable list endpoint.

## Resulting exposure decision

New MCP READ tools: `list_ledgers`, `list_currencies`, `list_invoice_pool`, `list_my_expense_items`, `get_loan_repayment_summary`, `search_loans`, and `get_reimbursement_payment_status`.

Not exposed: bank accounts, budget structures/projects, international areas, loan write-off records, payment mutations, and every submit/approve/reject/delete/withdraw/close operation.
