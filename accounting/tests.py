from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from students.models import Student

from core.models import AcademicYear, School
from admissions.models import FeePayment
from admissions.financial_services import student_remaining

from .financial_services import close_financial_year, financial_period, monthly_financial_report
from .models import DiscountRequest, ExpenseEntry, FeeCategory, FinancialYearClosure, Installment, Receipt, StudentInvoice, StudentPayment
from .services import decide_discount


class SchoolFinanceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("finance", password="x", is_staff=True)
        self.student = Student.objects.create(student_number="S-1", full_name="طالب مالي", grade="الأول")
        self.category = FeeCategory.objects.create(name="رسوم دراسية", amount=Decimal("1000"))
        self.invoice = StudentInvoice.objects.create(
            student=self.student,
            fee_category=self.category,
            amount=Decimal("1000"),
            due_date=timezone.localdate() + timedelta(days=30),
            created_by=self.user,
        )

    def test_payment_updates_invoice_and_prevents_overpayment(self):
        payment = StudentPayment.objects.create(invoice=self.invoice, amount=Decimal("400"), created_by=self.user)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "partial")
        self.assertEqual(self.invoice.remaining, Decimal("600"))
        with self.assertRaises(ValidationError):
            StudentPayment.objects.create(invoice=self.invoice, amount=Decimal("601"), created_by=self.user)
        self.assertEqual(payment.status, "posted")

    def test_reversal_restores_remaining_and_voids_receipt(self):
        payment = StudentPayment.objects.create(invoice=self.invoice, amount=Decimal("1000"), created_by=self.user)
        receipt = Receipt.objects.create(payment=payment, receipt_number="R-001")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "paid")
        payment.reverse(self.user, "تصحيح دفعة تجريبية")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "open")
        self.assertTrue(receipt.is_void)
        self.assertEqual(self.invoice.remaining, Decimal("1000"))

    def test_discount_approval_changes_net_amount(self):
        request = DiscountRequest.objects.create(
            invoice=self.invoice, requested_amount=Decimal("150"), reason="إعفاء معتمد", requested_by=self.user
        )
        decide_discount(request, self.user, True, "موافق")
        self.invoice.refresh_from_db()
        request.refresh_from_db()
        self.assertEqual(request.status, "approved")
        self.assertEqual(self.invoice.net_amount, Decimal("850"))

    def test_installment_status_uses_due_date_and_posted_payments(self):
        installment = Installment.objects.create(
            invoice=self.invoice, sequence=1, title="القسط الأول", due_date=date.today() - timedelta(days=1), amount=Decimal("500")
        )
        self.assertEqual(installment.calculated_status, "overdue")
        StudentPayment.objects.create(invoice=self.invoice, amount=Decimal("500"), payment_date=installment.due_date, created_by=self.user)
        self.assertEqual(installment.calculated_status, "paid")

    def test_student_balance_properties_are_derived_from_accounting(self):
        field_names = {field.name for field in Student._meta.get_fields()}
        self.assertNotIn("fees_total", field_names)
        self.assertNotIn("fees_paid", field_names)
        self.assertEqual(self.student.fees_total, Decimal("1000.00"))
        self.assertEqual(self.student.fees_paid, Decimal("0.00"))

        StudentPayment.objects.create(
            invoice=self.invoice,
            amount=Decimal("250"),
            created_by=self.user,
        )
        self.assertEqual(self.student.fees_paid, Decimal("250.00"))
        self.assertEqual(self.student.fees_remaining, Decimal("750.00"))


class FinancialPeriodTests(SimpleTestCase):
    def test_cycle_uses_actual_calendar_month(self):
        self.assertEqual(financial_period(date(2026, 7, 18)), (date(2026, 7, 1), date(2026, 7, 31)))
        self.assertEqual(financial_period(date(2026, 2, 12)), (date(2026, 2, 1), date(2026, 2, 28)))


class FinancialClosingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("closer", is_staff=True)
        self.school = School.objects.create(name="مدرسة الإغلاق", is_active=True)
        self.source = AcademicYear.objects.create(
            school=self.school, name="2025/2026", start_date=date(2025, 9, 1),
            end_date=date(2026, 6, 30), is_closed=True,
        )
        self.target = AcademicYear.objects.create(
            school=self.school, name="2026/2027", start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30), is_current=True,
        )
        self.student = Student.objects.create(student_number="CLOSE-1", full_name="طالب ترحيل", grade="الأول")
        self.category = FeeCategory.objects.create(name="رسوم إغلاق", amount=Decimal("1000"))
        self.invoice = StudentInvoice.objects.create(
            student=self.student, academic_year=self.source, fee_category=self.category,
            amount=Decimal("1000"), due_date=self.source.end_date,
        )
        StudentPayment.objects.create(invoice=self.invoice, amount=Decimal("250"), created_by=self.user)

    def test_close_carries_balance_once(self):
        closure = close_financial_year(
            school=self.school, source_year=self.source, target_year=self.target,
            user=self.user, notes="إغلاق اختباري",
        )
        self.assertEqual(closure.total_carried, Decimal("750"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "cancelled")
        carried = StudentInvoice.objects.get(academic_year=self.target, student=self.student)
        self.assertEqual(carried.amount, Decimal("750"))
        self.assertEqual(student_remaining(self.student), Decimal("750.00"))
        with self.assertRaises(ValidationError):
            close_financial_year(
                school=self.school, source_year=self.source, target_year=self.target,
                user=self.user,
            )

    def test_monthly_report_combines_income_and_expense(self):
        today = timezone.localdate()
        FeePayment.objects.create(
            school=self.school, receipt_number="PAY-MONTH-1", main_student=self.student,
            guardian_name="ولي الطالب", total_amount="200", total_due_before="1000",
            total_due_after="800", payment_method="cash", created_by=self.user,
        )
        ExpenseEntry.objects.create(
            school=self.school, expense_number="EXP-MONTH-1", expense_date=today,
            title="قرطاسية", amount="30", payment_method="cash", created_by=self.user,
        )
        report = monthly_financial_report(self.school)
        self.assertEqual(report["income"], Decimal("200"))
        self.assertEqual(report["expenses"], Decimal("30"))
        self.assertEqual(report["net"], Decimal("170"))


class MonthlyCanteenStatementTests(TestCase):
    def setUp(self):
        from core.models import School
        self.school = School.objects.create(name="مدرسة المقصف", is_active=True)
        self.user = User.objects.create_user("canteen", password="x", is_staff=True)

    def test_canteen_profit_and_closing_balance_use_invoices(self):
        from .models import CanteenTransaction, MonthlyFinancialStatement
        from .financial_services import monthly_financial_report

        CanteenTransaction.objects.create(
            school=self.school,
            transaction_type="income",
            transaction_date=date(2026, 7, 10),
            invoice_number="SALE-1",
            description="مبيعات المقصف",
            amount=Decimal("300"),
            payment_method="cash",
            created_by=self.user,
        )
        ExpenseEntry.objects.create(
            school=self.school,
            expense_number="EXP-CAN-1",
            expense_date=date(2026, 7, 11),
            title="مشتريات المقصف",
            source="canteen",
            supplier_invoice_number="SUP-1",
            amount=Decimal("120"),
            payment_method="cash",
            created_by=self.user,
        )
        report = monthly_financial_report(self.school, date(2026, 7, 31))
        self.assertEqual(report["canteen_income"], Decimal("300"))
        self.assertEqual(report["canteen_expenses"], Decimal("120"))
        self.assertEqual(report["canteen_profit"], Decimal("180"))
        self.assertEqual(report["closing_balance"], Decimal("180"))
        self.assertTrue(MonthlyFinancialStatement.objects.filter(school=self.school, period_end=date(2026, 7, 31)).exists())
