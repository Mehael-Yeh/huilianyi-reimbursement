import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from invoice_extract import (  # noqa: E402
    ArchivePasswordRequired,
    _read_archive_entry,
    classify_invoice,
    extract_amount,
    extract_invoice_number,
    extract_selected_archive_files,
    extract_text,
    inspect_invoices,
)


class InvoiceExtractTests(unittest.TestCase):
    def test_prefers_tax_inclusive_total_over_tax_and_unit_price(self):
        result = extract_amount("单价 88.00 税额 ¥6.00 价税合计（小写）¥106.00")
        self.assertEqual(result["amount"], 106.0)
        self.assertEqual(result["source"], "价税合计（小写）")
        self.assertFalse(result["needsReview"])

    def test_does_not_treat_unlabelled_filename_number_as_amount(self):
        result = extract_amount("无金额字段", "20260101_12345678901234567890.pdf")
        self.assertIsNone(result["amount"])
        self.assertTrue(result["needsReview"])

    def test_extracts_labelled_filename_amount_as_low_confidence_fallback(self):
        result = extract_amount("", "票据_金额-25.60.pdf")
        self.assertEqual(result["amount"], 25.6)
        self.assertTrue(result["needsReview"])

    def test_classifies_toll_before_generic_service_terms(self):
        result = classify_invoice("生产生活服务 收费公路通行费", amount=12.5)
        self.assertEqual(result["category"], "过路费")
        self.assertEqual(result["reportGroup"], "差旅报销")

    def test_classifies_meal_by_policy_threshold(self):
        self.assertEqual(classify_invoice("餐饮服务", amount=40)["category"], "餐费")
        self.assertEqual(classify_invoice("餐饮服务", amount=40.01)["category"], "礼品费")

    def test_unknown_is_review_not_gift(self):
        result = classify_invoice("技术服务", amount=100)
        self.assertEqual(result["category"], "待确认")
        self.assertTrue(result["needsReview"])

    def test_oil_card_project_name_suggests_mileage_with_review(self):
        result = classify_invoice("项目名称：油卡充值", amount=500)
        self.assertEqual(result["category"], "里程补贴")
        self.assertIn("油卡充值", result["matchedKeywords"])
        self.assertTrue(result["needsReview"])

    def test_summary_without_invoice_number_is_non_amount_attachment(self):
        result = classify_invoice("通行费电子票据汇总单")
        self.assertEqual(result["category"], "附件")
        self.assertFalse(result["countAmount"])

    def test_invoice_number_uses_label_before_other_long_numbers(self):
        self.assertEqual(extract_invoice_number("纳税人识别号 123456789012345678 发票号码：12345678"), "12345678")
        self.assertIsNone(extract_invoice_number("校验码 12345678901234567890"))

    def test_xml_and_ofd_text_extraction(self):
        xml = b"<Invoice><Item>OilCard</Item><Total>88.50</Total></Invoice>"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xml_path = root / "invoice.xml"
            xml_path.write_bytes(xml)
            self.assertIn("88.50", extract_text(xml_path))
            ofd_path = root / "invoice.ofd"
            with zipfile.ZipFile(ofd_path, "w") as archive:
                archive.writestr("Doc_0/Pages/Page_0/Content.xml", xml)
            text = extract_text(ofd_path)
            self.assertIn("OilCard", text)
            self.assertIn("Total", text)

    def test_zip_emits_one_row_per_supported_document(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invoices.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("a.xml", "<Invoice><Name>餐饮服务</Name><Value>价税合计 20.00</Value></Invoice>")
                archive.writestr("b.xml", "<Invoice><Name>油卡充值</Name><Value>价税合计 100.00</Value></Invoice>")
                archive.writestr("note.txt", "ignored")
            rows = inspect_invoices(path)
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["category"] for row in rows}, {"餐费", "里程补贴"})

    def test_zip_merges_same_invoice_across_xml_ofd_and_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "multi-format.zip"
            xml = "<Invoice><InvoiceNumber>12345678</InvoiceNumber><ItemName>通行费</ItemName><TotalTaxIncludedAmount>12.30</TotalTaxIncludedAmount></Invoice>"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("xml/same.xml", xml)
                nested = Path(directory) / "same.ofd"
                with zipfile.ZipFile(nested, "w") as ofd:
                    ofd.writestr("Doc_0/Content.xml", xml)
                archive.write(nested, "ofd/same.ofd")
            rows = inspect_invoices(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["formats"], ["OFD", "XML"])
            self.assertEqual(rows[0]["amount"], 12.3)
            self.assertEqual(rows[0]["category"], "过路费")

            ofd_rows = inspect_invoices(path, preferred_format="OFD")
            self.assertEqual(ofd_rows[0]["format"], "OFD")
            self.assertEqual(ofd_rows[0]["invoiceNumber"], "12345678")
            self.assertEqual(ofd_rows[0]["source"], "TotalTaxIncludedAmount")
            output_dir = Path(directory) / "selected"
            extracted = extract_selected_archive_files(path, ofd_rows, output_dir)
            self.assertEqual(len(extracted), 1)
            self.assertEqual(extracted[0].suffix, ".ofd")
            self.assertEqual(Path(ofd_rows[0]["extractedFile"]), extracted[0])

    def test_encrypted_entry_requests_password_before_reading(self):
        class Item:
            flag_bits = 1

        class Archive:
            def read(self, item, pwd=None):
                raise AssertionError("read should not be attempted without a password")

        with self.assertRaisesRegex(ArchivePasswordRequired, "requires a password"):
            _read_archive_entry(Archive(), Item(), None)


if __name__ == "__main__":
    unittest.main()
