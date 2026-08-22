"""Composable MCP tool implementations with stable JSON envelopes."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

from huilianyi.client import HuilianyiClient
from huilianyi.exceptions import ErrorCode, HuilianyiError, sanitize


def _scripts_path() -> Path:
    return Path(__file__).resolve().parents[2] / "scripts"


def _load_workflow():
    scripts = _scripts_path()
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import hly_workflow
    return hly_workflow


def _ok(data: Any, *, page: int | None = None, size: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"ok": True, "data": sanitize(data)}
    if page is not None and size is not None:
        result["pagination"] = {"page": page, "size": size, "returned": len(data)}
    return result


class HuilianyiTools:
    """Tool service kept separate from MCP decorators for deterministic tests."""

    def __init__(self, client_factory: Callable[[], HuilianyiClient] | None = None):
        self._client_factory = client_factory or HuilianyiClient.from_credentials

    def _call(self, operation: Callable[[HuilianyiClient], Any]) -> dict[str, Any]:
        try:
            return _ok(operation(self._client_factory()))
        except HuilianyiError as exc:
            return exc.as_dict()
        except (ValueError, LookupError) as exc:
            return HuilianyiError(ErrorCode.VALIDATION_ERROR, str(exc)).as_dict()

    def get_current_user(self) -> dict[str, Any]:
        safe_keys = (
            "userOID", "fullName", "employeeID", "email", "mobile", "language",
            "countryCode", "countryName", "companyOID", "companyName", "corporationOID",
            "departmentOID", "departmentName", "title", "status",
        )
        return self._call(lambda client: self._allowlist(client.get_current_user(), safe_keys))

    def get_company_info(self) -> dict[str, Any]:
        def operation(client: HuilianyiClient) -> dict[str, Any]:
            account = client.get_current_user()
            keys = ("companyOID", "companyName", "tenantOID", "tenantName", "corporationOID", "corporationName")
            return {key: account.get(key) for key in keys if key in account}
        return self._call(operation)

    def list_available_forms(self, form_type: int) -> dict[str, Any]:
        return self._call(lambda client: client.list_available_forms(form_type))

    def list_cost_centers(self, keyword: str = "", page: int = 0, size: int = 50) -> dict[str, Any]:
        return self._paged(lambda c: c.list_cost_centers(keyword, page, size), page, size)

    def get_loan_balance_summary(self) -> dict[str, Any]:
        safe_keys = ("count", "currencyCode", "stayWriteOffAmount")
        return self._call(lambda client: self._allowlist(client.get_loan_balance_summary(), safe_keys))

    def list_travel_itineraries(
        self, application_oid: str, user_oid: str, with_details: bool = True
    ) -> dict[str, Any]:
        return self._call(
            lambda client: client.list_travel_itineraries(application_oid, user_oid, with_details=with_details)
        )

    def get_approval_history(self, reimbursement_oid: str) -> dict[str, Any]:
        return self._call(lambda client: client.get_reimbursement_approval_history(reimbursement_oid))

    def search_users(self, keyword: str = "", page: int = 0, size: int = 20) -> dict[str, Any]:
        return self._paged(lambda c: c.search_users(keyword, page, size), page, size)

    def list_travel_applications(self, page: int = 0, size: int = 50) -> dict[str, Any]:
        return self._paged(lambda c: c.list_travel_applications(page, size), page, size)

    def get_travel_application(self, application_oid: str) -> dict[str, Any]:
        return self._call(lambda c: c.get_travel_application(application_oid))

    def list_reimbursements(self, page: int = 0, size: int = 50) -> dict[str, Any]:
        return self._paged(lambda c: c.list_reimbursements(page, size), page, size)

    def get_reimbursement(self, reimbursement_oid: str) -> dict[str, Any]:
        return self._call(lambda c: c.get_reimbursement(reimbursement_oid))

    def list_invoice_items(self, reimbursement_oid: str) -> dict[str, Any]:
        return self._call(lambda c: c.list_invoice_items(reimbursement_oid))

    def get_invoice(self, invoice_oid: str) -> dict[str, Any]:
        return self._call(lambda c: c.get_invoice(invoice_oid))

    def list_expense_types(self, reimbursement_oid: str) -> dict[str, Any]:
        def operation(client: HuilianyiClient) -> list[dict[str, Any]]:
            report = client.get_reimbursement(reimbursement_oid)
            return client.list_expense_types(
                reimbursement_oid,
                str(report.get("applicantOID") or ""),
                str(report.get("formOID") or report.get("customFormOID") or ""),
            )
        return self._call(operation)

    def create_travel_draft(
        self,
        template_application_oid: str,
        agent_name: str,
        participant_name: str,
        start_date: str,
        end_date: str,
        budget_lines: list[dict[str, Any]],
    ) -> dict[str, Any]:
        def operation(client: HuilianyiClient) -> dict[str, Any]:
            workflow = _load_workflow()
            template = client.get_travel_application(template_application_oid)
            agent = self._exact_user(client, agent_name)
            participant = self._exact_user(client, participant_name)
            payload = workflow.build_travel_application_draft(
                template, agent, participant, start_date, end_date, budget_lines
            )
            return client.create_travel_draft(payload)
        return self._call(operation)

    def create_reimbursement_draft(
        self,
        template_reimbursement_oid: str,
        title: str,
        target_application_oid: str | None = None,
    ) -> dict[str, Any]:
        def operation(client: HuilianyiClient) -> dict[str, Any]:
            workflow = _load_workflow()
            template = client.get_reimbursement(template_reimbursement_oid)
            if target_application_oid:
                target = client.get_travel_application(target_application_oid)
                travel = target.get("travelApplication") or {}
                payload = workflow.build_travel_report_draft(
                    template, target, travel.get("startDate"), travel.get("endDate")
                )
            else:
                payload = workflow.build_personal_report_draft(template, title)
            return client.create_reimbursement_draft(payload)
        return self._call(operation)

    def upload_attachment(self, file_path: str, attachment_type: str = "INVOICE_IMAGES") -> dict[str, Any]:
        return self._call(lambda c: c.api.upload_attachment(file_path, attachment_type))

    def attach_invoice(
        self,
        reimbursement_oid: str,
        file_path: str,
        expense_type: str,
        amount: float | None = None,
    ) -> dict[str, Any]:
        def operation(client: HuilianyiClient) -> dict[str, Any]:
            workflow = _load_workflow()
            report = client.assert_reimbursement_draft(reimbursement_oid)
            return workflow.add_invoice(
                client.api, client.gateway, report, file_path, expense_type, amount
            )
        return self._call(operation)

    def _paged(self, operation: Callable[[HuilianyiClient], list[dict[str, Any]]], page: int, size: int) -> dict[str, Any]:
        if page < 0 or not 1 <= size <= 100:
            return HuilianyiError(
                ErrorCode.VALIDATION_ERROR, "page must be >= 0 and size must be between 1 and 100"
            ).as_dict()
        result = self._call(operation)
        if result.get("ok"):
            result["pagination"] = {"page": page, "size": size, "returned": len(result["data"])}
        return result

    @staticmethod
    def _exact_user(client: HuilianyiClient, name: str) -> dict[str, Any]:
        matches = [row for row in client.search_users(name, 0, 20) if row.get("fullName") == name]
        if len(matches) != 1:
            raise LookupError(f"expected exactly one user named {name!r}; found {len(matches)}")
        return matches[0]

    @staticmethod
    def _allowlist(value: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
        return {key: value.get(key) for key in keys if key in value}
