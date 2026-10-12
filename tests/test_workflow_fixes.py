"""Regression tests for the fixes made from the 2026-06 reimbursement run:

* receipts must be matched back to their uploaded file (the platform answers in its own order);
* supporting documents may be spreadsheets, and the 私车公用 mileage sheet is auto-attached;
* ``/invoice/api/invoice/defaults`` answers with a raw field list, so the form fields it returns
  must survive into the V5 payload instead of being dropped;
* required form values (客户名称 and friends) can be added explicitly.
"""

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hly_workflow import (  # noqa: E402
    add_invoice_batch,
    align_receipts,
    apply_field_values,
    default_mileage_sheets,
    hotel_field_values,
    populate_apportionment,
    validate_attachment_file,
)


class AlignReceiptsTests(unittest.TestCase):
    def test_receipts_are_matched_back_to_their_file(self):
        uploads = [{"attachmentOID": "a"}, {"attachmentOID": "b"}, {"attachmentOID": "c"}]
        paths = [Path("one.pdf"), Path("two.pdf"), Path("three.pdf")]
        receipts = [
            {"ocrOriginAttachmentOID": "c", "billingNo": "third"},
            {"ocrOriginAttachmentOID": "b", "billingNo": "second"},
            {"ocrOriginAttachmentOID": "a", "billingNo": "first"},
        ]
        aligned = align_receipts(uploads, paths, receipts)
        self.assertEqual([row["billingNo"] for row in aligned], ["first", "second", "third"])

    def test_missing_receipt_names_the_file(self):
        uploads = [{"attachmentOID": "a"}, {"attachmentOID": "b"}]
        paths = [Path("one.pdf"), Path("two.pdf")]
        receipts = [{"ocrOriginAttachmentOID": "a", "billingNo": "first"}]
        with self.assertRaises(ValueError) as caught:
            align_receipts(uploads, paths, receipts)
        self.assertIn("two.pdf", str(caught.exception))

    def test_receipts_without_attachment_links_keep_the_platform_order(self):
        uploads = [{"attachmentOID": "a"}]
        paths = [Path("one.pdf")]
        receipts = [{"billingNo": "first"}, {"billingNo": "second"}]
        self.assertEqual(align_receipts(uploads, paths, receipts), receipts)


class AttachmentRuleTests(unittest.TestCase):
    def test_spreadsheet_is_allowed_but_other_formats_are_not(self):
        with tempfile.TemporaryDirectory() as directory:
            sheet = Path(directory) / "私车公用报销清单、里程截图.xlsx"
            sheet.write_bytes(b"xlsx")
            self.assertEqual(validate_attachment_file(sheet), sheet)
            notes = Path(directory) / "notes.txt"
            notes.write_text("nope", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_attachment_file(notes)

    def test_mileage_sheet_is_found_next_to_the_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            invoice = Path(directory) / "fuel.pdf"
            invoice.write_bytes(b"pdf")
            sheet = Path(directory) / "私车公用报销清单、里程截图.xlsx"
            sheet.write_bytes(b"xlsx")
            self.assertEqual(default_mileage_sheets([invoice]), [sheet])
            self.assertEqual(default_mileage_sheets([invoice]), default_mileage_sheets([invoice]))


class FieldValueTests(unittest.TestCase):
    def test_field_missing_from_defaults_is_cloned_from_a_template(self):
        templates = {"客户名称": {"name": "客户名称", "fieldOID": "f1", "value": "old", "showValue": "old"}}
        data = apply_field_values([], {"客户名称": "上海维凯光电、东莞宏邦"}, templates)
        self.assertEqual(data[0]["value"], "上海维凯光电、东莞宏邦")
        self.assertEqual(data[0]["showValue"], "上海维凯光电、东莞宏邦")
        self.assertEqual(data[0]["fieldOID"], "f1")
        self.assertEqual(templates["客户名称"]["value"], "old")

    def test_existing_field_is_updated_in_place(self):
        data = [{"messageKey": "location", "value": None, "showValue": ""}]
        out = apply_field_values(data, {"入住城市": ("CHN032002000", "无锡")})
        self.assertEqual(out[0]["value"], "CHN032002000")
        self.assertEqual(out[0]["showValue"], "无锡")

    def test_unknown_field_without_template_is_rejected(self):
        with self.assertRaises(ValueError):
            apply_field_values([], {"客户名称": "x"})

    def test_hotel_city_outside_the_lookup_keeps_its_name(self):
        out = hotel_field_values([{"name": "入住城市"}, {"name": "开始结束日期"}], ["常熟"], "2026-06-01", "2026-06-30")
        self.assertEqual(out[0]["value"], "常熟")
        self.assertEqual(out[0]["showValue"], "常熟")
        self.assertIn('"duration":30.0', out[1]["value"])


class ApportionmentTests(unittest.TestCase):
    def test_shell_from_the_api_is_filled_with_ids_and_amounts(self):
        shell = {
            "amount": None, "currency": None, "proportion": None, "defaultApportion": None,
            "costCenterItems": [{"fieldName": "费用承担部门"}],
        }
        report = {
            "id": "37715143", "docCompanyOID": "company-oid",
            "docCompanyName": "嘉兴锐石化工有限公司", "docCompanyCode": "rs",
        }
        filled = populate_apportionment([shell], report, "1704675864861536258", 696.0, 6.89)
        self.assertEqual(filled[0]["amount"], 696.0)
        self.assertEqual(filled[0]["baseCurrencyAmount"], 696.0)
        self.assertEqual(filled[0]["originTaxAmount"], 6.89)
        self.assertEqual(filled[0]["baseTaxAmount"], 6.89)
        self.assertEqual(filled[0]["currency"], "CNY")
        self.assertEqual(filled[0]["expenseTypeId"], "1704675864861536258")
        self.assertEqual(filled[0]["expenseReportId"], "37715143")
        self.assertEqual(filled[0]["apportionmentCompanyOID"], "company-oid")
        self.assertEqual(filled[0]["costCenterItems"], shell["costCenterItems"])
        self.assertIsNone(shell["amount"])


class BatchPipelineTests(unittest.TestCase):
    """The platform answers OCR/verify in its own order and defaults as a bare list."""

    class FakeAPI:
        def __init__(self):
            self.attachments = []

        def upload_invoice(self, path):
            return {"attachmentOID": f"att-{Path(path).stem}", "fileName": Path(path).name}

        def upload_attachment(self, path):
            self.attachments.append(Path(path).name)
            return {"attachmentOID": f"doc-{len(self.attachments)}", "fileName": Path(path).name}

        def request(self, path, method="GET", payload=None):
            if path == "/api/expense/type/byUser":
                return {"rows": [{"name": "里程补贴", "expenseTypeId": "mileage-type-id", "expenseTypeOID": "type-1"}]}
            if path.startswith("/api/expense/report/invoices/v2"):
                return {"rows": {"invoiceViewDTOMap": {}}}
            if path == "/api/expense/default/apportionment":
                return {"rows": [{"amount": None, "costCenterItems": []}]}
            raise AssertionError(path)

    class FakeGateway:
        def __init__(self):
            self.calls = []

        def request(self, path, method="GET", payload=None):
            self.calls.append((path, method, payload))
            if "/receipt/ocr/" in path:
                return {"rows": {"receiptList": [
                    {"ocrOriginAttachmentOID": wrapper["oriAttachment"]["attachmentOID"],
                     "billingNo": f"bill-{index}", "totalAmount": 100000 + index}
                    for index, wrapper in reversed(list(enumerate(payload)))
                ]}}
            if "/receipt/verify/" in path:
                return {"rows": [
                    {"invoiceInfo": {**wrapper["invoiceInfo"], "receiptOID": f"receipt-{wrapper['invoiceInfo']['billingNo']}",
                                     "unUsedAmount": 1000000}}
                    for wrapper in reversed(payload)
                ]}
            if "/invoice/defaults" in path:
                return [{"name": "里程", "fieldOID": "f-km", "value": None, "showValue": ""}]
            if "/invoice/tax/amount/" in path:
                return {"rows": {"taxAmount": 6.89}}
            if "/invoice/api/v5/invoices" in path:
                return {"rows": {"invoiceOID": "expense-line-1"}}
            raise AssertionError(path)

    def test_mileage_batch_keeps_file_order_fields_and_auto_attachment(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            first = folder / "fuel-a.pdf"
            second = folder / "fuel-b.pdf"
            first.write_bytes(b"pdf")
            second.write_bytes(b"pdf")
            sheet = folder / "私车公用报销清单、里程截图.xlsx"
            sheet.write_bytes(b"xlsx")

            api, gateway = self.FakeAPI(), self.FakeGateway()
            report = {
                "status": 1001, "expenseReportOID": "report-1", "applicantOID": "owner",
                "formOID": "form", "docCompanyOID": "company", "companyOID": "company",
            }
            result = add_invoice_batch(
                api,
                gateway,
                report,
                [{"path": str(first), "amount": None}, {"path": str(second), "amount": None}],
                "里程补贴",
                upload_workers=1,
            )

            self.assertEqual(result["invoiceOID"], "expense-line-1")
            self.assertEqual(result["receiptCount"], 2)
            self.assertEqual(
                [item["invoiceNumber"] for item in result["items"]], ["bill-0", "bill-1"]
            )
            self.assertEqual(api.attachments, ["私车公用报销清单、里程截图.xlsx"])

            body = next(payload for path, _, payload in gateway.calls if "/invoice/api/v5/invoices" in path)
            self.assertEqual([receipt["billingNo"] for receipt in body["receiptList"]], ["bill-0", "bill-1"])
            self.assertEqual([field["name"] for field in body["data"]], ["里程"])
            self.assertEqual(len(body["attachments"]), 1)
            self.assertEqual(body["expenseApportion"][0]["amount"], result["amount"])

    def test_attachment_is_refused_for_a_type_without_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            invoice = folder / "hotel.pdf"
            invoice.write_bytes(b"pdf")
            extra = folder / "note.pdf"
            extra.write_bytes(b"pdf")
            api, gateway = self.FakeAPI(), self.FakeGateway()
            report = {
                "status": 1001, "expenseReportOID": "report-1", "applicantOID": "owner",
                "formOID": "form", "docCompanyOID": "company", "companyOID": "company",
            }
            gateway.request = lambda *args, **kwargs: {"rows": [{"name": "酒店", "expenseTypeId": "hotel-type-id"}]}
            with self.assertRaises(ValueError) as caught:
                add_invoice_batch(
                    api,
                    gateway,
                    report,
                    [{"path": str(invoice), "amount": None}],
                    "酒店",
                    attachment_paths=[str(extra)],
                    hotel_cities=["上海"],
                )
            self.assertIn("supporting documents", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
