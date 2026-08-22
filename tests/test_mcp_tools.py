import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from huilianyi.exceptions import ErrorCode, HuilianyiError
from huilianyi_mcp.tools import HuilianyiTools


class FakeClient:
    def get_current_user(self):
        return {
            "userOID": "u1", "fullName": "Test User", "companyOID": "c1",
            "password": "must-not-leak", "tokenValue": "must-not-leak",
        }

    def list_reimbursements(self, page, size):
        return []

    def list_companies(self, enabled=True):
        return [{
            "companyOID": "c1", "name": "Company", "setOfBooksId": "ledger1",
            "clientSecret": "must-not-leak", "tokenValue": "must-not-leak",
        }]

    def get_reimbursement(self, oid):
        if oid == "expired":
            raise HuilianyiError(ErrorCode.AUTH_EXPIRED, "expired")
        return {"expenseReportOID": oid, "status": 1001}

    def list_invoice_pool(self, page, size):
        return [{
            "receiptOID": "r1", "totalAmount": 25, "payeeBankAccount": "secret",
            "pdfUrl": "https://signed.invalid/secret",
        }]

    def get_reimbursement_payment_schedules(self, oid):
        return [{
            "paymentScheduleOid": "p1", "status": 1003, "amount": 25,
            "accountNumber": "secret", "payeeName": "private",
        }]


class MCPToolTests(unittest.TestCase):
    def setUp(self):
        self.tools = HuilianyiTools(lambda: FakeClient())

    def test_read_tool_has_stable_envelope(self):
        result = self.tools.get_current_user()
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["userOID"], "u1")
        self.assertNotIn("password", result["data"])
        self.assertNotIn("tokenValue", result["data"])

    def test_empty_page_is_normal(self):
        result = self.tools.list_reimbursements(page=0, size=25)
        self.assertEqual(result["data"], [])
        self.assertEqual(result["pagination"], {"page": 0, "size": 25, "returned": 0})

    def test_errors_are_structured(self):
        result = self.tools.get_reimbursement("expired")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "AUTH_EXPIRED")

    def test_pagination_is_validated_before_network(self):
        result = self.tools.list_reimbursements(page=-1, size=1000)
        self.assertEqual(result["error"]["code"], "VALIDATION_ERROR")

    def test_invoice_pool_drops_sensitive_fields(self):
        result = self.tools.list_invoice_pool(0, 10)
        self.assertEqual(result["data"], [{"receiptOID": "r1", "totalAmount": 25}])
        self.assertNotIn("payeeBankAccount", result["data"][0])
        self.assertNotIn("pdfUrl", result["data"][0])

    def test_ledger_list_drops_company_security_configuration(self):
        result = self.tools.list_ledgers()
        self.assertEqual(
            result["data"],
            [{"companyOID": "c1", "name": "Company", "setOfBooksId": "ledger1"}],
        )
        self.assertNotIn("clientSecret", result["data"][0])

    def test_payment_status_drops_bank_and_payee_fields(self):
        result = self.tools.get_reimbursement_payment_status("er1")
        self.assertEqual(
            result["data"], [{"paymentScheduleOid": "p1", "status": 1003, "amount": 25}]
        )


class MCPProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_server_lists_allowlisted_tools(self):
        from mcp import Client
        from huilianyi_mcp.server import mcp

        async with Client(mcp) as client:
            result = await client.list_tools()
        names = {tool.name for tool in result.tools}
        self.assertIn("get_current_user", names)
        self.assertIn("create_travel_draft", names)
        self.assertIn("list_invoice_pool", names)
        self.assertIn("list_ledgers", names)
        self.assertIn("get_reimbursement_payment_status", names)
        forbidden = {"submit_reimbursement", "approve", "reject", "delete_reimbursement", "pay"}
        self.assertFalse(names.intersection(forbidden))


if __name__ == "__main__":
    unittest.main()
