from datetime import date
from decimal import Decimal
import uuid

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from admissions.financial_services import (
    build_family_payment_preview,
    create_siblings_fee_payment,
    student_finance_snapshot,
    student_separated_finance_snapshot,
)
from admissions.models import FeePayment
from core.models import AcademicYear, School
from parent_portal.models import Family, FamilyStudent
from students.models import Student

from .financial_services import collection_dashboard
from .invoice_list_services import build_invoice_list_context
from .models import (
    FeeCategory,
    FinancialCarryForward,
    FinancialYearClosure,
    StudentInvoice,
    StudentPayment,
)


class FeeYearSeparationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("year-fee-manager", password="x", is_staff=True)
        self.school = School.objects.create(name="مدرسة فصل الرسوم", is_active=True)
        self.previous_year = AcademicYear.objects.create(
            school=self.school,
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 6, 30),
        )
        self.current_year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        self.category = FeeCategory.objects.create(name="رسوم دراسية", amount=Decimal("600.00"))
        self.first = Student.objects.create(
            student_number="SEP-1",
            full_name="الطالب الأول",
            guardian_name="ولي الفصل",
            phone="0790000001",
        )
        self.second = Student.objects.create(
            student_number="SEP-2",
            full_name="الطالب الثاني",
            guardian_name="ولي الفصل",
            phone="0790000001",
        )
        family = Family.objects.create(
            school=self.school,
            guardian_name="ولي الفصل",
            phone="0790000001",
        )
        FamilyStudent.objects.create(family=family, student=self.first, is_active=True)
        FamilyStudent.objects.create(family=family, student=self.second, is_active=True)

        self.first_previous = StudentInvoice.objects.create(
            student=self.first,
            academic_year=self.previous_year,
            fee_category=self.category,
            amount=Decimal("300.00"),
            due_date=date(2026, 5, 1),
        )
        StudentPayment.objects.create(
            invoice=self.first_previous,
            amount=Decimal("50.00"),
            payment_method="cash",
            created_by=self.user,
        )
        self.second_previous = StudentInvoice.objects.create(
            student=self.second,
            academic_year=self.previous_year,
            fee_category=self.category,
            amount=Decimal("400.00"),
            due_date=date(2026, 5, 1),
        )
        self.first_current = StudentInvoice.objects.create(
            student=self.first,
            academic_year=self.current_year,
            fee_category=self.category,
            amount=Decimal("500.00"),
            due_date=date(2027, 5, 1),
        )
        StudentPayment.objects.create(
            invoice=self.first_current,
            amount=Decimal("100.00"),
            payment_method="cash",
            created_by=self.user,
        )
        self.second_current = StudentInvoice.objects.create(
            student=self.second,
            academic_year=self.current_year,
            fee_category=self.category,
            amount=Decimal("600.00"),
            due_date=date(2027, 5, 1),
        )
        # A legacy carry target can coexist with its authoritative source
        # invoices in older data. It must never be counted or paid as a
        # current-year fee.
        self.compatibility_target = StudentInvoice.objects.create(
            student=self.first,
            academic_year=self.current_year,
            fee_category=self.category,
            amount=Decimal("250.00"),
            due_date=date(2026, 9, 15),
        )
        closure = FinancialYearClosure.objects.create(
            school=self.school,
            source_year=self.previous_year,
            target_year=self.current_year,
            total_carried=Decimal("250.00"),
            closed_by=self.user,
        )
        carry = FinancialCarryForward.objects.create(
            closure=closure,
            student=self.first,
            amount=Decimal("250.00"),
            target_invoice=self.compatibility_target,
        )
        carry.source_invoices.add(self.first_previous)

    def test_snapshot_exposes_current_and_previous_balances_separately(self):
        current = student_finance_snapshot(self.first, academic_year=self.current_year)
        separated = student_separated_finance_snapshot(
            self.first,
            academic_year=self.current_year,
        )

        self.assertEqual(current["total"], Decimal("500.00"))
        self.assertEqual(current["paid"], Decimal("100.00"))
        self.assertEqual(current["remaining"], Decimal("400.00"))
        self.assertEqual(separated["previous"]["total"], Decimal("250.00"))
        self.assertEqual(separated["combined_remaining"], Decimal("650.00"))

    def test_legacy_carry_target_is_not_a_current_year_fee(self):
        current = student_finance_snapshot(self.first, academic_year=self.current_year)

        self.assertEqual(current["total"], Decimal("500.00"))
        self.assertEqual(current["remaining"], Decimal("400.00"))

    def test_collection_dashboard_publishes_separated_totals(self):
        dashboard = collection_dashboard(self.school)

        self.assertEqual(dashboard["current_fees"], Decimal("1100.00"))
        self.assertEqual(dashboard["current_paid"], Decimal("100.00"))
        self.assertEqual(dashboard["current_remaining"], Decimal("1000.00"))
        self.assertEqual(dashboard["previous_remaining"], Decimal("650.00"))
        self.assertEqual(dashboard["combined_remaining"], Decimal("1650.00"))

    def test_invoice_list_period_filter_keeps_years_separate(self):
        current = build_invoice_list_context(
            academic_year=self.current_year,
            period="current",
        )
        previous = build_invoice_list_context(
            academic_year=self.current_year,
            period="previous",
        )

        self.assertEqual(
            {invoice.pk for invoice in current["invoices"]},
            {self.first_current.pk, self.second_current.pk},
        )
        self.assertEqual(
            {invoice.pk for invoice in previous["invoices"]},
            {self.first_previous.pk, self.second_previous.pk},
        )

    def test_family_preview_uses_current_year_only(self):
        preview = build_family_payment_preview(
            self.first,
            Decimal("200.00"),
            academic_year=self.current_year,
        )

        self.assertEqual(preview["due_before"], Decimal("1000.00"))
        self.assertEqual(preview["due_after"], Decimal("800.00"))
        self.assertEqual([row["allocated"] for row in preview["rows"]], [Decimal("100.00"), Decimal("100.00")])

    def test_family_payment_never_touches_previous_year_invoices(self):
        payment = create_siblings_fee_payment(
            main_student=self.first,
            amount=Decimal("200.00"),
            user=self.user,
            payment_method="cash",
            operation_token=uuid.uuid4(),
        )

        self.first_previous.refresh_from_db()
        self.second_previous.refresh_from_db()
        self.first_current.refresh_from_db()
        self.second_current.refresh_from_db()
        self.compatibility_target.refresh_from_db()
        self.assertEqual(self.first_previous.remaining, Decimal("250.00"))
        self.assertEqual(self.second_previous.remaining, Decimal("400.00"))
        self.assertEqual(self.first_current.remaining, Decimal("300.00"))
        self.assertEqual(self.second_current.remaining, Decimal("500.00"))
        self.assertEqual(self.compatibility_target.remaining, Decimal("250.00"))
        self.assertFalse(self.compatibility_target.payments.exists())
        self.assertEqual(payment.total_due_before, Decimal("1000.00"))
        self.assertEqual(payment.total_due_after, Decimal("800.00"))
        self.assertEqual(payment.payment_period, "current")
        self.assertEqual(payment.payment_period_label, "رسوم السنة الحالية")

    def test_amount_above_current_due_is_rejected_even_when_previous_due_exists(self):
        with self.assertRaises(ValidationError):
            create_siblings_fee_payment(
                main_student=self.first,
                amount=Decimal("1000.01"),
                user=self.user,
                payment_method="cash",
                operation_token=uuid.uuid4(),
            )

        self.assertFalse(FeePayment.objects.exists())
        self.assertEqual(self.first_previous.payments.filter(status="posted").count(), 1)
        self.assertEqual(self.second_previous.payments.filter(status="posted").count(), 0)
        self.assertEqual(self.first_current.payments.filter(status="posted").count(), 1)
        self.assertEqual(self.second_current.payments.filter(status="posted").count(), 0)

    def test_old_balance_alone_is_not_payable_from_current_year_route(self):
        self.first_current.status = "cancelled"
        self.first_current.save(update_fields=["status"])
        self.second_current.status = "cancelled"
        self.second_current.save(update_fields=["status"])

        with self.assertRaisesMessage(ValidationError, "جميع أبناء ولي الأمر مسددون بالكامل"):
            create_siblings_fee_payment(
                main_student=self.first,
                amount=Decimal("10.00"),
                user=self.user,
                payment_method="cash",
                operation_token=uuid.uuid4(),
            )

        self.assertEqual(self.first_previous.remaining, Decimal("250.00"))
        self.assertEqual(self.second_previous.remaining, Decimal("400.00"))
