#!/usr/bin/env python3
"""Verified Huilianyi draft and invoice workflows.

This module intentionally contains no submit, close, withdraw, or delete
operations. All write helpers create/edit draft data only.
"""

from __future__ import annotations

import copy
import json
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Any

from hly_api import Client, unwrap_row, unwrap_rows


DRAFT_STATUS = 1001
APPROVED_APPLICATION_STATUS = 1003
TRAVEL_TYPE_ALIASES = {"市内交通费": "其他交通", "其他交通费": "其他交通"}
ALLOWED_UPLOAD_SUFFIXES = {".pdf", ".ofd", ".zip", ".xml"}
RECEIPT_AMOUNT_KEYS = (
    "totalTaxIncludedAmount", "taxInclusiveTotalAmount", "amountIncludingTax",
    "totalAmountWithTax", "invoiceAmountWithTax", "totalPriceAndTax", "priceTaxTotal",
    "invoicePriceTaxTotal", "invoiceTotalAmount", "invoiceAmount", "totalAmount",
)
HOTEL_CITY_CODES = {
    "上海": "CHN031000000",
    "南京": "CHN032001000",
    "无锡": "CHN032002000",
    "常州": "CHN032004000",
    "苏州": "CHN032005000",
    "昆山": "CHN032005830",
    "杭州": "CHN033001000",
    "嘉兴": "CHN033004000",
}


def validate_upload_file(file_path: str | Path) -> Path:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_UPLOAD_SUFFIXES))
        raise ValueError(f"unsupported upload format {suffix or '<none>'}; allowed: {allowed}")
    return path


def recognized_receipt_amount(receipt: dict[str, Any]) -> float | None:
    """Return a verified tax-inclusive amount, never tax or unit price."""
    containers = [receipt]
    for key in ("invoiceInfo", "receiptInfo", "recognizedData"):
        value = receipt.get(key)
        if isinstance(value, dict):
            containers.append(value)
    for container in containers:
        for key in RECEIPT_AMOUNT_KEYS:
            value = container.get(key)
            if value in (None, ""):
                continue
            normalized = re.sub(r"[^0-9.,-]", "", str(value)).replace(",", "")
            try:
                amount = round(float(normalized), 2)
            except ValueError:
                continue
            if key == "totalAmount" and any(
                marker in container
                for marker in ("fee", "unUsedAmount", "invoicedReceiptAmount", "dtoVersion", "receiptCode")
            ):
                amount = round(amount / 100, 2)
            if amount > 0:
                return amount
    return None


def receipt_available_amount(receipt: dict[str, Any]) -> float | None:
    """Return Huilianyi's remaining reimbursable receipt balance in yuan."""
    for key in ("unUsedAmount", "unusedAmount", "availableAmount"):
        value = receipt.get(key)
        if value in (None, ""):
            continue
        normalized = re.sub(r"[^0-9.,-]", "", str(value)).replace(",", "")
        try:
            amount = float(normalized)
        except ValueError:
            continue
        if key == "unUsedAmount":
            amount /= 100
        return round(amount, 2)
    return None


def infer_hotel_cities(*values: Any) -> list[str]:
    text = " ".join(json.dumps(value, ensure_ascii=False, default=str) for value in values if value)
    return sorted(
        (city for city in HOTEL_CITY_CODES if city in text),
        key=text.index,
    )


def hotel_field_values(
    data: list[dict[str, Any]], cities: list[str], start: str, end: str
) -> list[dict[str, Any]]:
    result = copy.deepcopy(data)
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    duration = float((end_date - start_date).days + 1)
    date_value = json.dumps(
        {
            "startDate": f"{start_date.isoformat()}T00:00:00Z",
            "endDate": f"{end_date.isoformat()}T23:59:59Z",
            "duration": duration,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    for field in result:
        name = field.get("name") or field.get("messageKey")
        if name in {"入住城市", "location"} and cities:
            codes = [HOTEL_CITY_CODES[city] for city in cities if city in HOTEL_CITY_CODES]
            field["value"] = ",".join(codes) if codes else "，".join(cities)
            field["showValue"] = "，".join(cities)
        elif name in {"开始结束日期", "dateCombined"}:
            field["value"] = field["showValue"] = date_value
    return result


def business_code(item: dict[str, Any]) -> str | None:
    return item.get("businessCode") or item.get("applicationBusinessCode") or item.get("code")


def application_oid(item: dict[str, Any]) -> str | None:
    return item.get("applicationOID") or item.get("entityOID") or item.get("oid")


def report_oid(item: dict[str, Any]) -> str | None:
    return item.get("expenseReportOID") or item.get("entityOID") or item.get("oid")


def search_applications(api: Client, size: int = 100) -> list[dict[str, Any]]:
    return unwrap_rows(api.request(f"/api/applications/v4/search?roleType=TENANT&page=0&size={size}", "POST", {}))


def search_reports(api: Client, size: int = 100) -> list[dict[str, Any]]:
    return unwrap_rows(api.request(f"/api/expense/reports/search/my?roleType=TENANT&page=0&size={size}", "POST", {}))


def get_application(api: Client, oid: str) -> dict[str, Any]:
    return api.request(f"/api/application/{oid}?showValue=true")


def get_report(api: Client, oid: str) -> dict[str, Any]:
    return unwrap_row(api.request(f"/api/v3/expense/reports/{oid}"))


def find_application(api: Client, code: str) -> dict[str, Any]:
    for item in search_applications(api):
        if business_code(item) == code:
            oid = application_oid(item)
            if oid:
                return get_application(api, oid)
    raise LookupError(f"Application not found: {code}")


def find_report(api: Client, code: str) -> dict[str, Any]:
    for item in search_reports(api):
        if business_code(item) == code:
            oid = report_oid(item)
            if oid:
                return get_report(api, oid)
    raise LookupError(f"Expense report not found: {code}")


def find_user(api: Client, full_name: str) -> dict[str, Any]:
    value = api.request(
        "/api/users/v3/search?roleType=TENANT&size=20&page=0&keyword=" + urllib.parse.quote(full_name)
    )
    exact = [item for item in unwrap_rows(value) if item.get("fullName") == full_name]
    if len(exact) != 1:
        raise LookupError(f"Expected exactly one user named {full_name!r}; found {len(exact)}")
    return exact[0]


def _field_map(values: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    result = {}
    for field in values or []:
        key = field.get("fieldCode") or field.get("messageKey") or field.get("fieldName")
        if key:
            result[key] = field
    return result


def canonical_expense_type(name: str) -> str:
    return TRAVEL_TYPE_ALIASES.get(name, name)


def application_budget_summary(application: dict[str, Any]) -> dict[str, float]:
    result: dict[str, float] = {}
    for line in (application.get("budgetDetailDTO") or {}).get("budgetDetail") or []:
        name = canonical_expense_type((line.get("expenseType") or {}).get("name") or "")
        if name:
            result[name] = round(result.get(name, 0.0) + float(line.get("amount") or 0), 2)
    return result


def report_expense_summary(invoice_data: dict[str, Any]) -> dict[str, float]:
    result: dict[str, float] = {}
    views = (invoice_data.get("invoiceViewDTOMap") or {}).values()
    for invoice in views:
        name = canonical_expense_type(invoice.get("expenseTypeName") or "")
        if name:
            result[name] = round(result.get(name, 0.0) + float(invoice.get("amount") or 0), 2)
    return result


def application_budget_match(application: dict[str, Any], expense_type_name: str) -> dict[str, Any]:
    name = canonical_expense_type(expense_type_name)
    lines = [
        line for line in (application.get("budgetDetailDTO") or {}).get("budgetDetail") or []
        if canonical_expense_type((line.get("expenseType") or {}).get("name") or "") == name
    ]
    return {
        "expenseType": name,
        "applicationCustomBudgetId": [str(line["id"]) for line in lines if line.get("id") is not None],
        "applicationAmount": round(sum(float(line.get("amount") or 0) for line in lines), 2),
        "budgetLineCount": len(lines),
        "mode": "application-budget" if lines else "manual-expense",
    }


def compare_travel_amounts(application: dict[str, Any], invoice_data: dict[str, Any]) -> dict[str, Any]:
    planned = application_budget_summary(application)
    reimbursed = report_expense_summary(invoice_data)
    invoice_counts: dict[str, int] = {}
    for invoice in (invoice_data.get("invoiceViewDTOMap") or {}).values():
        name = canonical_expense_type(invoice.get("expenseTypeName") or "")
        if name:
            invoice_counts[name] = invoice_counts.get(name, 0) + 1
    categories = []
    for name in sorted(set(planned) | set(reimbursed)):
        delta = round(reimbursed.get(name, 0.0) - planned.get(name, 0.0), 2)
        categories.append({
            "expenseType": name,
            "applicationAmount": planned.get(name, 0.0),
            "reportAmount": reimbursed.get(name, 0.0),
            "difference": delta,
            "invoiceCount": invoice_counts.get(name, 0),
            "coverage": "application-budget" if name in planned else "manual-expense",
        })
    return {
        "application": planned,
        "report": reimbursed,
        "applicationTotal": round(sum(planned.values()), 2),
        "reportTotal": round(sum(reimbursed.values()), 2),
        "amountsEqual": all(not row["difference"] for row in categories),
        "allReportCategoriesCovered": all(row["expenseType"] in planned for row in categories if row["reportAmount"]),
        "categories": categories,
    }


def build_history_model(api: Client, limit: int = 100) -> dict[str, Any]:
    """Read history and model application/report/invoice relationships."""
    applications = []
    known_application_oids = set()
    application_details = {}
    for item in search_applications(api, limit):
        oid = application_oid(item)
        if not oid:
            continue
        detail = get_application(api, oid)
        application_details[oid] = detail
        known_application_oids.add(oid)
        travel = detail.get("travelApplication") or {}
        fields = _field_map(detail.get("custFormValues"))
        applications.append(
            {
                "businessCode": detail.get("businessCode"),
                "applicationOID": oid,
                "status": detail.get("status"),
                "closed": detail.get("closed"),
                "formOID": detail.get("formOID"),
                "createdDate": detail.get("createdDate"),
                "approvalDate": detail.get("approvalDate"),
                "startDate": travel.get("startDate"),
                "endDate": travel.get("endDate"),
                "travelDays": travel.get("travelDays"),
                "participantNum": travel.get("participantNum"),
                "totalAmount": detail.get("totalAmount"),
                "budgetByExpenseType": application_budget_summary(detail),
                "companyOID": (fields.get("field_3917") or {}).get("value"),
                "companyName": (fields.get("field_3917") or {}).get("showValue"),
                "departmentOID": (fields.get("field_0001") or {}).get("value"),
                "departmentName": (fields.get("field_0001") or {}).get("showValue"),
                "agentOID": (fields.get("DLR") or {}).get("value"),
                "agentName": (fields.get("DLR") or {}).get("showValue"),
            }
        )

    reports = []
    for item in search_reports(api, limit):
        oid = report_oid(item)
        if not oid:
            continue
        detail = get_report(api, oid)
        invoice_data = unwrap_row(api.request(f"/api/expense/report/invoices/v2?expenseReportOID={oid}"))
        linked_oid = detail.get("applicationOID")
        comparison = None
        if linked_oid in application_details:
            comparison = compare_travel_amounts(application_details[linked_oid], invoice_data)
        reports.append(
            {
                "businessCode": detail.get("businessCode"),
                "expenseReportOID": oid,
                "status": detail.get("status"),
                "formOID": detail.get("formOID"),
                "createdDate": detail.get("createdDate"),
                "approvalDate": detail.get("approvalDate"),
                "totalAmount": detail.get("totalAmount"),
                "applicationBusinessCode": detail.get("applicationBusinessCode"),
                "applicationOID": linked_oid,
                "linkedApplicationKnown": linked_oid in known_application_oids,
                "linkDTOCount": len(detail.get("expenseReportApplicationDTOS") or []),
                "applicationStartAndEndDateMap": detail.get("applicationStartAndEndDateMap") or {},
                "invoiceCount": len(invoice_data.get("expenseReportInvoices") or []),
                "expenseByType": report_expense_summary(invoice_data),
                "applicationReportComparison": comparison,
                "invoiceGroups": [
                    {
                        "categoryName": group.get("categoryName"),
                        "totalAmount": group.get("totalAmount"),
                        "totalInvoiceAmount": group.get("totalInvoiceAmount"),
                        "count": len(group.get("invoices") or []),
                    }
                    for group in (invoice_data.get("invoiceGroups") or [])
                ],
            }
        )
    return {"applications": applications, "reports": reports}


def _reset_form_values(values: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    result = copy.deepcopy(values or [])
    for item in result:
        for key in ("id", "formValueOID", "bizOID", "createdDate", "lastModifiedDate"):
            if key in item:
                item[key] = None
    return result


def _parse_date(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def application_date_values(start: str | date, end: str | date) -> tuple[str, str, int]:
    """Convert local China business dates to application ISO values."""
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    if end_date < start_date:
        raise ValueError("end date is before start date")
    china = timezone(timedelta(hours=8))
    start_dt = datetime.combine(start_date, dt_time.min, tzinfo=china).astimezone(timezone.utc)
    end_dt = datetime.combine(end_date, dt_time(23, 59), tzinfo=china).astimezone(timezone.utc)
    return (
        start_dt.isoformat(timespec="seconds").replace("+00:00", "Z"),
        end_dt.isoformat(timespec="seconds").replace("+00:00", "Z"),
        (end_date - start_date).days + 1,
    )


def report_date_values(start: str | date, end: str | date) -> tuple[str, str]:
    """HLY report links store local wall-clock values with a Z suffix."""
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    return f"{start_date.isoformat()}T00:00:00Z", f"{end_date.isoformat()}T23:59:00Z"


def build_travel_application_draft(
    template: dict[str, Any],
    agent: dict[str, Any],
    participant: dict[str, Any],
    start: str | date,
    end: str | date,
    expense_plan: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a travel application whose budget mirrors classified travel expenses."""
    if not expense_plan:
        raise ValueError("travel application requires a non-empty expense plan")
    start_iso, end_iso, travel_days = application_date_values(start, end)
    fields = _reset_form_values(template.get("custFormValues"))
    for field in fields:
        code = field.get("fieldCode")
        if code == "DLR":
            field["value"] = agent["userOID"]
            field["showValue"] = agent["fullName"]
        elif code == "KSRQ":
            field["value"] = field["showValue"] = start_iso
        elif code == "JSRQ":
            field["value"] = field["showValue"] = end_iso
        elif code == "field_0004":
            people = [
                {
                    "userOID": participant["userOID"],
                    "fullName": participant["fullName"],
                    "participantOID": participant["userOID"],
                }
            ]
            field["value"] = field["showValue"] = json.dumps(people, ensure_ascii=False, separators=(",", ":"))

    travel = copy.deepcopy(template.get("travelApplication") or {})
    for key in ("id", "applicationOID", "businessCode", "createdDate", "lastModifiedDate"):
        if key in travel:
            travel[key] = None
    budget_templates = {}
    for existing in (template.get("budgetDetailDTO") or {}).get("budgetDetail") or []:
        name = canonical_expense_type((existing.get("expenseType") or {}).get("name") or "")
        if name and name not in budget_templates:
            budget_templates[name] = existing
    merged_plan: dict[str, float] = {}
    for requested in expense_plan:
        name = canonical_expense_type(str(requested.get("expenseType") or ""))
        amount = round(float(requested.get("amount") or 0), 2)
        if not name or amount <= 0:
            raise ValueError("every travel expense plan line needs expenseType and a positive amount")
        merged_plan[name] = round(merged_plan.get(name, 0.0) + amount, 2)
    missing = sorted(set(merged_plan) - set(budget_templates))
    if missing:
        raise LookupError("application template lacks budget types: " + ", ".join(missing))

    budget_lines = []
    for name, amount in merged_plan.items():
        line = copy.deepcopy(budget_templates[name])
        for key in ("id", "budgetOID", "applicationOID", "createdDate", "lastModifiedDate"):
            if key in line:
                line[key] = None
        line.update(
            {"amount": amount, "baseCurrencyAmount": amount, "taxExcBaseCurrencyAmount": amount}
        )
        for apportionment in line.get("apportionmentDTOList") or []:
            for key in (
                "id", "apportionmentOID", "entityOID", "createdDate", "lastModifiedDate",
                "expenseBudgetOID",
            ):
                if key in apportionment:
                    apportionment[key] = None
            apportionment.update(
                {"amount": amount, "baseCurrencyAmount": amount,
                 "reimbursementAmount": 0.0, "baseReimbursementAmount": 0.0}
            )
            for item in apportionment.get("costCenterItems") or []:
                item["entityOID"] = None
                item["costCenterItemID"] = None
        budget_lines.append(line)
    total_budget = round(sum(merged_plan.values()), 2)

    travel.update(
        {
            "applicationOID": None,
            "startDate": start_iso,
            "endDate": end_iso,
            "travelDays": travel_days,
            "participantNum": 1,
            "bookingClerkOID": participant["userOID"],
            "bookingClerkName": participant["fullName"],
            "hotelBookingClerkOID": participant["userOID"],
            "hotelBookingClerkName": participant["fullName"],
            "trainBookingClerkOID": participant["userOID"],
            "trainBookingClerkName": participant["fullName"],
            "baseCurrencyAmount": total_budget,
            "totalBudget": total_budget,
            "travelItinerarys": [],
            "travelItineraryBookingClerkDTOs": [],
        }
    )
    participant_oid = participant["userOID"]
    person = {
        "applicationOID": None,
        "participantOID": participant_oid,
        "userOID": participant_oid,
        "fullName": participant["fullName"],
        "companyOID": participant.get("companyOID"),
        "closed": 0,
        "type": 1,
        "deleted": False,
    }
    return {
        "applicationOID": None,
        "formOID": template["formOID"],
        "applicantOID": participant_oid,
        "companyOID": template.get("companyOID"),
        "corporationOID": template.get("corporationOID"),
        "departmentOID": participant.get("departmentOID") or template.get("departmentOID"),
        "custFormValues": fields,
        "travelApplication": travel,
        "applicationParticipant": {"applicationOID": None, "participantOID": participant_oid},
        "applicationParticipants": [person],
        "budgetDetailDTO": {"amount": total_budget, "budgetDetail": budget_lines},
        "totalAmount": total_budget,
        "baseCurrencyAmount": total_budget,
        "taxExcBaseCurrencyAmount": total_budget,
    }


_REPORT_ID_KEYS = (
    "expenseReportOID",
    "entityOID",
    "applicationOID",
    "businessCode",
    "id",
    "expenseReportId",
    "applicationId",
    "createdBy",
    "createdName",
    "createdDate",
    "lastModifiedBy",
    "lastModifiedDate",
    "approvalDate",
    "auditApprovalDate",
    "bookDate",
    "bookDateWithoutZone",
    "attachmentOID",
)


def _fresh_report(template: dict[str, Any]) -> dict[str, Any]:
    row = copy.deepcopy(template)
    for key in _REPORT_ID_KEYS:
        if key in row:
            row[key] = None
    for key in (
        "expenseReportDetailDTOList",
        "expenseReportDetails",
        "expenseReportInvoices",
        "expenseReportLabels",
        "approvalHistorys",
        "approvalSummaries",
        "paymentLines",
        "prepaymentLines",
        "loans",
        "attachments",
    ):
        if key in row:
            row[key] = []
    for key, value in list(row.items()):
        if isinstance(value, (int, float)) and "amount" in key.lower():
            row[key] = 0.0
    row.update(
        {
            "status": DRAFT_STATUS,
            "custFormValues": _reset_form_values(row.get("custFormValues")),
            "recalculateSubsidy": False,
            "isDateCombinedUTC": False,
            "showValidatePopUp": True,
            "containsInvoice": False,
            "containsPaymentLine": False,
            "containsSubsidy": False,
        }
    )
    return row


def build_personal_report_draft(template: dict[str, Any], title: str) -> dict[str, Any]:
    row = _fresh_report(template)
    row["expenseReportApplicationDTOS"] = []
    row["applicationStartAndEndDateMap"] = {}
    row["title"] = title
    for field in row["custFormValues"]:
        if field.get("messageKey") == "title":
            field["value"] = field["name"] = field["showValue"] = title
    return row


def build_travel_report_draft(
    template: dict[str, Any], target: dict[str, Any], start: str | date, end: str | date
) -> dict[str, Any]:
    if target.get("status") != APPROVED_APPLICATION_STATUS:
        raise ValueError("travel report target application is not approved (status 1003)")
    if bool(target.get("closed")):
        raise ValueError("travel report target application is closed")
    row = _fresh_report(template)
    target_oid = target["applicationOID"]
    target_code = target["businessCode"]
    start_iso, end_iso = report_date_values(start, end)
    row["applicationOID"] = target_oid
    row["applicationBusinessCode"] = target_code
    row["applicationFormOID"] = target["formOID"]
    row["applicationStartAndEndDateMap"] = {
        f"{target_oid}+start_date": start_iso,
        f"{target_oid}+end_date": end_iso,
    }
    dto = copy.deepcopy(template["expenseReportApplicationDTOS"][0])
    for key in ("id", "expenseReportOID", "createdDate", "lastModifiedDate", "createdBy", "lastModifiedBy"):
        if key in dto:
            dto[key] = None
    dto.update(
        {
            "applicationOID": target_oid,
            "applicationBusinessCode": target_code,
            "applicationFormOID": target["formOID"],
            "travelStartDate": start_iso,
            "travelEndDate": end_iso,
            "travelDays": (target.get("travelApplication") or {}).get("travelDays"),
            "participantNum": (target.get("travelApplication") or {}).get("participantNum"),
        }
    )
    related = dto.get("relatedSimpleApplicationInfo") or {}
    related.update(
        {
            "businessCode": target_code,
            "travelStartDate": start_iso,
            "travelEndDate": end_iso,
            "travelDays": (target.get("travelApplication") or {}).get("travelDays"),
            "totalAmount": target.get("totalAmount", 0.0),
            "loanableAmount": target.get("totalAmount", 0.0),
            "referenceReportsCode": [],
            "closed": False,
        }
    )
    dto["relatedSimpleApplicationInfo"] = related
    row["expenseReportApplicationDTOS"] = [dto]
    for field in row["custFormValues"]:
        if field.get("fieldCode") == "field_7800":
            field["value"] = field["showValue"] = start_iso
        elif field.get("fieldCode") == "field_4242":
            field["value"] = field["showValue"] = end_iso
    return row


def save_application_draft(api: Client, payload: dict[str, Any]) -> dict[str, Any]:
    return unwrap_row(api.request("/api/travel/applications/draft", "POST", payload))


def save_report_draft(api: Client, payload: dict[str, Any]) -> dict[str, Any]:
    return unwrap_row(api.request("/api/expense/reports/custom/form/draft?corporateFlag=false", "POST", payload))


def available_expense_types(api: Client, report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    payload = {
        "companyOID": report.get("docCompanyOID"),
        "formOID": report.get("formOID"),
        "expenseReportOID": report.get("expenseReportOID"),
        "userOID": report.get("applicantOID"),
        "roleType": "TENANT",
    }
    result = {}
    for item in unwrap_rows(api.request("/api/expense/type/byUser", "POST", payload)):
        name = item.get("name") or item.get("expenseTypeName")
        if name:
            result[name] = item
    return result


def _first_receipt(value: Any) -> dict[str, Any]:
    row = unwrap_row(value)
    receipts = row.get("receiptList") or row.get("receipts") or []
    if not receipts:
        raise RuntimeError("OCR returned no receipt")
    return receipts[0]


def _verified_receipt(value: Any) -> dict[str, Any]:
    values = unwrap_rows(value)
    if not values and isinstance(value, list):
        values = value
    if not values:
        raise RuntimeError("receipt verification returned no receipt")
    first = values[0]
    return first.get("invoiceInfo") or first


def build_v5_body(tax_result: dict[str, Any], common: dict[str, Any]) -> dict[str, Any]:
    """Build the final creator request and discard tax's provisional identity."""
    body = {key: value for key, value in tax_result.items() if value is not None}
    body.update(common)
    body.pop("invoiceOID", None)
    body["valid"] = True
    return body


def report_travel_date_range(api: Client, report: dict[str, Any]) -> tuple[str, str]:
    application_oid_value = report.get("applicationOID")
    date_map = report.get("applicationStartAndEndDateMap") or {}
    if application_oid_value:
        start = date_map.get(f"{application_oid_value}+start_date")
        end = date_map.get(f"{application_oid_value}+end_date")
        if start and end:
            return str(start)[:10], str(end)[:10]
        application = get_application(api, application_oid_value)
        travel = application.get("travelApplication") or {}
        china = timezone(timedelta(hours=8))
        parsed = []
        for value in (travel.get("startDate"), travel.get("endDate")):
            if not value:
                break
            parsed.append(
                datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                .astimezone(china)
                .date()
                .isoformat()
            )
        if len(parsed) == 2:
            return parsed[0], parsed[1]
    raise ValueError("hotel expense requires the linked report travel date range")


def add_invoice(
    api: Client,
    gateway: Client,
    report: dict[str, Any],
    file_path: str | Path,
    expense_type_name: str,
    amount: float,
    attachment_paths: list[str | Path] | None = None,
    hotel_cities: list[str] | None = None,
) -> dict[str, Any]:
    """Upload, recognize, verify, classify, and bind one invoice to a draft."""
    if report.get("status") != DRAFT_STATUS:
        raise ValueError("invoices may only be added to an editing draft (status 1001)")
    invoice_path = validate_upload_file(file_path)
    attachment_files = [validate_upload_file(path) for path in (attachment_paths or [])]
    if attachment_files and expense_type_name != "过路费":
        raise ValueError("supporting toll documents may only be attached to 过路费")
    report_oid_value = report["expenseReportOID"]
    types = available_expense_types(api, report)
    if expense_type_name not in types:
        raise LookupError(f"expense type not available: {expense_type_name}")
    expense_type = types[expense_type_name]
    expense_type_id = str(expense_type.get("expenseTypeId") or expense_type.get("id"))
    expense_type_oid = expense_type.get("expenseTypeOID") or expense_type.get("oid")
    owner_oid = report["applicantOID"]
    budget_match = {
        "expenseType": canonical_expense_type(expense_type_name),
        "applicationCustomBudgetId": [],
        "applicationAmount": 0.0,
        "budgetLineCount": 0,
        "mode": "personal-expense" if not report.get("applicationOID") else "manual-expense",
    }
    if report.get("applicationOID"):
        application = get_application(api, report["applicationOID"])
        budget_match = application_budget_match(application, expense_type_name)

    upload = api.upload_invoice(invoice_path)
    ocr = gateway.request(
        "/receipt/api/receipt/ocr/v3?roleType=TENANT&client=WEB&isInternationalOCR=false"
        f"&districtCode=&reportOID={urllib.parse.quote(report_oid_value)}",
        "POST",
        [{"oriAttachment": upload, "attachmentType": "INVOICE_IMAGES", "autoCountSent": "TRUE"}],
    )
    receipt = _first_receipt(ocr)
    receipt["pdfUrl"] = upload.get("fileURL") or upload.get("downloadUrl")
    verified = gateway.request(
        "/receipt/api/receipt/verify/batch?roleType=TENANT", "POST", [{"invoiceInfo": receipt}]
    )
    receipt = _verified_receipt(verified)
    receipt["pdfUrl"] = receipt.get("pdfUrl") or upload.get("fileURL") or upload.get("downloadUrl")
    recognized_amount = recognized_receipt_amount(receipt)
    available_amount = receipt_available_amount(receipt)
    if available_amount is not None and available_amount <= 0:
        raise ValueError(
            "invoice has no reimbursable balance; it may already be locked or reimbursed in another report"
        )
    if amount is None:
        if recognized_amount is None:
            raise ValueError("invoice amount is unavailable after OCR/verification; confirm it manually")
        amount = recognized_amount
    amount = round(float(amount), 2)
    if recognized_amount is not None and abs(amount - recognized_amount) > 0.01:
        raise ValueError(
            f"provided amount {amount:.2f} differs from verified invoice amount {recognized_amount:.2f}"
        )
    if available_amount is not None and amount - available_amount > 0.01:
        raise ValueError(
            f"invoice amount {amount:.2f} exceeds remaining reimbursable balance {available_amount:.2f}"
        )

    # Incremental dedup: if this invoice number already exists in the report, skip it.
    invoice_no = str(receipt.get("invoiceNumber") or receipt.get("invoiceCode") or "").strip()
    if invoice_no and invoice_no in existing_invoice_numbers(api, report_oid_value):
        return {
            "duplicate": True,
            "invoiceNumber": invoice_no,
            "invoiceOID": receipt.get("receiptOID"),
            "receiptOID": receipt.get("receiptOID"),
            "expenseType": expense_type_name,
            "amount": float(amount),
            "message": f"发票号 {invoice_no} 已存在于该报销单,跳过(不重复落账)",
        }

    defaults_value = gateway.request(
        "/invoice/api/invoice/defaults?roleType=TENANT&isDateCombinedUTC=false",
        "POST",
        {"expenseTypeId": expense_type_id, "receipts": [receipt]},
    )
    defaults = unwrap_row(defaults_value)
    data = copy.deepcopy(defaults.get("data") or []) if isinstance(defaults, dict) else []
    resolved_hotel_cities: list[str] = []
    if expense_type_name == "酒店":
        resolved_hotel_cities = list(dict.fromkeys(hotel_cities or infer_hotel_cities(
            invoice_path.name, receipt
        )))
        if not resolved_hotel_cities:
            raise ValueError("cannot infer hotel city; pass --hotel-city explicitly")
        start, end = report_travel_date_range(api, report)
        data = hotel_field_values(data, resolved_hotel_cities, start, end)
    attachments = [api.upload_attachment(path) for path in attachment_files]
    apportionment = unwrap_rows(api.request(
        "/api/expense/default/apportionment",
        "POST",
        {
            "expenseReportOID": report_oid_value,
            "expenseTypeId": expense_type_id,
            "amount": amount,
            "currency": "CNY",
            "ownerOID": owner_oid,
            "merge": True,
            "applicationCustomBudgetId": budget_match["applicationCustomBudgetId"],
            "prepaymentLineIdList": [],
            "paymentCompanyOID": report.get("companyOID"),
        },
    ))
    common = {
        "expenseReportOID": report_oid_value,
        "ownerOID": owner_oid,
        "expenseTypeId": expense_type_id,
        "expenseTypeOID": expense_type_oid,
        "expenseTypeName": expense_type_name,
        "expenseTypeIconName": expense_type.get("iconName") or expense_type.get("expenseTypeIconName"),
        "currencyCode": "CNY",
        "invoiceCurrencyCode": "CNY",
        "amount": float(amount),
        "originalAmount": float(amount),
        "currencyPrecision": 2,
        "receiptList": [receipt],
        "receipts": [receipt],
        "withReceipt": True,
        "valid": True,
        "attachments": attachments,
        "data": data,
        "expenseApportion": apportionment,
    }
    tax_body = dict(defaults) if isinstance(defaults, dict) else {}
    tax_body.update(common)
    tax_result = unwrap_row(
        gateway.request("/invoice/api/invoice/tax/amount/by/receipts?roleType=TENANT", "POST", tax_body)
    )
    v5_body = build_v5_body(tax_result, common)
    query = (
        f"/invoice/api/v5/invoices?hlyRequestID=agent-{int(time.time() * 1000)}&roleType=TENANT"
        "&isDateCombinedUTC=false&utcTime=true&recalculatePolicy=false&shieldTax=false&distrit=true"
        "&recalculateDeductible=true&needValidateExpBaseAmountOverReceipt=true"
    )
    created = unwrap_row(gateway.request(query, "POST", v5_body))
    return {
        "invoiceOID": created.get("invoiceOID"),
        "receiptOID": receipt.get("receiptOID"),
        "receiptId": receipt.get("id"),
        "expenseType": expense_type_name,
        "amount": float(amount),
        "recognizedAmount": recognized_amount,
        "availableAmount": available_amount,
        "budgetMatch": budget_match,
        "attachments": [item.get("fileName") for item in attachments],
        "hotelCities": resolved_hotel_cities,
    }


def _receipt_list(value: Any) -> list[dict[str, Any]]:
    row = unwrap_row(value)
    if isinstance(row, dict):
        receipts = row.get("receiptList") or row.get("receipts") or []
        if receipts:
            return receipts
    return unwrap_rows(value)


def _verified_receipts(value: Any) -> list[dict[str, Any]]:
    rows = unwrap_rows(value)
    if not rows and isinstance(value, list):
        rows = value
    return [row.get("invoiceInfo") or row for row in rows]


def add_invoice_batch(
    api: Client,
    gateway: Client,
    report: dict[str, Any],
    items: list[dict[str, Any]],
    expense_type_name: str,
    attachment_paths: list[str | Path] | None = None,
    hotel_cities: list[str] | None = None,
    upload_workers: int = 4,
) -> dict[str, Any]:
    """Bind one pre-classified category as one multi-receipt expense line.

    Originals still use one multipart upload each, but uploads run concurrently;
    OCR, verification, defaults, tax, and V5 creation run once for the category.
    """
    if report.get("status") != DRAFT_STATUS:
        raise ValueError("invoices may only be added to an editing draft (status 1001)")
    if not items:
        raise ValueError("invoice category contains no files")
    paths = [validate_upload_file(item["path"]) for item in items]
    attachments_to_upload = [validate_upload_file(path) for path in (attachment_paths or [])]
    if attachments_to_upload and expense_type_name != "过路费":
        raise ValueError("supporting toll documents may only be attached to 过路费")

    report_oid_value = report["expenseReportOID"]
    types = available_expense_types(api, report)
    if expense_type_name not in types:
        raise LookupError(f"expense type not available: {expense_type_name}")
    expense_type = types[expense_type_name]
    expense_type_id = str(expense_type.get("expenseTypeId") or expense_type.get("id"))
    expense_type_oid = expense_type.get("expenseTypeOID") or expense_type.get("oid")
    owner_oid = report["applicantOID"]

    budget_match = {
        "expenseType": canonical_expense_type(expense_type_name),
        "applicationCustomBudgetId": [],
        "applicationAmount": 0.0,
        "budgetLineCount": 0,
        "mode": "personal-expense" if not report.get("applicationOID") else "manual-expense",
    }
    if report.get("applicationOID"):
        budget_match = application_budget_match(
            get_application(api, report["applicationOID"]), expense_type_name
        )

    workers = max(1, min(int(upload_workers), len(paths)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        uploads = list(pool.map(api.upload_invoice, paths))
    ocr = gateway.request(
        "/receipt/api/receipt/ocr/v3?roleType=TENANT&client=WEB&isInternationalOCR=false"
        f"&districtCode=&reportOID={urllib.parse.quote(report_oid_value)}",
        "POST",
        [
            {"oriAttachment": upload, "attachmentType": "INVOICE_IMAGES", "autoCountSent": "TRUE"}
            for upload in uploads
        ],
    )
    receipts = _receipt_list(ocr)
    if len(receipts) != len(items):
        raise RuntimeError(f"OCR returned {len(receipts)} receipts for {len(items)} files")
    for receipt, upload in zip(receipts, uploads):
        receipt["pdfUrl"] = upload.get("fileURL") or upload.get("downloadUrl")
    verified = _verified_receipts(
        gateway.request(
            "/receipt/api/receipt/verify/batch?roleType=TENANT",
            "POST",
            [{"invoiceInfo": receipt} for receipt in receipts],
        )
    )
    if len(verified) != len(items):
        raise RuntimeError(f"verification returned {len(verified)} receipts for {len(items)} files")
    for receipt, upload in zip(verified, uploads):
        receipt["pdfUrl"] = receipt.get("pdfUrl") or upload.get("fileURL") or upload.get("downloadUrl")

    existing_numbers = existing_invoice_numbers(api, report_oid_value)
    active = []
    results = []
    for item, path, receipt in zip(items, paths, verified):
        recognized = recognized_receipt_amount(receipt)
        available = receipt_available_amount(receipt)
        requested = item.get("amount")
        amount = round(float(requested if requested is not None else recognized), 2) if requested is not None or recognized is not None else None
        if amount is None:
            raise ValueError(f"invoice amount is unavailable after verification: {path.name}")
        if recognized is not None and abs(amount - recognized) > 0.01:
            raise ValueError(
                f"provided amount {amount:.2f} differs from verified invoice amount {recognized:.2f}: {path.name}"
            )
        invoice_number = str(
            receipt.get("invoiceNumber") or receipt.get("invoiceCode") or receipt.get("billingNo") or ""
        ).strip()
        closed = (
            receipt.get("reimburseStatus") == "INVOICE_REIMBURSE_CLOSURE"
            or available is not None and available <= 0
        )
        duplicate = bool(invoice_number and invoice_number in existing_numbers)
        status = "skipped_duplicate" if duplicate else "skipped_closed" if closed else "ready"
        result = {
            "path": str(path),
            "invoiceNumber": invoice_number,
            "receiptOID": receipt.get("receiptOID"),
            "amount": amount,
            "recognizedAmount": recognized,
            "availableAmount": available,
            "status": status,
        }
        results.append(result)
        if status == "ready":
            if available is not None and amount - available > 0.01:
                raise ValueError(
                    f"invoice amount {amount:.2f} exceeds remaining balance {available:.2f}: {path.name}"
                )
            active.append((path, receipt, amount, result))
    if not active:
        return {
            "invoiceOID": None, "expenseType": expense_type_name, "amount": 0.0,
            "receiptCount": 0, "items": results, "budgetMatch": budget_match,
        }

    active_receipts = [receipt for _, receipt, _, _ in active]
    amount = round(sum(value for _, _, value, _ in active), 2)
    defaults_value = gateway.request(
        "/invoice/api/invoice/defaults?roleType=TENANT&isDateCombinedUTC=false",
        "POST",
        {"expenseTypeId": expense_type_id, "receipts": active_receipts},
    )
    defaults = unwrap_row(defaults_value)
    data = copy.deepcopy(defaults.get("data") or []) if isinstance(defaults, dict) else []
    resolved_hotel_cities: list[str] = []
    if expense_type_name == "酒店":
        resolved_hotel_cities = list(dict.fromkeys(hotel_cities or infer_hotel_cities(paths, active_receipts)))
        if not resolved_hotel_cities:
            raise ValueError("cannot infer hotel city; pass --hotel-city explicitly")
        start, end = report_travel_date_range(api, report)
        data = hotel_field_values(data, resolved_hotel_cities, start, end)
    attachments = [api.upload_attachment(path) for path in attachments_to_upload]
    apportionment = unwrap_rows(api.request(
        "/api/expense/default/apportionment",
        "POST",
        {
            "expenseReportOID": report_oid_value,
            "expenseTypeId": expense_type_id,
            "amount": amount,
            "currency": "CNY",
            "ownerOID": owner_oid,
            "merge": True,
            "applicationCustomBudgetId": budget_match["applicationCustomBudgetId"],
            "prepaymentLineIdList": [],
            "paymentCompanyOID": report.get("companyOID"),
        },
    ))
    common = {
        "expenseReportOID": report_oid_value,
        "ownerOID": owner_oid,
        "expenseTypeId": expense_type_id,
        "expenseTypeOID": expense_type_oid,
        "expenseTypeName": expense_type_name,
        "expenseTypeIconName": expense_type.get("iconName") or expense_type.get("expenseTypeIconName"),
        "currencyCode": "CNY", "invoiceCurrencyCode": "CNY",
        "amount": amount, "originalAmount": amount, "currencyPrecision": 2,
        "receiptList": active_receipts, "receipts": active_receipts,
        "withReceipt": True, "valid": True,
        "attachments": attachments, "data": data, "expenseApportion": apportionment,
    }
    tax_body = dict(defaults) if isinstance(defaults, dict) else {}
    tax_body.update(common)
    tax_result = unwrap_row(gateway.request(
        "/invoice/api/invoice/tax/amount/by/receipts?roleType=TENANT", "POST", tax_body
    ))
    v5_body = build_v5_body(tax_result, common)
    query = (
        f"/invoice/api/v5/invoices?hlyRequestID=agent-{int(time.time() * 1000)}&roleType=TENANT"
        "&isDateCombinedUTC=false&utcTime=true&recalculatePolicy=false&shieldTax=false&distrit=true"
        "&recalculateDeductible=true&needValidateExpBaseAmountOverReceipt=true"
    )
    created = unwrap_row(gateway.request(query, "POST", v5_body))
    for _, _, _, result in active:
        result["status"] = "bound"
    return {
        "invoiceOID": created.get("invoiceOID"), "expenseType": expense_type_name,
        "amount": amount, "receiptCount": len(active_receipts), "items": results,
        "budgetMatch": budget_match, "attachments": [item.get("fileName") for item in attachments],
        "hotelCities": resolved_hotel_cities,
    }


def _manual_expense_template(api: Client, expense_type_name: str) -> dict[str, Any]:
    for item in search_reports(api):
        oid = report_oid(item)
        if not oid:
            continue
        invoice_data = unwrap_row(api.request(f"/api/expense/report/invoices/v2?expenseReportOID={oid}"))
        for view in (invoice_data.get("invoiceViewDTOMap") or {}).values():
            if (
                view.get("expenseTypeName") == expense_type_name
                and not view.get("withReceipt")
                and view.get("invoiceStatus") in {"FINISHED", "SUBMITTED"}
                and view.get("invoiceSaveStatus") != 100
            ):
                invoice_oid_value = view.get("invoiceOID") or view.get("entityOID")
                if invoice_oid_value:
                    return copy.deepcopy(unwrap_row(api.request(
                        f"/api/invoices/{invoice_oid_value}?isDateCombinedUTC=false"
                    )))
                return copy.deepcopy(view)
    return {}


def validate_manual_expense_values(
    expense_type_name: str, amount: float, field_values: dict[str, Any]
) -> list[str]:
    if expense_type_name != "出差补贴":
        return []
    raw_days = str(field_values.get("补贴天数", "")).strip()
    if not raw_days or not re.fullmatch(r"[1-9]\d*", raw_days):
        raise ValueError("出差补贴 requires a positive integer 补贴天数")
    expected = int(raw_days) * 100
    if round(float(amount), 2) != float(expected):
        return [
            f"出差补贴按通用默认公式为 补贴天数 × 100（参考金额 {expected:.2f}）；"
            "当前金额不同，请按本公司制度或用户确认结果填报"
        ]
    return []


def _expense_views(api: Client, report_oid_value: str) -> list[dict[str, Any]]:
    value = unwrap_row(api.request(f"/api/expense/report/invoices/v2?expenseReportOID={report_oid_value}"))
    return list((value.get("invoiceViewDTOMap") or {}).values())


def _find_expense_view(
    api: Client, report_oid_value: str, identity: str
) -> dict[str, Any] | None:
    for view in _expense_views(api, report_oid_value):
        if identity in {
            str(view.get("entityOID") or ""),
            str(view.get("invoiceOID") or ""),
            str(view.get("expenseCode") or ""),
        }:
            return view
    return None


def _expense_save_fingerprint(view: dict[str, Any] | None) -> tuple[Any, ...] | None:
    if not view:
        return None
    return (
        view.get("invoiceStatus"),
        view.get("invoiceSaveStatus"),
        view.get("lastModifiedDate"),
        tuple(sorted((label.get("type"), label.get("name")) for label in view.get("invoiceLabels") or [])),
    )


def complete_manual_apportionment(
    rows: list[dict[str, Any]],
    report: dict[str, Any],
    template: dict[str, Any],
    expense_type_id: str,
    amount: float | None,
) -> list[dict[str, Any]]:
    """Fill the client-side fields omitted by the default-apportionment API."""
    owner_job = template.get("ownerJob") or {}
    company_oid = report.get("docCompanyOID") or template.get("companyOID")
    company_id = template.get("companyID")
    company_name = report.get("docCompanyName")
    company_code = report.get("docCompanyCode")
    for row in rows:
        row.update({
            "expenseTypeId": expense_type_id,
            "currency": "CNY",
            "amount": amount,
            "baseCurrencyAmount": amount,
            "relevantPerson": report.get("applicantOID"),
            "personName": report.get("applicantName"),
            "personEmployeeID": owner_job.get("employeeId"),
            "companyId": company_id,
            "apportionmentCompanyOID": company_oid,
            "apportionmentCompanyName": company_name,
            "apportionmentCompanyCode": company_code,
            "originTaxAmount": 0.0,
            "baseTaxAmount": 0.0,
            "defaultApportion": True,
            "isEditable": True,
            "proportion": 1.0,
        })
    return rows


def wait_for_expense_save(
    api: Client,
    report_oid_value: str,
    identity: str,
    previous_fingerprint: tuple[Any, ...] | None = None,
    timeout_seconds: float = 45,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last = None
    while time.monotonic() < deadline:
        view = _find_expense_view(api, report_oid_value, identity)
        if view:
            last = view
            fingerprint = _expense_save_fingerprint(view)
            if previous_fingerprint is None or fingerprint != previous_fingerprint:
                labels = view.get("invoiceLabels") or []
                async_error = any(
                    label.get("type") == "INVOICE_ASYNC_ERROR" or label.get("name") == "费用保存失败"
                    for label in labels
                )
                if async_error or view.get("invoiceSaveStatus") == 100:
                    raise RuntimeError("expense asynchronous save failed")
                if (
                    view.get("invoiceStatus") in {"FINISHED", "SUBMITTED"}
                    and view.get("invoiceSaveStatus") in {None, 102}
                ):
                    return view
        time.sleep(1)
    status = {
        "invoiceStatus": (last or {}).get("invoiceStatus"),
        "invoiceSaveStatus": (last or {}).get("invoiceSaveStatus"),
        "labels": [label.get("name") for label in (last or {}).get("invoiceLabels") or []],
    }
    raise TimeoutError(f"expense did not reach FINISHED state: {status}")


def add_manual_expense(
    api: Client,
    gateway: Client,
    report: dict[str, Any],
    expense_type_name: str,
    amount: float,
    occurred_date: str | date,
    field_values: dict[str, Any],
    wait_timeout_seconds: float = 45,
) -> dict[str, Any]:
    """Create a no-receipt manual expense and bind it to an editing report."""
    if report.get("status") != DRAFT_STATUS:
        raise ValueError("manual expenses may only be added to an editing draft (status 1001)")
    types = available_expense_types(api, report)
    if expense_type_name not in types:
        raise LookupError(f"expense type not available: {expense_type_name}")
    expense_type = types[expense_type_name]
    if expense_type.get("invoiceRequired") or expense_type.get("pasteInvoiceNeeded"):
        raise ValueError(f"expense type requires a receipt: {expense_type_name}")
    if not expense_type.get("isAbleToCreatedManually", True):
        raise ValueError(f"expense type cannot be created manually: {expense_type_name}")
    amount = round(float(amount), 2)
    if amount <= 0:
        raise ValueError("manual expense amount must be positive")
    policy_warnings = validate_manual_expense_values(expense_type_name, amount, field_values)

    budget_match = {
        "expenseType": canonical_expense_type(expense_type_name),
        "applicationCustomBudgetId": [], "applicationAmount": 0.0,
        "budgetLineCount": 0,
        "mode": "personal-expense" if not report.get("applicationOID") else "manual-expense",
    }
    if report.get("applicationOID"):
        budget_match = application_budget_match(
            get_application(api, report["applicationOID"]), expense_type_name
        )
    expense_type_id = str(expense_type.get("expenseTypeId") or expense_type.get("id"))
    apportionment = unwrap_rows(api.request(
        "/api/expense/default/apportionment", "POST", {
            "expenseReportOID": report["expenseReportOID"],
            "expenseTypeId": expense_type_id,
            "amount": amount, "currency": "CNY", "ownerOID": report["applicantOID"],
            "merge": True,
            "applicationCustomBudgetId": budget_match["applicationCustomBudgetId"],
            "prepaymentLineIdList": [], "paymentCompanyOID": report.get("companyOID"),
        }
    ))
    payload = _manual_expense_template(api, expense_type_name)
    if not payload:
        raise LookupError(f"no historical no-receipt template found: {expense_type_name}")
    # Historical FINISHED DTOs may have lost their job context.  The web flow
    # uses the current report applicant's job, and omitting it causes the later
    # asynchronous save worker to reject an otherwise accepted request.
    payload["ownerJobId"] = report.get("applicantJobId") or payload.get("ownerJobId")
    owner_job = payload.get("ownerJob") or {}
    apportionment = complete_manual_apportionment(
        apportionment, report, payload, expense_type_id, amount
    )
    data = payload.get("data") or []
    for field in data:
        key = field.get("name") or field.get("messageKey")
        if field.get("fieldType") == "ATTACHMENTS":
            field["value"] = field["showValue"] = ""
        elif key in field_values:
            raw_value = field_values[key]
            if raw_value is None or str(raw_value).strip() == "":
                field["value"] = None
                field["showValue"] = ""
            else:
                field["value"] = field["showValue"] = str(raw_value)
        else:
            field["value"] = field["showValue"] = ""
        if field.get("mappedColumnId") == 111:
            payload["stringCol1"] = field.get("value") or None
    local_date = _parse_date(occurred_date)
    china = timezone(timedelta(hours=8))
    created = datetime.combine(local_date, dt_time.min, tzinfo=china).astimezone(timezone.utc)
    identity_keys = (
        "id", "invoiceOID", "entityOID", "expenseReportInvoiceOID", "expenseCode",
    )
    for key in identity_keys + (
        "expenseReportOID",
        "createTime", "lastModifiedDate", "invoiceLabels", "invoiceLabelDTOS", "approvalOperates",
        "paymentScheduleId", "referenceId", "applicationNumber", "applicationTitle",
        "invoiceSaveStatus", "invoiceStatus", "invoiceStatusId",
    ):
        payload.pop(key, None)
    payload.update({
        "expenseReportOID": report["expenseReportOID"],
        "ownerOID": report["applicantOID"], "userOID": report["applicantOID"],
        "reimbursementUserOID": report["applicantOID"],
        "expenseTypeId": expense_type_id,
        "expenseTypeOID": expense_type.get("expenseTypeOID") or expense_type.get("oid"),
        "expenseTypeName": expense_type_name,
        "expenseTypeCode": expense_type.get("code"),
        "expenseTypeIconName": expense_type.get("iconName"),
        "classificationCode": expense_type.get("classificationCode"),
        "expenseTypeSubsidyType": expense_type.get("subsidyType", 0),
        "amount": amount, "originalAmount": amount,
        "currencyCode": "CNY", "invoiceCurrencyCode": "CNY",
        "createdDate": created.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "currencyDate": f"{local_date.isoformat()} 00:00:00",
        "companyOID": report.get("docCompanyOID") or payload.get("companyOID"),
        "companyID": payload.get("companyID"),
        "paymentCompanyOID": None, "paymentType": 1001,
        "withReceipt": False, "receiptList": [], "receipts": [],
        "attachments": [], "data": data, "expenseApportion": apportionment,
        "comment": "", "valid": False, "createInvoice": True,
        "applicationList": [], "relatedApplicationItineraryBudgetVOList": None,
    })
    for key in (
        "nonVATinclusiveAmount", "nonVatBaseAmount", "originalApprovedNonVat",
        "baseApprovedNonVat", "actualCurrencyAmount", "baseAmount", "orderAmount",
        "expenseAmount", "expenseAmortiseAmount",
    ):
        payload[key] = amount
    validation = unwrap_row(
        gateway.request("/invoice/api/validate/invoice/async?roleType=TENANT", "POST", payload)
    )
    if isinstance(validation, dict) and validation.get("isError"):
        raise ValueError(
            "manual expense preflight failed; no expense was created: "
            f"{validation.get('validationErrors')}"
        )
    query = (
        "/invoice/api/v6/invoices?roleType=TENANT&isDateCombinedUTC=false&utcTime=true"
        "&needValidateExpBaseAmountOverReceipt=true"
    )
    created_expense = unwrap_row(gateway.request(query, "POST", payload))
    identity = str(
        created_expense.get("invoiceOID")
        or created_expense.get("entityOID")
        or payload.get("entityOID")
        or payload.get("invoiceOID")
    )
    settled = wait_for_expense_save(
        api,
        report["expenseReportOID"],
        identity,
        timeout_seconds=wait_timeout_seconds,
    )
    missing_required = [
        (field.get("name") or field.get("messageKey"))
        for field in data
        if field.get("required") and not field.get("value")
    ]
    return {
        "invoiceOID": settled.get("entityOID") or settled.get("invoiceOID") or identity,
        "expenseType": expense_type_name, "amount": amount,
        "withReceipt": False, "budgetMatch": budget_match,
        "invoiceStatus": settled.get("invoiceStatus"),
        "invoiceSaveStatus": settled.get("invoiceSaveStatus"),
        "missingRequiredFields": missing_required,
        "policyWarnings": policy_warnings,
        "validationErrors": validation.get("validationErrors") if isinstance(validation, dict) else None,
    }


def existing_invoice_numbers(api: Client, report_oid_value: str) -> set[str]:
    """Return the set of invoice numbers already bound to a report (for dedup on incremental add)."""
    invoice_data = unwrap_row(api.request(f"/api/expense/report/invoices/v2?expenseReportOID={report_oid_value}"))
    numbers: set[str] = set()
    # invoiceViewDTOMap keyed views may carry invoice number in nested receipt info.
    for view in (invoice_data.get("invoiceViewDTOMap") or {}).values():
        for key in ("invoiceNumber", "invoiceCode"):
            v = view.get(key)
            if v:
                numbers.add(str(v).strip())
        for receipt in view.get("receiptList") or []:
            for key in ("invoiceNumber", "invoiceCode"):
                v = receipt.get(key)
                if v:
                    numbers.add(str(v).strip())
    # Fallback: iterate top-level expenseReportInvoices list.
    for item in invoice_data.get("expenseReportInvoices") or []:
        for key in ("invoiceNumber", "invoiceCode", "number"):
            v = item.get(key)
            if v:
                numbers.add(str(v).strip())
    return numbers


def verify_report_invoices(api: Client, report_oid_value: str) -> dict[str, Any]:
    detail = get_report(api, report_oid_value)
    invoice_data = unwrap_row(api.request(f"/api/expense/report/invoices/v2?expenseReportOID={report_oid_value}"))
    views = list((invoice_data.get("invoiceViewDTOMap") or {}).values())
    asynchronous_failures = []
    for view in views:
        labels = view.get("invoiceLabels") or []
        if view.get("invoiceSaveStatus") == 100 or any(
            label.get("type") == "INVOICE_ASYNC_ERROR" or label.get("name") == "费用保存失败"
            for label in labels
        ):
            asynchronous_failures.append(view.get("expenseCode") or view.get("entityOID"))
    return {
        "businessCode": detail.get("businessCode"),
        "status": detail.get("status"),
        "totalAmount": detail.get("totalAmount"),
        "invoiceCount": len(invoice_data.get("expenseReportInvoices") or []),
        "manualExpenseCount": sum(1 for view in views if not view.get("withReceipt")),
        "asynchronousSaveFailures": asynchronous_failures,
        "businessAccepted": not asynchronous_failures,
        "invoiceNumbers": sorted(existing_invoice_numbers(api, report_oid_value)),
        "expenses": [
            {"expenseOID": view.get("entityOID") or view.get("invoiceOID"),
             "expenseCode": view.get("expenseCode"),
             "expenseType": view.get("expenseTypeName"), "amount": view.get("amount"),
              "withReceipt": bool(view.get("withReceipt")), "receiptCount": len(view.get("receiptList") or []),
             "invoiceStatus": view.get("invoiceStatus"),
             "invoiceSaveStatus": view.get("invoiceSaveStatus"),
             "labels": [label.get("name") for label in view.get("invoiceLabels") or []],
             "attachments": [item.get("fileName") for item in view.get("attachments") or []],
             "fields": {
                 field.get("name") or field.get("messageKey"): field.get("showValue") or field.get("value")
                 for field in view.get("data") or []
             },
             "invoiceNumbers": [
                 str(r.get("invoiceNumber") or r.get("invoiceCode") or "").strip()
                 for r in view.get("receiptList") or [] if r.get("invoiceNumber") or r.get("invoiceCode")
             ]}
            for view in views
        ],
        "groups": [
            {
                "categoryName": group.get("categoryName"),
                "totalAmount": group.get("totalAmount"),
                "invoiceTotal": group.get("totalInvoiceAmount"),
                "count": len(group.get("invoices") or []),
            }
            for group in (invoice_data.get("invoiceGroups") or [])
        ],
    }
