from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]


class FeeYearSeparationUiContractTests(SimpleTestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_current_payment_filters_invoices_by_current_academic_year(self):
        service = self.source("admissions/financial_services.py")
        apply_block = service.split("def apply_student_payment", 1)[1].split("@transaction.atomic", 1)[0]
        self.assertIn("filter(academic_year=academic_year)", apply_block)
        self.assertIn("carry_forward_record__source_invoices__isnull=False", apply_block)
        self.assertNotIn("ensure_balance_invoice", apply_block)
        self.assertIn("رسوم السنة الحالية", apply_block)

    def test_previous_payment_keeps_its_older_year_filter(self):
        service = self.source("accounting/previous_debt_services.py")
        self.assertIn("academic_year__start_date__lt=current_year.start_date", service)
        self.assertIn("PREVIOUS_YEARS_FEE_NOTE_PREFIX", service)

    def test_main_finance_surfaces_publish_both_balances(self):
        required_labels = ("رسوم السنة الحالية", "متبقيات السنوات السابقة", "الإجمالي المطلوب")
        for relative in (
            "templates/admissions/fee_payment_form.html",
            "templates/admissions/student_financial_record.html",
            "templates/accounting/dashboard.html",
            "templates/parent_portal/dashboard.html",
            "templates/parent_portal/fees.html",
            "templates/students/student_360.html",
        ):
            source = self.source(relative)
            for label in required_labels:
                self.assertIn(label, source, relative)

    def test_no_parallel_balance_model_or_migration_is_added(self):
        models = self.source("accounting/models.py") + self.source("admissions/models.py")
        self.assertNotIn("class PreviousYearBalance", models)
        self.assertFalse((ROOT / "accounting" / "migrations" / "0010_fee_year_separation.py").exists())
        self.assertFalse((ROOT / "admissions" / "migrations" / "0014_fee_year_separation.py").exists())
