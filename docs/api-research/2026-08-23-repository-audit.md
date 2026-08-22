# Repository API audit — 2026-08-23

## Scope and method

Read `origin/main` in full: Skill instructions, README, all Python/JavaScript code, references, tests, configuration, and Git state. Searched call sites and endpoint literals. No live content was changed during this phase.

## Evidence

- Existing endpoint implementations: `scripts/hly_api.py`, `scripts/hly_workflow.py`, and three direct read calls in `scripts/hly.py`.
- Existing behavioral records: `references/api-endpoints.md`, `api-notes.md`, `invoice-landing.md`, and `workflow-model.md`.
- Prior verified draft workflow: travel/reimbursement status 1001 and receipt landing sequence were read back successfully.

Request and response examples in the registry deliberately contain schemas and representative field names, not tokens, cookies, signed URLs, OIDs, or raw account payloads.

## Stability and risk findings

- The API is an authenticated A2 web API rather than a documented public integration contract, so even verified endpoints are treated as version-sensitive.
- Receipt OCR and verification are classified as draft mutations/intermediate writes rather than pure reads.
- The former generic `Client.request()` is retained only as an internal SDK compatibility surface. It is not an MCP tool.
- `GET /api/account` and available-form discovery were recorded by maintained repository documentation but had no direct call site at audit time, so they are not marked fully verified.

## Next research

Use normal account-authorized, read-only requests and static front-end bundle evidence. Do not probe guessed paths, escalate permissions, enumerate other tenants, or call submit/approval/deletion/payment actions.
