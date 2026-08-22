#!/usr/bin/env python3
"""Command-line entry point for the Huilianyi reimbursement skill."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hly_api import clients_from_auth, login
from hly_credentials import CredentialStore
from hly_workflow import (
    add_invoice,
    add_invoice_batch,
    add_manual_expense,
    build_history_model,
    build_personal_report_draft,
    build_travel_application_draft,
    build_travel_report_draft,
    compare_travel_amounts,
    find_application,
    find_report,
    find_user,
    get_application,
    get_report,
    report_oid,
    save_application_draft,
    save_report_draft,
    search_reports,
    verify_report_invoices,
)
from review_export import load_json, merge_review_data
from build_review_workbook import save_verified_workbook


def _clients(username: str | None):
    store = CredentialStore()
    cached_auth = {}

    def validate(account: str, password: str):
        cached_auth["value"] = login(account, password)

    credentials = store.resolve(username, validate=validate)
    auth = cached_auth.get("value") or login(credentials.username, credentials.password)
    return clients_from_auth(auth)


def _write_json(path: str | Path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _load_travel_plan(path: str | Path) -> list[dict]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    lines = value.get("travel") if isinstance(value, dict) else value
    if not isinstance(lines, list) or not lines:
        raise ValueError("travel plan must be a non-empty JSON array or an object with a travel array")
    return lines


def _load_invoice_batch(path: str | Path) -> list[dict]:
    source = Path(path).resolve()
    value = json.loads(source.read_text(encoding="utf-8"))
    items = value.get("files") if isinstance(value, dict) else value
    if not isinstance(items, list) or not items:
        raise ValueError("invoice batch must be a non-empty JSON array or an object with a files array")
    resolved = []
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not item.get("path"):
            raise ValueError(f"invoice batch item {index} requires path")
        row = dict(item)
        item_path = Path(str(row["path"]))
        row["path"] = str(item_path if item_path.is_absolute() else (source.parent / item_path).resolve())
        resolved.append(row)
    return resolved


def _confirmed_dates(start: str | None, end: str | None) -> tuple[str, str]:
    start = start or input("Reimbursement start date (YYYY-MM-DD): ").strip()
    end = end or input("Reimbursement end date (YYYY-MM-DD): ").strip()
    start_date = datetime.fromisoformat(start).date()
    end_date = datetime.fromisoformat(end).date()
    if end_date < start_date:
        raise ValueError("end date is before start date")
    return start_date.isoformat(), end_date.isoformat()


def _save_state(path: Path, state: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _local_dates(application: dict) -> tuple[str, str]:
    travel = application["travelApplication"]
    china = timezone(timedelta(hours=8))
    start = datetime.fromisoformat(travel["startDate"].replace("Z", "+00:00")).astimezone(china).date()
    end = datetime.fromisoformat(travel["endDate"].replace("Z", "+00:00")).astimezone(china).date()
    return start.isoformat(), end.isoformat()


def _templates(api):
    travel_paid = None
    personal_paid = None
    travel_fallback = None
    personal_fallback = None
    for item in search_reports(api):
        oid = report_oid(item)
        if not oid:
            continue
        detail = get_report(api, oid)
        is_travel = bool(detail.get("applicationOID"))
        is_paid = int(detail.get("status") or 0) == 1005
        if is_travel and travel_fallback is None:
            travel_fallback = detail
        if not is_travel and personal_fallback is None:
            personal_fallback = detail
        if is_travel and is_paid and travel_paid is None:
            travel_paid = detail
        if not is_travel and is_paid and personal_paid is None:
            personal_paid = detail
    travel = travel_paid or travel_fallback
    personal = personal_paid or personal_fallback
    if not travel:
        raise LookupError("Could not find a historical travel report template")
    return travel, personal


def _boolean_option(parser, name: str, default: bool = True):
    """Python 3.8-compatible --foo/--no-foo option pair."""
    destination = name.replace("-", "_")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(f"--{name}", dest=destination, action="store_true")
    group.add_argument(f"--no-{name}", dest=destination, action="store_false")
    parser.set_defaults(**{destination: default})


def command_history(args):
    api, _ = _clients(args.username)
    model = build_history_model(api, args.limit)
    _write_json(args.output, model)
    print(json.dumps({"output": str(Path(args.output).resolve()), "applications": len(model["applications"]), "reports": len(model["reports"])}, ensure_ascii=False, indent=2))


def command_credentials_init(args):
    store = CredentialStore()
    store.prompt_and_save(lambda username, password: login(username, password))
    print(json.dumps({"stored": True, "config": str(store.config_path)}, ensure_ascii=False, indent=2))


def command_profile(args):
    """First-run profile: read history and distill the user's reimbursement habits
    (companies, departments, agents, expense-type usage frequency) into a local,
    human-reviewable profile. Nothing here is written into the skill; credentials
    are never read back from this file."""
    api, _ = _clients(args.username)
    model = build_history_model(api, args.limit)
    apps, reports = model["applications"], model["reports"]

    companies = Counter()
    company_oids = {}
    departments = Counter()
    department_oids = {}
    agents = Counter()
    agent_oids = {}
    for app in apps:
        cname, doid = app.get("companyName"), app.get("companyOID")
        if cname:
            companies[cname] += 1
            if cname not in company_oids and doid:
                company_oids[cname] = doid
        dname, d_oid = app.get("departmentName"), app.get("departmentOID")
        if dname:
            departments[dname] += 1
            if dname not in department_oids and d_oid:
                department_oids[dname] = d_oid
        aname, a_oid = app.get("agentName"), app.get("agentOID")
        if aname:
            agents[aname] += 1
            if aname not in agent_oids and a_oid:
                agent_oids[aname] = a_oid

    expense_types = Counter()
    for app in apps:
        for name in (app.get("budgetByExpenseType") or {}):
            expense_types[name] += 1
    for report in reports:
        for name in (report.get("expenseByType") or {}):
            expense_types[name] += 1

    profile = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "disclaimer": "First-run review copy. OIDs are runtime caches only and MUST be re-validated against the live tenant before each fill (per form-fields.md). Confirm/correct values with the user before use.",
        "habits": {
            "companies": [{"name": n, "oid": company_oids.get(n), "uses": c} for n, c in companies.most_common()],
            "departments": [{"name": n, "oid": department_oids.get(n), "uses": c} for n, c in departments.most_common()],
            "agents": [{"name": n, "oid": agent_oids.get(n), "uses": c} for n, c in agents.most_common()],
        },
        "expenseTypeUsage": [{"name": n, "seenInDocuments": c} for n, c in expense_types.most_common()],
        "samples": {
            "applications": len(apps),
            "reports": len(reports),
            "recentApplications": [{"businessCode": a["businessCode"], "status": a["status"], "company": a["companyName"], "dept": a["departmentName"], "agent": a["agentName"], "budget": a["budgetByExpenseType"]} for a in apps[:5]],
            "recentReports": [{"businessCode": r["businessCode"], "status": r["status"], "totalAmount": r["totalAmount"], "expenseByType": r["expenseByType"]} for r in reports[:5]],
        },
    }
    _write_json(args.output, profile)
    print(json.dumps({"profile": str(Path(args.output).resolve()), **{k: list(v) for k, v in
        {"companies": companies.most_common(), "departments": departments.most_common(), "agents": agents.most_common(), "expenseTypes": expense_types.most_common()}.items()}}, ensure_ascii=False, indent=2))


def command_create_application(args):
    if not args.confirm_draft_write:
        raise SystemExit("Refusing external writes without --confirm-draft-write")
    api, _ = _clients(args.username)
    template = find_application(api, args.template_application)
    agent = find_user(api, args.agent)
    participant = find_user(api, args.participant)
    plan = _load_travel_plan(args.travel_plan)
    start, end = _confirmed_dates(args.start, args.end)
    state_path = Path(args.state)
    state = _load_state(state_path)
    if "travelApplication" not in state:
        payload = build_travel_application_draft(
            template, agent, participant, start, end, plan
        )
        created = save_application_draft(api, payload)
        state["travelApplication"] = {
            "businessCode": created.get("businessCode"),
            "applicationOID": created.get("applicationOID") or created.get("entityOID"),
            "plannedAmount": round(sum(float(line["amount"]) for line in plan), 2),
        }
        _save_state(state_path, state)
    print(json.dumps({"state": str(state_path.resolve()), "drafts": state}, ensure_ascii=False, indent=2))


def command_create_reports(args):
    if not args.confirm_draft_write:
        raise SystemExit("Refusing external writes without --confirm-draft-write")
    api, _ = _clients(args.username)
    target = find_application(api, args.target_application)
    start, end = _local_dates(target)
    travel_template, personal_template = _templates(api)
    state_path = Path(args.state)
    state = _load_state(state_path)
    if "travelReport" not in state:
        payload = build_travel_report_draft(travel_template, target, start, end)
        created = save_report_draft(api, payload)
        state["travelReport"] = {
            "businessCode": created.get("businessCode"),
            "expenseReportOID": created.get("expenseReportOID") or created.get("entityOID"),
            "linkedApplication": args.target_application,
        }
        _save_state(state_path, state)

    if args.create_personal_report and "personalReport" not in state:
        if personal_template is None:
            raise LookupError("Could not find a historical personal report template")
        payload = build_personal_report_draft(personal_template, args.personal_title)
        created = save_report_draft(api, payload)
        state["personalReport"] = {
            "businessCode": created.get("businessCode"),
            "expenseReportOID": created.get("expenseReportOID") or created.get("entityOID"),
        }
        _save_state(state_path, state)

    print(json.dumps({"state": str(state_path.resolve()), "drafts": state}, ensure_ascii=False, indent=2))


def command_audit_travel_pair(args):
    api, _ = _clients(args.username)
    application = find_application(api, args.application)
    report = find_report(api, args.report)
    if report.get("applicationOID") != application.get("applicationOID"):
        raise SystemExit("Report is not linked to the specified application")
    invoices = api.request(
        f"/api/expense/report/invoices/v2?expenseReportOID={report['expenseReportOID']}"
    )
    comparison = compare_travel_amounts(application, invoices.get("rows") or invoices)
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


def command_add_invoice(args):
    if not args.confirm_draft_write:
        raise SystemExit("Refusing external writes without --confirm-draft-write")
    api, gateway = _clients(args.username)
    report = find_report(api, args.report)
    result = add_invoice(
        api,
        gateway,
        report,
        args.file,
        args.expense_type,
        args.amount,
        attachment_paths=args.attachment,
        hotel_cities=args.hotel_city,
    )
    verification = verify_report_invoices(api, report["expenseReportOID"])
    print(json.dumps({"created": result, "report": verification}, ensure_ascii=False, indent=2))


def command_add_invoice_batch(args):
    if not args.confirm_draft_write:
        raise SystemExit("Refusing external writes without --confirm-draft-write")
    api, gateway = _clients(args.username)
    report = find_report(api, args.report)
    result = add_invoice_batch(
        api,
        gateway,
        report,
        _load_invoice_batch(args.invoice_batch),
        args.expense_type,
        attachment_paths=args.attachment,
        hotel_cities=args.hotel_city,
        upload_workers=args.upload_workers,
    )
    verification = verify_report_invoices(api, report["expenseReportOID"])
    print(json.dumps({"created": result, "report": verification}, ensure_ascii=False, indent=2))


def command_add_manual_expense(args):
    if not args.confirm_draft_write:
        raise SystemExit("Refusing external writes without --confirm-draft-write")
    api, gateway = _clients(args.username)
    report = find_report(api, args.report)
    fields = dict(value.split("=", 1) for value in args.field)
    result = add_manual_expense(
        api,
        gateway,
        report,
        args.expense_type,
        args.amount,
        args.date,
        fields,
    )
    verification = verify_report_invoices(api, report["expenseReportOID"])
    print(json.dumps({"created": result, "report": verification}, ensure_ascii=False, indent=2))


def command_verify_report(args):
    api, _ = _clients(args.username)
    report = find_report(api, args.report)
    print(json.dumps(verify_report_invoices(api, report["expenseReportOID"]), ensure_ascii=False, indent=2))


def command_prepare_review(args):
    api, _ = _clients(args.username)
    reports = []
    categories = []
    for code in args.report:
        report = find_report(api, code)
        verification = verify_report_invoices(api, report["expenseReportOID"])
        reports.append(verification)
        if report.get("applicationOID"):
            comparison = compare_travel_amounts(
                get_application(api, report["applicationOID"]),
                api.request(
                    f"/api/expense/report/invoices/v2?expenseReportOID={report['expenseReportOID']}"
                ).get("rows") or {},
            )
            categories.extend(comparison.get("categories") or [])
    review = merge_review_data(load_json(args.invoice_review), reports, categories)
    _write_json(args.output, review)
    print(json.dumps({"output": str(Path(args.output).resolve()), "rows": len(review["rows"])}, ensure_ascii=False, indent=2))


def command_finalize_review(args):
    api, _ = _clients(args.username)
    reports = []
    categories = []
    for code in args.report:
        report = find_report(api, code)
        verification = verify_report_invoices(api, report["expenseReportOID"])
        reports.append(verification)
        if report.get("applicationOID"):
            categories.extend(compare_travel_amounts(
                get_application(api, report["applicationOID"]),
                api.request(
                    f"/api/expense/report/invoices/v2?expenseReportOID={report['expenseReportOID']}"
                ).get("rows") or {},
            ).get("categories") or [])
    review = merge_review_data(load_json(args.invoice_review), reports, categories)
    _write_json(args.review_output, review)
    workbook = save_verified_workbook(review, Path(args.xlsx_output))
    print(json.dumps({"review": str(Path(args.review_output).resolve()), **workbook}, ensure_ascii=False, indent=2))


def build_parser():
    parser = argparse.ArgumentParser(description="Huilianyi draft-only API workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    credentials = sub.add_parser("credentials-init", help="validate and securely store account and password")
    credentials.set_defaults(func=command_credentials_init)

    history = sub.add_parser("history", help="read application/report/invoice relationships")
    history.add_argument("--username")
    history.add_argument("--limit", type=int, default=100)
    history.add_argument("--output", default="tmp/hly-history.json")
    history.set_defaults(func=command_history)

    profile = sub.add_parser("profile", help="first-run: distill reimbursement habits into a local profile for user review")
    profile.add_argument("--username")
    profile.add_argument("--limit", type=int, default=100)
    profile.add_argument("--output", default="tmp/hly-profile.json")
    profile.set_defaults(func=command_profile)

    application = sub.add_parser("create-application", help="create one planned travel application draft")
    application.add_argument("--username")
    application.add_argument("--template-application", required=True)
    application.add_argument("--agent", required=True)
    application.add_argument("--participant", required=True)
    application.add_argument("--start")
    application.add_argument("--end")
    application.add_argument("--travel-plan", required=True)
    application.add_argument("--state", default="tmp/hly-state.json")
    application.add_argument("--confirm-draft-write", action="store_true")
    application.set_defaults(func=command_create_application)

    reports = sub.add_parser("create-reports", help="create travel and optional personal report drafts")
    reports.add_argument("--username")
    reports.add_argument("--target-application", required=True)
    reports.add_argument("--personal-title", default="客户送礼，请客招待")
    reports.add_argument("--state", default="tmp/hly-state.json")
    _boolean_option(reports, "create-personal-report", default=False)
    reports.add_argument("--confirm-draft-write", action="store_true")
    reports.set_defaults(func=command_create_reports)

    audit = sub.add_parser("audit-travel-pair", help="compare linked application budget and report expenses")
    audit.add_argument("--username")
    audit.add_argument("--application", required=True)
    audit.add_argument("--report", required=True)
    audit.set_defaults(func=command_audit_travel_pair)

    invoice = sub.add_parser("add-invoice", help="upload/OCR/verify/classify/bind one invoice")
    invoice.add_argument("--username")
    invoice.add_argument("--report", required=True)
    invoice.add_argument("--file", required=True)
    invoice.add_argument("--expense-type", required=True)
    invoice.add_argument("--amount", type=float, help="optional; otherwise use verified OCR amount")
    invoice.add_argument(
        "--attachment", action="append", default=[], help="supporting toll document (PDF/OFD/ZIP/XML)"
    )
    invoice.add_argument(
        "--hotel-city", action="append", default=[], help="override/add an inferred hotel city"
    )
    invoice.add_argument("--confirm-draft-write", action="store_true")
    invoice.set_defaults(func=command_add_invoice)

    batch = sub.add_parser("add-invoice-batch", help="bind one classified category as one expense line")
    batch.add_argument("--username")
    batch.add_argument("--report", required=True)
    batch.add_argument("--invoice-batch", required=True, help="JSON array of {path, amount} items")
    batch.add_argument("--expense-type", required=True)
    batch.add_argument("--attachment", action="append", default=[])
    batch.add_argument("--hotel-city", action="append", default=[])
    batch.add_argument("--upload-workers", type=int, default=4)
    batch.add_argument("--confirm-draft-write", action="store_true")
    batch.set_defaults(func=command_add_invoice_batch)

    manual = sub.add_parser("add-manual-expense", help="create a no-receipt manual expense")
    manual.add_argument("--username")
    manual.add_argument("--report", required=True)
    manual.add_argument("--expense-type", required=True)
    manual.add_argument("--amount", type=float, required=True)
    manual.add_argument("--date", required=True)
    manual.add_argument("--field", action="append", default=[], metavar="NAME=VALUE")
    manual.add_argument("--confirm-draft-write", action="store_true")
    manual.set_defaults(func=command_add_manual_expense)

    verify = sub.add_parser("verify-report", help="read back expense and receipt state")
    verify.add_argument("--username")
    verify.add_argument("--report", required=True)
    verify.set_defaults(func=command_verify_report)

    review = sub.add_parser("prepare-review", help="merge invoice classification with saved expense results")
    review.add_argument("--username")
    review.add_argument("--report", action="append", required=True)
    review.add_argument("--invoice-review", required=True)
    review.add_argument("--output", default="tmp/reimbursement-review.json")
    review.set_defaults(func=command_prepare_review)

    final_review = sub.add_parser("finalize-review", help="read back reports and always export the final Excel list")
    final_review.add_argument("--username")
    final_review.add_argument("--report", action="append", required=True)
    final_review.add_argument("--invoice-review", required=True)
    final_review.add_argument("--review-output", default="tmp/reimbursement-review.json")
    final_review.add_argument("--xlsx-output", default="outputs/报销分类金额核对.xlsx")
    final_review.set_defaults(func=command_finalize_review)
    return parser


if __name__ == "__main__":
    parsed = build_parser().parse_args()
    parsed.func(parsed)
