import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from review_export import merge_review_data  # noqa: E402


class ReviewExportTests(unittest.TestCase):
    def test_matches_classified_invoice_to_saved_expense(self):
        invoice_review = {"rows": [{
            "fileName": "invoice.pdf", "format": "PDF", "invoiceNumber": "12345678",
            "category": "过路费", "reportGroup": "差旅报销", "amount": 25.5,
            "source": "价税合计", "confidence": "high", "needsReview": False,
            "countAmount": True, "matchedKeywords": ["收费公路通行费"],
        }]}
        reports = [{
            "businessCode": "ER-DEMO", "totalAmount": 25.5, "asynchronousSaveFailures": [],
            "expenses": [{
                "expenseOID": "expense-1", "expenseCode": "EXP-DEMO", "expenseType": "过路费",
                "amount": 25.5, "invoiceNumbers": ["12345678"], "invoiceSaveStatus": None, "labels": [],
            }],
        }]
        result = merge_review_data(invoice_review, reports)
        self.assertEqual(result["rows"][0]["expenseCode"], "EXP-DEMO")
        self.assertEqual(result["rows"][0]["saveStatus"], "成功")
        self.assertEqual(result["metadata"]["reportTotal"], 25.5)

    def test_attachment_is_not_marked_unmatched(self):
        result = merge_review_data({"rows": [{
            "fileName": "summary.pdf", "format": "PDF", "category": "附件",
            "reportGroup": "随对应费用", "amount": None, "source": None,
            "confidence": "high", "needsReview": False, "countAmount": False,
        }]}, [])
        self.assertEqual(result["rows"][0]["saveStatus"], "附件")
        self.assertEqual(result["rows"][0]["needsReview"], "否")


if __name__ == "__main__":
    unittest.main()
