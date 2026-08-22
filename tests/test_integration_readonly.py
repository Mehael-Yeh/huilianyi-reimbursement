"""Opt-in live tests. Run only with HUILIANYI_INTEGRATION_READONLY=1."""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from huilianyi.client import HuilianyiClient


@unittest.skipUnless(
    os.environ.get("HUILIANYI_INTEGRATION_READONLY") == "1",
    "live read-only integration tests are disabled",
)
class ReadOnlyIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = HuilianyiClient.from_credentials()

    def test_current_user_and_lists(self):
        self.assertIsInstance(self.client.get_current_user(), dict)
        self.assertIsInstance(self.client.list_travel_applications(0, 1), list)
        self.assertIsInstance(self.client.list_reimbursements(0, 1), list)
        self.assertIsInstance(self.client.list_available_forms(101), list)
        self.assertIsInstance(self.client.list_cost_centers("", 0, 1), list)
        self.assertIsInstance(self.client.get_loan_balance_summary(), dict)
        self.assertIsInstance(self.client.get_loan_repayment_summary(), list)
        self.assertIsInstance(self.client.search_loans(""), list)
        self.assertIsInstance(self.client.list_invoice_pool(0, 1), list)
        self.assertIsInstance(self.client.list_my_expense_items(0, 1), list)
        companies = self.client.list_companies()
        self.assertIsInstance(companies, list)
        ledger_id = next((row.get("setOfBooksId") for row in companies if row.get("setOfBooksId")), None)
        if ledger_id:
            self.assertIsInstance(self.client.list_currencies(str(ledger_id)), list)

    def test_detail_read_capabilities(self):
        applications = self.client.list_travel_applications(0, 1)
        account = self.client.get_current_user()
        if applications:
            oid = applications[0].get("applicationOID") or applications[0].get("entityOID")
            self.assertIsInstance(
                self.client.list_travel_itineraries(oid, account["userOID"]), list
            )
        reports = self.client.list_reimbursements(0, 1)
        if reports:
            oid = reports[0].get("expenseReportOID") or reports[0].get("entityOID")
            self.assertIsInstance(self.client.get_reimbursement_approval_history(oid), list)
            self.assertIsInstance(self.client.get_reimbursement_payment_schedules(oid), list)


if __name__ == "__main__":
    unittest.main()
