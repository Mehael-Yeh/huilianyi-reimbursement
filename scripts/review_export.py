#!/usr/bin/env python3
"""Prepare user-facing reimbursement review data from classification and API results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CATEGORY_ALIASES = {
    "打车费": {"打车费", "市内交通费", "其他交通", "其他交通费"},
    "其他交通": {"其他交通", "其他交通费", "市内交通费", "火车", "机票"},
    "礼品费": {"礼品费", "其他招待费用"},
    "里程补贴": {"里程补贴", "油费"},
}


def _possible_expense_types(category: str) -> set[str]:
    return CATEGORY_ALIASES.get(category, {category})


def _successful(expense: dict[str, Any]) -> bool:
    labels = set(expense.get("labels") or [])
    return expense.get("invoiceSaveStatus") != 100 and "费用保存失败" not in labels


def merge_review_data(
    invoice_review: dict[str, Any], reports: list[dict[str, Any]], categories: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    expenses = []
    for report in reports:
        for expense in report.get("expenses") or []:
            expenses.append({**expense, "reportCode": report.get("businessCode")})

    used_expenses: set[str] = set()
    rows = []
    for item in invoice_review.get("rows") or []:
        match = None
        invoice_number = str(item.get("invoiceNumber") or "")
        if invoice_number:
            candidates = [
                expense for expense in expenses
                if invoice_number in {str(value) for value in expense.get("invoiceNumbers") or []}
            ]
            if len(candidates) == 1:
                match = candidates[0]
        if match is None and item.get("countAmount", True):
            allowed = _possible_expense_types(str(item.get("category") or ""))
            candidates = [
                expense for expense in expenses
                if str(expense.get("expenseOID")) not in used_expenses
                and expense.get("expenseType") in allowed
                and round(float(expense.get("amount") or 0), 2) == round(float(item.get("amount") or 0), 2)
            ]
            if len(candidates) == 1:
                match = candidates[0]
        if match:
            used_expenses.add(str(match.get("expenseOID")))
        rows.append({
            "fileName": item.get("fileName"),
            "format": "/".join(item.get("formats") or [item.get("format") or ""]),
            "documentType": "附件" if not item.get("countAmount", True) else "发票",
            "invoiceNumber": item.get("invoiceNumber"),
            "suggestedCategory": item.get("category"),
            "confirmedCategory": item.get("category") if not item.get("needsReview") else "",
            "reportGroup": item.get("reportGroup"),
            "recognizedAmount": item.get("amount") if item.get("countAmount", True) else None,
            "finalAmount": (match or {}).get("amount") if match else item.get("amount"),
            "amountSource": item.get("source"),
            "classificationBasis": "、".join(item.get("matchedKeywords") or []),
            "confidence": {"high": "高", "low": "低"}.get(item.get("confidence"), item.get("confidence")),
            "needsReview": "是" if item.get("needsReview") or not match and item.get("countAmount", True) else "否",
            "expenseCode": (match or {}).get("expenseCode"),
            "saveStatus": (
                "成功" if match and _successful(match)
                else "失败" if match
                else "附件" if not item.get("countAmount", True)
                else "未匹配"
            ),
            "reportCode": (match or {}).get("reportCode"),
            "notes": "",
        })

    metadata = {
        "reportCodes": [report.get("businessCode") for report in reports],
        "reportTotal": round(sum(float(report.get("totalAmount") or 0) for report in reports), 2),
        "failedExpenses": sum(len(report.get("asynchronousSaveFailures") or []) for report in reports),
    }
    return {"metadata": metadata, "rows": rows, "categories": categories or []}


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
