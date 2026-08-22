#!/usr/bin/env python3
"""Round-two read-only probes with structure-only output.

Every path in this file has a matching production Web bundle call site. The
script never persists response values, identifiers, account numbers, or URLs.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from huilianyi.client import HuilianyiClient, unwrap_rows  # noqa: E402
from huilianyi.exceptions import HuilianyiError  # noqa: E402


def describe(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        keys = sorted({str(key) for row in value[:5] if isinstance(row, dict) for key in row})
        return {"shape": "list", "count": len(value), "itemKeys": keys}
    if isinstance(value, dict):
        result: dict[str, Any] = {"shape": "object", "keys": sorted(map(str, value.keys()))}
        for container in ("rows", "data", "values", "paymentSchedules"):
            if isinstance(value.get(container), list):
                result[container] = describe(value[container])
        return result
    return {"shape": type(value).__name__}


def run_probe(name: str, operation: Callable[[], Any], evidence: dict[str, Any]) -> Any:
    try:
        value = operation()
        evidence[name] = describe(value)
        return value
    except HuilianyiError as exc:
        evidence[name] = {"errorCode": exc.code.value, "status": exc.status}
        return None


def first_identifier(rows: list[dict[str, Any]], candidates: tuple[str, ...]) -> str | None:
    for row in rows:
        for key in candidates:
            if row.get(key):
                return str(row[key])
    return None


def main() -> None:
    client = HuilianyiClient.from_credentials()
    account = client.get_current_user()
    evidence: dict[str, Any] = {}

    run_probe(
        "loan_repayment_summary",
        lambda: client.api.request("/api/loanBill/repayment/summary"),
        evidence,
    )
    run_probe(
        "invoice_pool",
        lambda: client.api.request("/api/receipt/pool/query/v2?page=0&size=1"),
        evidence,
    )
    run_probe(
        "my_expense_items",
        lambda: client.api.request("/api/invoices/my", "POST", {"page": 0, "size": 1}),
        evidence,
    )
    run_probe(
        "international_areas",
        lambda: client.api.request("/api/areas/international/list?type=internation"),
        evidence,
    )

    companies = run_probe(
        "companies_for_configuration",
        lambda: client.api.request("/api/widget/company/all?enabled=true"),
        evidence,
    )
    company_rows = unwrap_rows(companies) if companies is not None else []
    set_of_books = account.get("setOfBooksId") or first_identifier(
        company_rows, ("setOfBooksId", "bookId")
    )
    if set_of_books:
        query = urllib.parse.urlencode(
            {"setOfBooksId": set_of_books, "language": "zh_cn", "enable": "true"}
        )
        run_probe(
            "currencies",
            lambda: client.api.request(f"/api/currency/rate/list/all?{query}"),
            evidence,
        )

    user_oid = account.get("userOID")
    if user_oid:
        query = urllib.parse.urlencode(
            {"userOID": user_oid, "enable": "true", "sourceType": "BANKCARD_ACCOUNT"}
        )
        run_probe(
            "my_bank_accounts",
            lambda: client.api.request(f"/api/contact/bank/account/my?{query}"),
            evidence,
        )

    structures_value = run_probe(
        "budget_structures",
        lambda: client.gateway.request(
            "/budget-service/api/budget/structures/query?page=0&size=20"
        ),
        evidence,
    )
    structure_rows = unwrap_rows(structures_value) if structures_value is not None else []
    structure_id = first_identifier(
        structure_rows, ("structureId", "budgetStructureId", "id", "entityOID")
    )
    if structure_id:
        query = urllib.parse.urlencode({"structureId": structure_id})
        run_probe(
            "projects_for_budget_structure",
            lambda: client.gateway.request(
                f"/budget-service/api/budget/structure/assign/project/queryAll?{query}"
            ),
            evidence,
        )
    else:
        evidence["projects_for_budget_structure"] = {
            "notRun": "no visible budget structure identifier"
        }

    reports = client.list_reimbursements(0, 1)
    report_oid = first_identifier(reports, ("expenseReportOID", "entityOID", "oid"))
    if report_oid:
        query = urllib.parse.urlencode({"expOid": report_oid})
        run_probe(
            "payment_schedules_for_reimbursement",
            lambda: client.api.request(f"/api/payment/schedule/query/by/expOid?{query}"),
            evidence,
        )
    else:
        evidence["payment_schedules_for_reimbursement"] = {
            "notRun": "no visible reimbursement"
        }

    print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
