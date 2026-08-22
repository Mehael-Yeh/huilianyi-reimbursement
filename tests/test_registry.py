import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from huilianyi.registry import load_registry, validate_registry


class RegistryTests(unittest.TestCase):
    def test_registry_is_complete_and_safe(self):
        entries = load_registry()
        validate_registry(entries)
        self.assertGreaterEqual(len(entries), 20)
        self.assertTrue(any(row["status"] == "verified" for row in entries))
        names = {row["name"] for row in entries}
        self.assertTrue({
            "list_invoice_pool", "list_my_expense_items", "loan_repayment_summary",
            "search_loans", "reimbursement_payment_schedules",
        }.issubset(names))

    def test_state_change_cannot_be_exposed(self):
        entries = load_registry()
        unsafe = copy.deepcopy(entries[0])
        unsafe.update({"name": "submit_test", "risk_level": "STATE_CHANGE", "mcp_exposed": True})
        with self.assertRaisesRegex(ValueError, "unsafe MCP exposure"):
            validate_registry(entries + [unsafe])


if __name__ == "__main__":
    unittest.main()
