#!/usr/bin/env python3
"""Command-line entry point for the Huilianyi reimbursement skill."""

from __future__ import annotations

import argparse
import getpass
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hly_api import clients_from_auth, login
from hly_workflow import (
    add_invoice,
    build_history_model,
    build_personal_report_draft,
    build_travel_application_draft,
    build_travel_report_draft,
    find_application,
    find_report,
    find_user,
    get_report,
    report_oid,
    save_application_draft,
    save_report_draft,
    search_reports,
    verify_report_invoices,
)


def _password() -> str:
    return os.environ.get("HLY_PASSWORD") or getpass.getpass("Huilianyi password: ")


def _clients(username: str):
    return clients_from_auth(login(username, _password()))


def _write_json(path: str | Path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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
    if travel and personal:
        return travel, personal
    raise LookupError("Could not find both a historical travel report and personal report template")


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


def command_create_drafts(args):
    if not args.confirm_draft_write:
        raise SystemExit("Refusing external writes without --confirm-draft-write")
    api, _ = _clients(args.username)
    target = find_application(api, args.target_application)
    if target.get("closed"):
        raise SystemExit("Target application is closed and cannot be used for a new travel report")
    agent = find_user(api, args.agent)
    participant = find_user(api, args.participant)
    start, end = _local_dates(target)
    travel_template, personal_template = _templates(api)
    state_path = Path(args.state)
    state = _load_state(state_path)

    if args.create_application and "travelApplication" not in state:
        payload = build_travel_application_draft(target, agent, participant, start, end)
        created = save_application_draft(api, payload)
        state["travelApplication"] = {
            "businessCode": created.get("businessCode"),
            "applicationOID": created.get("applicationOID") or created.get("entityOID"),
        }
        _save_state(state_path, state)

    if args.create_travel_report and "travelReport" not in state:
        payload = build_travel_report_draft(travel_template, target, start, end)
        created = save_report_draft(api, payload)
        state["travelReport"] = {
            "businessCode": created.get("businessCode"),
            "expenseReportOID": created.get("expenseReportOID") or created.get("entityOID"),
            "linkedApplication": args.target_application,
        }
        _save_state(state_path, state)

    if args.create_personal_report and "personalReport" not in state:
        payload = build_personal_report_draft(personal_template, args.personal_title)
        created = save_report_draft(api, payload)
        state["personalReport"] = {
            "businessCode": created.get("businessCode"),
            "expenseReportOID": created.get("expenseReportOID") or created.get("entityOID"),
        }
        _save_state(state_path, state)

    print(json.dumps({"state": str(state_path.resolve()), "drafts": state}, ensure_ascii=False, indent=2))


def command_add_invoice(args):
    if not args.confirm_draft_write:
        raise SystemExit("Refusing external writes without --confirm-draft-write")
    api, gateway = _clients(args.username)
    report = find_report(api, args.report)
    result = add_invoice(api, gateway, report, args.file, args.expense_type, args.amount)
    verification = verify_report_invoices(api, report["expenseReportOID"])
    print(json.dumps({"created": result, "report": verification}, ensure_ascii=False, indent=2))


def build_parser():
    parser = argparse.ArgumentParser(description="Huilianyi draft-only API workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    history = sub.add_parser("history", help="read application/report/invoice relationships")
    history.add_argument("--username", required=True)
    history.add_argument("--limit", type=int, default=100)
    history.add_argument("--output", default="tmp/hly-history.json")
    history.set_defaults(func=command_history)

    drafts = sub.add_parser("create-drafts", help="create editing drafts only")
    drafts.add_argument("--username", required=True)
    drafts.add_argument("--target-application", required=True)
    drafts.add_argument("--agent", required=True)
    drafts.add_argument("--participant", required=True)
    drafts.add_argument("--personal-title", default="客户送礼，请客招待")
    drafts.add_argument("--state", default="tmp/hly-state.json")
    _boolean_option(drafts, "create-application")
    _boolean_option(drafts, "create-travel-report")
    _boolean_option(drafts, "create-personal-report")
    drafts.add_argument("--confirm-draft-write", action="store_true")
    drafts.set_defaults(func=command_create_drafts)

    invoice = sub.add_parser("add-invoice", help="upload/OCR/verify/classify/bind one invoice")
    invoice.add_argument("--username", required=True)
    invoice.add_argument("--report", required=True)
    invoice.add_argument("--file", required=True)
    invoice.add_argument("--expense-type", required=True)
    invoice.add_argument("--amount", type=float, required=True)
    invoice.add_argument("--confirm-draft-write", action="store_true")
    invoice.set_defaults(func=command_add_invoice)
    return parser


if __name__ == "__main__":
    parsed = build_parser().parse_args()
    parsed.func(parsed)
