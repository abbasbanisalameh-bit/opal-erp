from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]


class PreviousDebtUiContractTests(SimpleTestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_previous_debt_uses_canonical_invoice_and_payment_models(self):
        service = self.source("accounting/previous_debt_services.py")
        self.assertIn("StudentInvoice", service)
        self.assertIn("StudentPayment", service)
        self.assertIn('exclude(status="cancelled")', service)
        self.assertIn('payments__status="posted"', service)
        self.assertIn("academic_year__start_date__lt=current_year.start_date", service)
        self.assertNotIn("class PreviousDebt", service)

    def test_manager_student_and_guardian_alerts_are_published(self):
        student = self.source("templates/students/student_360.html")
        parent = self.source("templates/parent_portal/dashboard.html")
        self.assertIn("opal-previous-debt-pulse", student)
        self.assertIn("admissions:previous_debt_payment", student)
        self.assertIn("opal-previous-debt-pulse", parent)
        self.assertIn("accounting:previous_debt_list", self.source("dashboard/templates/dashboard/home.html"))

    def test_receipt_contains_year_grade_and_balance_details(self):
        receipt = self.source("templates/admissions/fee_payment_receipt.html")
        self.assertIn("previous_debt_receipt.is_previous_debt", receipt)
        self.assertIn("row.academic_year.name", receipt)
        self.assertIn("row.grade_label", receipt)
        self.assertIn("row.remaining_before", receipt)
        self.assertIn("row.remaining_after", receipt)

    def test_no_migration_or_parallel_balance_is_added(self):
        migrations = list((ROOT / "accounting" / "migrations").glob("*.py"))
        self.assertFalse(any(path.name.startswith("0010_") for path in migrations))
        service = self.source("accounting/previous_debt_services.py")
        self.assertIn("FinancialCarryForward", service)
        self.assertIn("source_invoices", service)
    def test_school_fee_language_and_parent_gateway_contract(self):
        visible_templates = (
            "templates/students/student_360.html",
            "templates/parent_portal/dashboard.html",
            "templates/parent_portal/student_detail.html",
            "templates/accounting/previous_debt_list.html",
            "templates/admissions/previous_debt_payment.html",
            "templates/admissions/fee_payment_receipt.html",
            "dashboard/templates/dashboard/home.html",
        )
        for relative in visible_templates:
            source = self.source(relative)
            self.assertNotIn("الذمم", source, relative)
            self.assertNotIn("ذمة", source, relative)
        parent_detail = self.source("templates/parent_portal/student_detail.html")
        self.assertIn("opal-previous-debt-pulse", parent_detail)
        self.assertNotIn("parent_portal:fees", parent_detail)
        self.assertIn("بوابة ولي الأمر الرئيسية", parent_detail)

