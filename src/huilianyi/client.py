"""Unified Huilianyi transport and typed domain operations."""

from __future__ import annotations

import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable, Literal

from .auth import AuthSession, login
from .credentials import CredentialProvider, default_provider
from .exceptions import ErrorCode, HuilianyiError, error_code_for_status


def unwrap_row(value: Any) -> Any:
    if isinstance(value, dict) and isinstance(value.get("rows"), dict):
        return value["rows"]
    return value


def unwrap_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return value
    if not isinstance(value, dict):
        return []
    for key in ("rows", "content", "data", "list"):
        candidate = value.get(key)
        if isinstance(candidate, list):
            return candidate
        if isinstance(candidate, dict):
            nested = unwrap_rows(candidate)
            if nested:
                return nested
    return []


class Client:
    """Compatibility service client. New code should use :class:`HuilianyiClient`."""

    def __init__(
        self,
        token: str,
        base_url: str,
        *,
        opener: Callable[..., Any] = urllib.request.urlopen,
        timeout: float = 60,
    ):
        self._token = token
        self.base_url = base_url.rstrip("/")
        self._opener = opener
        self.timeout = timeout

    def request(self, path: str, method: str = "GET", payload: Any = None) -> Any:
        if not path.startswith("/"):
            raise HuilianyiError(ErrorCode.VALIDATION_ERROR, "API path must begin with /", path=path)
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with self._opener(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                value = {"message": raw[:1000]}
            raise HuilianyiError(
                error_code_for_status(exc.code),
                "Huilianyi API request failed",
                method=method,
                path=path,
                status=exc.code,
                details=value,
            ) from exc
        except HuilianyiError:
            raise
        except Exception as exc:
            raise HuilianyiError(
                ErrorCode.NETWORK_ERROR,
                "Huilianyi API request could not be completed",
                method=method,
                path=path,
            ) from exc

    def upload_attachment(self, file_path: str | Path, attachment_type: str = "INVOICE_IMAGES") -> dict[str, Any]:
        path = Path(file_path)
        if not path.is_file():
            raise HuilianyiError(ErrorCode.VALIDATION_ERROR, "attachment file does not exist")
        boundary = "----HLYSDK" + uuid.uuid4().hex
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body = b"".join([
            (f"--{boundary}\r\nContent-Disposition: form-data; name=\"attachmentType\"\r\n\r\n{attachment_type}\r\n").encode(),
            (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\nContent-Type: {mime}\r\n\r\n").encode("utf-8"),
            path.read_bytes(), b"\r\n", f"--{boundary}--\r\n".encode(),
        ])
        request = urllib.request.Request(
            self.base_url + "/api/upload/attachment",
            data=body,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=max(self.timeout, 90)) as response:
                return unwrap_row(json.loads(response.read().decode("utf-8")))
        except urllib.error.HTTPError as exc:
            raise HuilianyiError(
                error_code_for_status(exc.code), "attachment upload failed",
                method="POST", path="/api/upload/attachment", status=exc.code,
            ) from exc

    def upload_invoice(self, file_path: str | Path) -> dict[str, Any]:
        return self.upload_attachment(file_path, "INVOICE_IMAGES")


class HuilianyiClient:
    """Single session used by workflows and MCP tools."""

    GATEWAY_URL = "https://console-a2.huilianyi.com"

    def __init__(self, session: AuthSession, *, opener: Callable[..., Any] = urllib.request.urlopen):
        self.session = session
        self.api = Client(session.access_token, session.api_base_url, opener=opener)
        self.gateway = Client(session.access_token, self.GATEWAY_URL, opener=opener)

    @classmethod
    def from_auth(cls, auth: dict[str, Any], **kwargs: Any) -> "HuilianyiClient":
        return cls(AuthSession.from_response(auth), **kwargs)

    @classmethod
    def from_credentials(cls, provider: CredentialProvider | None = None) -> "HuilianyiClient":
        credentials = (provider or default_provider()).load()
        return cls.from_auth(login(credentials.username, credentials.password))

    def get_current_user(self) -> dict[str, Any]:
        return unwrap_row(self.api.request("/api/account?roleType=TENANT"))

    def list_available_forms(self, form_type: int) -> list[dict[str, Any]]:
        if form_type not in (101, 102):
            raise HuilianyiError(ErrorCode.VALIDATION_ERROR, "form_type must be 101 or 102")
        return unwrap_rows(self.api.request(
            f"/api/custom/forms/my/available?roleType=TENANT&formType={form_type}"
        ))

    def list_companies(self, *, enabled: bool = True) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"enabled": str(enabled).lower()})
        return unwrap_rows(self.api.request(f"/api/widget/company/all?{query}"))

    def list_cost_centers(self, keyword: str = "", page: int = 0, size: int = 50) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"keyword": keyword, "page": page, "size": size})
        return unwrap_rows(self.api.request(f"/api/cost/centers/search?{query}"))

    def get_loan_balance_summary(self) -> dict[str, Any]:
        return unwrap_row(self.api.request(
            "/api/loanBill/my/amountAndCount?statusList=1005&statusList=1006"
        ))

    def get_loan_repayment_summary(self) -> list[dict[str, Any]]:
        return unwrap_rows(self.api.request("/api/loanBill/repayment/summary"))

    def search_loans(self, keyword: str = "") -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"keyword": keyword})
        return unwrap_rows(
            self.api.request(f"/api/loanBill/query/business/code/by/keyword?{query}")
        )

    def list_currencies(
        self,
        set_of_books_id: str,
        *,
        language: str = "zh_cn",
        enabled: bool = True,
    ) -> list[dict[str, Any]]:
        if not set_of_books_id:
            raise HuilianyiError(ErrorCode.VALIDATION_ERROR, "set_of_books_id is required")
        query = urllib.parse.urlencode({
            "setOfBooksId": set_of_books_id,
            "language": language,
            "enable": str(enabled).lower(),
        })
        return unwrap_rows(self.api.request(f"/api/currency/rate/list/all?{query}"))

    def list_invoice_pool(self, page: int = 0, size: int = 50) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"page": page, "size": size})
        return unwrap_rows(self.api.request(f"/api/receipt/pool/query/v2?{query}"))

    def list_my_expense_items(self, page: int = 0, size: int = 50) -> list[dict[str, Any]]:
        return unwrap_rows(
            self.api.request("/api/invoices/my", "POST", {"page": page, "size": size})
        )

    def list_my_bank_accounts(self, *, enabled: bool | None = True) -> list[dict[str, Any]]:
        account = self.get_current_user()
        query = urllib.parse.urlencode({
            "userOID": account.get("userOID") or "",
            "enable": "" if enabled is None else str(enabled).lower(),
            "sourceType": "BANKCARD_ACCOUNT",
        })
        return unwrap_rows(self.api.request(f"/api/contact/bank/account/my?{query}"))

    def get_reimbursement_payment_schedules(self, report_oid: str) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"expOid": report_oid})
        value = self.api.request(f"/api/payment/schedule/query/by/expOid?{query}")
        if isinstance(value, dict) and isinstance(value.get("paymentSchedules"), list):
            return value["paymentSchedules"]
        return []

    def list_travel_itineraries(
        self, application_oid: str, user_oid: str, *, with_details: bool = True
    ) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({
            "applicationOID": application_oid,
            "withRequestDetail": str(with_details).lower(),
            "withItemDetail": str(with_details).lower(),
            "userOID": user_oid,
        })
        return unwrap_rows(self.api.request(f"/api/travel/applications/itinerarys?{query}"))

    def get_reimbursement_approval_history(self, reimbursement_oid: str) -> list[dict[str, Any]]:
        value = self.api.request(
            "/api/v2/expense/reports/approval/history?expenseReportOID="
            + urllib.parse.quote(reimbursement_oid)
        )
        return unwrap_rows(value)

    def search_users(self, keyword: str = "", page: int = 0, size: int = 20) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"roleType": "TENANT", "size": size, "page": page, "keyword": keyword})
        return unwrap_rows(self.api.request(f"/api/users/v3/search?{query}"))

    def list_travel_applications(self, page: int = 0, size: int = 50) -> list[dict[str, Any]]:
        return unwrap_rows(self.api.request(
            f"/api/applications/v4/search?roleType=TENANT&page={page}&size={size}", "POST", {}
        ))

    def get_travel_application(self, oid: str) -> dict[str, Any]:
        return unwrap_row(self.api.request(f"/api/application/{urllib.parse.quote(oid)}?showValue=true"))

    def list_reimbursements(self, page: int = 0, size: int = 50) -> list[dict[str, Any]]:
        return unwrap_rows(self.api.request(
            f"/api/expense/reports/search/my?roleType=TENANT&page={page}&size={size}", "POST", {}
        ))

    def get_reimbursement(self, oid: str) -> dict[str, Any]:
        return unwrap_row(self.api.request(f"/api/v3/expense/reports/{urllib.parse.quote(oid)}"))

    def list_invoice_items(self, report_oid: str) -> dict[str, Any]:
        return unwrap_row(self.api.request(
            "/api/expense/report/invoices/v2?expenseReportOID=" + urllib.parse.quote(report_oid)
        ))

    def get_invoice(self, invoice_oid: str) -> dict[str, Any]:
        return unwrap_row(self.api.request(
            f"/api/invoices/{urllib.parse.quote(invoice_oid)}?isDateCombinedUTC=false"
        ))

    def list_expense_types(self, report_oid: str, applicant_oid: str, form_oid: str) -> list[dict[str, Any]]:
        return unwrap_rows(self.api.request("/api/expense/type/byUser", "POST", {
            "expenseReportOID": report_oid,
            "applicantOID": applicant_oid,
            "formOID": form_oid,
            "roleType": "TENANT",
        }))

    @staticmethod
    def _validate_draft_payload(payload: dict[str, Any]) -> None:
        forbidden = {"submit", "approved", "approvalStatus", "paymentStatus", "deleted"}
        present = forbidden.intersection(payload)
        if present:
            raise HuilianyiError(
                ErrorCode.UNSAFE_OPERATION,
                f"draft payload contains forbidden state fields: {', '.join(sorted(present))}",
            )
        if payload.get("status") not in (None, 1001):
            raise HuilianyiError(ErrorCode.UNSAFE_OPERATION, "MCP writes are limited to status 1001 drafts")
        payload["status"] = 1001

    def create_travel_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._validate_draft_payload(payload)
        return unwrap_row(self.api.request("/api/travel/applications/draft", "POST", payload))

    def create_reimbursement_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._validate_draft_payload(payload)
        return unwrap_row(self.api.request(
            "/api/expense/reports/custom/form/draft?corporateFlag=false", "POST", payload
        ))

    def assert_reimbursement_draft(self, report_oid: str) -> dict[str, Any]:
        report = self.get_reimbursement(report_oid)
        if report.get("status") != 1001:
            raise HuilianyiError(ErrorCode.UNSAFE_OPERATION, "target reimbursement is not a status 1001 draft")
        return report


def clients_from_auth(auth: dict[str, Any]) -> tuple[Client, Client]:
    client = HuilianyiClient.from_auth(auth)
    return client.api, client.gateway
