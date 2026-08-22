import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hly_workflow import (  # noqa: E402
    application_date_values,
    application_budget_match,
    build_travel_application_draft,
    build_personal_report_draft,
    build_travel_report_draft,
    build_v5_body,
    compare_travel_amounts,
    hotel_field_values,
    infer_hotel_cities,
    report_date_values,
    receipt_available_amount,
    recognized_receipt_amount,
    validate_manual_expense_values,
    complete_manual_apportionment,
    validate_upload_file,
)


def field(code, value=None, message_key=None):
    return {
        "id": "old-id",
        "formValueOID": "old-value",
        "bizOID": "old-biz",
        "fieldCode": code,
        "messageKey": message_key,
        "value": value,
        "name": value,
        "showValue": value or "",
    }


class WorkflowTests(unittest.TestCase):
    def test_travel_application_budget_matches_classified_plan(self):
        budget_line = {
            "id": "old", "budgetOID": "old-budget", "applicationOID": "old-app",
            "amount": 1000, "baseCurrencyAmount": 1000,
            "expenseType": {"name": "酒店", "expenseTypeOID": "hotel"},
            "apportionmentDTOList": [{
                "id": 1, "apportionmentOID": "old", "entityOID": "old-app",
                "expenseBudgetOID": "old-budget", "amount": 1000,
                "baseCurrencyAmount": 1000, "costCenterItems": [{"entityOID": "old-app"}],
            }],
        }
        template = {
            "formOID": "form", "companyOID": "company", "corporationOID": "corp",
            "departmentOID": "dept", "custFormValues": [], "travelApplication": {},
            "budgetDetailDTO": {"amount": 1000, "budgetDetail": [budget_line]},
        }
        agent = {"userOID": "agent", "fullName": "代理人"}
        participant = {"userOID": "person", "fullName": "参与人", "departmentOID": "dept"}
        result = build_travel_application_draft(
            template, agent, participant, "2026-06-02", "2026-06-30",
            [{"expenseType": "酒店", "amount": 220.15}],
        )
        self.assertEqual(result["travelApplication"]["totalBudget"], 220.15)
        self.assertEqual(result["budgetDetailDTO"]["amount"], 220.15)
        line = result["budgetDetailDTO"]["budgetDetail"][0]
        self.assertEqual(line["amount"], 220.15)
        self.assertIsNone(line["budgetOID"])
        self.assertEqual(line["apportionmentDTOList"][0]["amount"], 220.15)

    def test_travel_pair_comparison_allows_historical_type_alias(self):
        application = {"budgetDetailDTO": {"budgetDetail": [
            {"expenseType": {"name": "其他交通"}, "amount": 20},
            {"expenseType": {"name": "酒店"}, "amount": 100},
        ]}}
        invoices = {"invoiceViewDTOMap": {
            "a": {"expenseTypeName": "市内交通费", "amount": 20},
            "b": {"expenseTypeName": "酒店", "amount": 90},
        }}
        result = compare_travel_amounts(application, invoices)
        self.assertFalse(result["amountsEqual"])
        self.assertTrue(result["allReportCategoriesCovered"])
        hotel = next(row for row in result["categories"] if row["expenseType"] == "酒店")
        self.assertEqual(hotel["difference"], -10.0)
        self.assertEqual(hotel["invoiceCount"], 1)

    def test_many_invoices_reuse_all_same_category_budget_line_ids(self):
        application = {"budgetDetailDTO": {"budgetDetail": [
            {"id": 101, "expenseType": {"name": "火车"}, "amount": 727},
            {"id": 102, "expenseType": {"name": "火车"}, "amount": 553},
            {"id": 103, "expenseType": {"name": "酒店"}, "amount": 300},
        ]}}
        result = application_budget_match(application, "火车")
        self.assertEqual(result["applicationCustomBudgetId"], ["101", "102"])
        self.assertEqual(result["applicationAmount"], 1280.0)
        self.assertEqual(result["mode"], "application-budget")

    def test_missing_application_category_becomes_manual_expense(self):
        application = {"budgetDetailDTO": {"budgetDetail": []}}
        result = application_budget_match(application, "停车费")
        self.assertEqual(result["applicationCustomBudgetId"], [])
        self.assertEqual(result["mode"], "manual-expense")

    def test_unplanned_report_category_is_reported_not_rejected(self):
        application = {"budgetDetailDTO": {"budgetDetail": [
            {"expenseType": {"name": "酒店"}, "amount": 200},
        ]}}
        invoices = {"invoiceViewDTOMap": {
            "a": {"expenseTypeName": "酒店", "amount": 220},
            "b": {"expenseTypeName": "停车费", "amount": 30},
        }}
        result = compare_travel_amounts(application, invoices)
        self.assertFalse(result["amountsEqual"])
        self.assertFalse(result["allReportCategoriesCovered"])
        parking = next(row for row in result["categories"] if row["expenseType"] == "停车费")
        self.assertEqual(parking["coverage"], "manual-expense")
        self.assertEqual(parking["invoiceCount"], 1)

    def test_application_dates_use_china_timezone(self):
        start, end, days = application_date_values("2026-06-02", "2026-06-30")
        self.assertEqual(start, "2026-06-01T16:00:00Z")
        self.assertEqual(end, "2026-06-30T15:59:00Z")
        self.assertEqual(days, 29)

    def test_report_dates_are_wall_clock_z_values(self):
        self.assertEqual(
            report_date_values("2026-06-02", "2026-06-30"),
            ("2026-06-02T00:00:00Z", "2026-06-30T23:59:00Z"),
        )

    def test_travel_report_has_all_three_link_surfaces(self):
        template = {
            "expenseReportOID": "old-report",
            "entityOID": "old-report",
            "businessCode": "ER-old",
            "status": 1005,
            "totalAmount": 100,
            "formOID": "travel-form",
            "custFormValues": [field("field_7800"), field("field_4242")],
            "expenseReportApplicationDTOS": [
                {
                    "id": "old-link",
                    "expenseReportOID": "old-report",
                    "relatedSimpleApplicationInfo": {"referenceReportsCode": [{"businessCode": "ER-old"}]},
                }
            ],
            "expenseReportInvoices": ["old"],
        }
        target = {
            "applicationOID": "app-1",
            "businessCode": "TZ-1",
            "formOID": "application-form",
            "status": 1003,
            "totalAmount": 2000,
            "travelApplication": {"travelDays": 29, "participantNum": 1},
        }
        result = build_travel_report_draft(template, target, "2026-06-02", "2026-06-30")
        self.assertEqual(result["applicationOID"], "app-1")
        self.assertEqual(result["applicationBusinessCode"], "TZ-1")
        self.assertEqual(len(result["expenseReportApplicationDTOS"]), 1)
        self.assertEqual(result["expenseReportApplicationDTOS"][0]["applicationOID"], "app-1")
        self.assertEqual(
            result["applicationStartAndEndDateMap"]["app-1+start_date"], "2026-06-02T00:00:00Z"
        )
        self.assertEqual(result["status"], 1001)
        self.assertEqual(result["totalAmount"], 0.0)
        self.assertEqual(result["expenseReportInvoices"], [])

    def test_travel_report_rejects_closed_application(self):
        template = {
            "formOID": "travel-form",
            "custFormValues": [],
            "expenseReportApplicationDTOS": [{"relatedSimpleApplicationInfo": {}}],
        }
        target = {
            "applicationOID": "app-1",
            "businessCode": "TZ-1",
            "formOID": "application-form",
            "status": 1003,
            "closed": True,
            "travelApplication": {},
        }
        with self.assertRaisesRegex(ValueError, "closed"):
            build_travel_report_draft(template, target, "2026-06-02", "2026-06-30")

    def test_personal_report_never_links_application(self):
        template = {
            "expenseReportOID": "old",
            "applicationOID": "old-app",
            "businessCode": "old-code",
            "status": 1005,
            "formOID": "personal-form",
            "custFormValues": [field("field_0002", "old", "title")],
            "expenseReportApplicationDTOS": [{"applicationOID": "old-app"}],
            "applicationStartAndEndDateMap": {"old": "date"},
        }
        result = build_personal_report_draft(template, "客户送礼，请客招待")
        self.assertIsNone(result["applicationOID"])
        self.assertEqual(result["expenseReportApplicationDTOS"], [])
        self.assertEqual(result["applicationStartAndEndDateMap"], {})
        self.assertEqual(result["title"], "客户送礼，请客招待")

    def test_v5_discards_provisional_invoice_oid_and_allows_null_receipt_id(self):
        receipt = {"id": None, "receiptOID": "receipt-1"}
        tax = {"invoiceOID": "provisional", "valid": False, "receiptList": [receipt]}
        common = {
            "receiptList": [receipt], "amount": 14.6,
            "expenseApportion": [{"relationApplicationApportionmentGroupMd5": "group"}],
        }
        body = build_v5_body(tax, common)
        self.assertNotIn("invoiceOID", body)
        self.assertTrue(body["valid"])
        self.assertIsNone(body["receiptList"][0]["id"])
        self.assertEqual(body["receiptList"][0]["receiptOID"], "receipt-1")
        self.assertEqual(
            body["expenseApportion"][0]["relationApplicationApportionmentGroupMd5"], "group"
        )

    def test_workflow_source_contains_no_destructive_or_submit_endpoint(self):
        source = (ROOT / "scripts" / "hly_workflow.py").read_text(encoding="utf-8")
        forbidden = ["/submit", "reports/delete", "delete/invoice", "batch/delete", "/withdraw", "/close"]
        for value in forbidden:
            self.assertNotIn(value, source)

    def test_manual_expense_uses_no_receipt_v6_flow(self):
        source = (ROOT / "scripts" / "hly_workflow.py").read_text(encoding="utf-8")
        manual = source.split("def add_manual_expense(", 1)[1].split("def verify_report_invoices", 1)[0]
        self.assertIn('"withReceipt": False', manual)
        self.assertIn('"receiptList": []', manual)
        self.assertIn('/invoice/api/validate/invoice/async', manual)
        self.assertIn('/invoice/api/v6/invoices', manual)
        self.assertIn('manual expense preflight failed; no expense was created', manual)
        self.assertIn('wait_for_expense_save(', manual)
        self.assertNotIn("upload_invoice", manual)

    def test_upload_whitelist_accepts_only_supported_invoice_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for suffix in (".pdf", ".ofd", ".zip", ".xml", ".PDF"):
                path = root / f"invoice{suffix}"
                path.write_bytes(b"test")
                self.assertEqual(validate_upload_file(path), path)
            for suffix in (".png", ".jpg", ".xlsx", ".rar", ".7z"):
                path = root / f"invoice{suffix}"
                path.write_bytes(b"test")
                with self.assertRaisesRegex(ValueError, "unsupported upload format"):
                    validate_upload_file(path)

    def test_receipt_amount_uses_tax_inclusive_fields_only(self):
        self.assertEqual(
            recognized_receipt_amount({
                "taxAmount": 5,
                "invoiceInfo": {"totalTaxIncludedAmount": "¥105.00"},
            }),
            105.0,
        )
        self.assertIsNone(recognized_receipt_amount({"taxAmount": 5, "unitPrice": 100}))
        self.assertEqual(
            recognized_receipt_amount({"totalAmount": 2527, "unUsedAmount": 2527, "dtoVersion": "2.0"}),
            25.27,
        )
        self.assertEqual(receipt_available_amount({"unUsedAmount": 2527}), 25.27)
        self.assertEqual(receipt_available_amount({"unUsedAmount": 0}), 0.0)

    def test_travel_subsidy_uses_100_per_day_as_non_blocking_default(self):
        self.assertEqual(validate_manual_expense_values(
            "出差补贴", 2900, {"补贴天数": "29", "客户名称": ""}
        ), [])
        warnings = validate_manual_expense_values(
            "出差补贴", 29, {"补贴天数": "29", "客户名称": "客户"}
        )
        self.assertEqual(len(warnings), 1)
        self.assertIn("通用默认公式", warnings[0])
        with self.assertRaisesRegex(ValueError, "positive integer"):
            validate_manual_expense_values("出差补贴", 100, {"补贴天数": "1.5"})

    def test_manual_expense_matches_web_job_and_draft_semantics(self):
        source = (ROOT / "scripts" / "hly_workflow.py").read_text(encoding="utf-8")
        manual = source.split("def add_manual_expense(", 1)[1].split("def verify_report_invoices", 1)[0]
        self.assertIn('report.get("applicantJobId")', manual)
        self.assertIn('"paymentCompanyOID": None', manual)
        self.assertIn('"valid": False', manual)
        self.assertIn('field["value"] = None', manual)
        self.assertIn('view.get("invoiceSaveStatus") in {None, 102}', source)

    def test_manual_expense_completes_default_apportionment_skeleton(self):
        rows = complete_manual_apportionment(
            [{"costCenterItems": []}],
            {
                "applicantOID": "person-1",
                "applicantName": "报销人",
                "docCompanyOID": "doc-company-oid",
                "docCompanyName": "示例公司",
                "docCompanyCode": "rs",
            },
            {"companyID": "doc-company-id", "ownerJob": {"employeeId": "241202623"}},
            "expense-type-id",
            100.0,
        )
        self.assertEqual(rows[0]["amount"], 100.0)
        self.assertEqual(rows[0]["baseCurrencyAmount"], 100.0)
        self.assertEqual(rows[0]["expenseTypeId"], "expense-type-id")
        self.assertEqual(rows[0]["companyId"], "doc-company-id")
        self.assertEqual(rows[0]["apportionmentCompanyOID"], "doc-company-oid")

    def test_hotel_fields_use_inferred_cities_and_full_report_range(self):
        cities = infer_hotel_cities(
            "上海汉成酒店管理有限公司", "昆山某酒店", "无锡酒店"
        )
        self.assertEqual(cities, ["上海", "昆山", "无锡"])
        data = hotel_field_values(
            [
                {"name": "入住城市", "fieldType": "LOCATION"},
                {"name": "开始结束日期", "fieldType": "START_DATE_AND_END_DATE"},
            ],
            cities,
            "2026-06-02",
            "2026-06-30",
        )
        self.assertEqual(data[0]["showValue"], "上海，昆山，无锡")
        date_value = __import__("json").loads(data[1]["value"])
        self.assertEqual(date_value["startDate"], "2026-06-02T00:00:00Z")
        self.assertEqual(date_value["endDate"], "2026-06-30T23:59:59Z")
        self.assertEqual(date_value["duration"], 29.0)


if __name__ == "__main__":
    unittest.main()
