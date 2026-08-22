"""Standard MCP server exposing allowlisted Huilianyi capabilities."""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer
from pydantic import Field
from typing_extensions import Annotated

from huilianyi.models import TravelBudgetLine
from .tools import HuilianyiTools


mcp = MCPServer(
    "Huilianyi MCP",
    instructions=(
        "Huilianyi capability layer. Compose atomic tools; keep reimbursement classification and "
        "business decisions in the calling workflow. Read tools are safe. Write tools may create or "
        "edit only status-1001 drafts. Never submit, approve, reject, delete, withdraw, close, or pay. "
        "Do not expose credentials, signed URLs, or raw private API calls."
    ),
)
tools = HuilianyiTools()


@mcp.tool()
def get_current_user() -> dict[str, Any]:
    """Return the authenticated Huilianyi user's normalized account data."""
    return tools.get_current_user()


@mcp.tool()
def get_company_info() -> dict[str, Any]:
    """Return company/tenant fields visible in the current account response."""
    return tools.get_company_info()


@mcp.tool()
def list_ledgers() -> dict[str, Any]:
    """List sanitized visible company ledgers for use with currency and budget reads."""
    return tools.list_ledgers()


@mcp.tool()
def list_available_forms(form_type: int) -> dict[str, Any]:
    """List forms available to the user; form_type is 101 (application) or 102 (reimbursement)."""
    return tools.list_available_forms(form_type)


@mcp.tool()
def list_cost_centers(keyword: str = "", page: int = 0, size: int = 50) -> dict[str, Any]:
    """Search cost centers visible to the current account."""
    return tools.list_cost_centers(keyword, page, size)


@mcp.tool()
def get_loan_balance_summary() -> dict[str, Any]:
    """Return the current user's loan count and outstanding write-off amount summary."""
    return tools.get_loan_balance_summary()


@mcp.tool()
def get_loan_repayment_summary() -> dict[str, Any]:
    """Return read-only grouped loan repayment totals for the current user."""
    return tools.get_loan_repayment_summary()


@mcp.tool()
def search_loans(keyword: str = "") -> dict[str, Any]:
    """Search visible loan documents by business-code keyword."""
    return tools.search_loans(keyword)


@mcp.tool()
def list_currencies(set_of_books_id: str) -> dict[str, Any]:
    """List enabled currencies and rates for an explicit visible ledger ID."""
    return tools.list_currencies(set_of_books_id)


@mcp.tool()
def list_invoice_pool(page: int = 0, size: int = 50) -> dict[str, Any]:
    """List normalized invoices/receipts in the current user's invoice pool."""
    return tools.list_invoice_pool(page, size)


@mcp.tool()
def list_my_expense_items(page: int = 0, size: int = 50) -> dict[str, Any]:
    """List the current user's reusable expense items with pagination."""
    return tools.list_my_expense_items(page, size)


@mcp.tool()
def get_reimbursement_payment_status(reimbursement_oid: str) -> dict[str, Any]:
    """Return sanitized read-only payment status rows for one reimbursement."""
    return tools.get_reimbursement_payment_status(reimbursement_oid)


@mcp.tool()
def search_users(keyword: str = "", page: int = 0, size: int = 20) -> dict[str, Any]:
    """Search employees visible to the current tenant with pagination."""
    return tools.search_users(keyword, page, size)


@mcp.tool()
def list_travel_applications(page: int = 0, size: int = 50) -> dict[str, Any]:
    """List travel applications visible to the current user."""
    return tools.list_travel_applications(page, size)


@mcp.tool()
def get_travel_application(application_oid: str) -> dict[str, Any]:
    """Get a travel application by OID."""
    return tools.get_travel_application(application_oid)


@mcp.tool()
def list_travel_itineraries(
    application_oid: str, user_oid: str, with_details: bool = True
) -> dict[str, Any]:
    """List itinerary rows for a travel application and visible user."""
    return tools.list_travel_itineraries(application_oid, user_oid, with_details)


@mcp.tool()
def list_reimbursements(page: int = 0, size: int = 50) -> dict[str, Any]:
    """List reimbursement reports visible to the current user."""
    return tools.list_reimbursements(page, size)


@mcp.tool()
def get_reimbursement(reimbursement_oid: str) -> dict[str, Any]:
    """Get a reimbursement report by OID."""
    return tools.get_reimbursement(reimbursement_oid)


@mcp.tool()
def list_invoice_items(reimbursement_oid: str) -> dict[str, Any]:
    """List expense/invoice items on a reimbursement report."""
    return tools.list_invoice_items(reimbursement_oid)


@mcp.tool()
def get_invoice(invoice_oid: str) -> dict[str, Any]:
    """Get one expense/invoice item by OID."""
    return tools.get_invoice(invoice_oid)


@mcp.tool()
def get_approval_history(reimbursement_oid: str) -> dict[str, Any]:
    """Return read-only approval history for a reimbursement report."""
    return tools.get_approval_history(reimbursement_oid)


@mcp.tool()
def list_expense_types(reimbursement_oid: str) -> dict[str, Any]:
    """List expense types available for a specific reimbursement draft/form."""
    return tools.list_expense_types(reimbursement_oid)


@mcp.tool()
def create_travel_draft(
    template_application_oid: str,
    agent_name: str,
    participant_name: str,
    start_date: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")],
    end_date: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")],
    budget_lines: list[TravelBudgetLine],
) -> dict[str, Any]:
    """Create only a status-1001 travel draft from an explicit template and budget lines."""
    return tools.create_travel_draft(
        template_application_oid,
        agent_name,
        participant_name,
        start_date,
        end_date,
        [line.model_dump() for line in budget_lines],
    )


@mcp.tool()
def create_reimbursement_draft(
    template_reimbursement_oid: str,
    title: str,
    target_application_oid: str | None = None,
) -> dict[str, Any]:
    """Create only a status-1001 personal or linked travel reimbursement draft."""
    return tools.create_reimbursement_draft(template_reimbursement_oid, title, target_application_oid)


@mcp.tool()
def upload_attachment(file_path: str) -> dict[str, Any]:
    """Upload one local attachment using the fixed Huilianyi attachment endpoint."""
    return tools.upload_attachment(file_path, "INVOICE_IMAGES")


@mcp.tool()
def attach_invoice(
    reimbursement_oid: str,
    file_path: str,
    expense_type: str,
    amount: float | None = None,
) -> dict[str, Any]:
    """OCR, verify, and attach one invoice to a status-1001 reimbursement draft."""
    return tools.attach_invoice(reimbursement_oid, file_path, expense_type, amount)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
