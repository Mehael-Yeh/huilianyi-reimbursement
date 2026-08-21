#!/usr/bin/env python3
"""Verified Huilianyi draft and invoice workflows.

This module intentionally contains no submit, close, withdraw, or delete
operations. All write helpers create/edit draft data only.
"""

from __future__ import annotations

import copy
import json
import time
import urllib.parse
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Any

from hly_api import Client, unwrap_row, unwrap_rows


DRAFT_STATUS = 1001
APPROVED_APPLICATION_STATUS = 1003


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


def build_history_model(api: Client, limit: int = 100) -> dict[str, Any]:
    """Read history and model application/report/invoice relationships."""
    applications = []
    known_application_oids = set()
    for item in search_applications(api, limit):
        oid = application_oid(item)
        if not oid:
            continue
        detail = get_application(api, oid)
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
) -> dict[str, Any]:
    """Build a header-complete, zero-budget travel application draft."""
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
            "baseCurrencyAmount": 0.0,
            "totalBudget": 0.0,
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


def add_invoice(
    api: Client,
    gateway: Client,
    report: dict[str, Any],
    file_path: str | Path,
    expense_type_name: str,
    amount: float,
) -> dict[str, Any]:
    """Upload, recognize, verify, classify, and bind one invoice to a draft."""
    if report.get("status") != DRAFT_STATUS:
        raise ValueError("invoices may only be added to an editing draft (status 1001)")
    report_oid_value = report["expenseReportOID"]
    types = available_expense_types(api, report)
    if expense_type_name not in types:
        raise LookupError(f"expense type not available: {expense_type_name}")
    expense_type = types[expense_type_name]
    expense_type_id = str(expense_type.get("expenseTypeId") or expense_type.get("id"))
    expense_type_oid = expense_type.get("expenseTypeOID") or expense_type.get("oid")
    owner_oid = report["applicantOID"]

    upload = api.upload_invoice(file_path)
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

    defaults_value = gateway.request(
        "/invoice/api/invoice/defaults?roleType=TENANT&isDateCombinedUTC=false",
        "POST",
        {"expenseTypeId": expense_type_id, "receipts": [receipt]},
    )
    defaults = unwrap_row(defaults_value)
    api.request(
        "/api/expense/default/apportionment",
        "POST",
        {
            "expenseReportOID": report_oid_value,
            "expenseTypeId": expense_type_id,
            "amount": amount,
            "currency": "CNY",
            "ownerOID": owner_oid,
            "merge": True,
            "applicationCustomBudgetId": [],
            "prepaymentLineIdList": [],
            "paymentCompanyOID": report.get("companyOID"),
        },
    )
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
        "attachments": [],
        "data": [],
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
    }


def verify_report_invoices(api: Client, report_oid_value: str) -> dict[str, Any]:
    detail = get_report(api, report_oid_value)
    invoice_data = unwrap_row(api.request(f"/api/expense/report/invoices/v2?expenseReportOID={report_oid_value}"))
    return {
        "businessCode": detail.get("businessCode"),
        "status": detail.get("status"),
        "totalAmount": detail.get("totalAmount"),
        "invoiceCount": len(invoice_data.get("expenseReportInvoices") or []),
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
