from datetime import date
from decimal import Decimal
import uuid

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from academics.models import Enrollment, Grade
from admissions.models import FeePayment
from core.models import AcademicYear, School
from parent_portal.models import Family, FamilyStudent
from students.models import Student

from .models import (
    FeeCategory,
    FinancialCarryForward,
    FinancialYearClosure,
    StudentInvoice,
    StudentPayment,
)
from .previous_debt_services import (
    create_previous_debt_payment,
    previous_debt_guardian_report,
    previous_debt_receipt_breakdown,
    previous_debt_summary,
    student_previous_debt_snapshot,
)


class PreviousDebtServicesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("debt-manager", password="x", is_staff=True)
        self.school = School.objects.create(name="مدرسة الذمم", is_active=True)
        self.oldest = AcademicYear.objects.create(
            school=self.school,
            name="2024/2025",
            start_date=date(2024, 9, 1),
            end_date=date(2025, 6, 30),
        )
        self.old = AcademicYear.objects.create(
            school=self.school,
            name="2025/2026",
            start_date=date(2025, 9, 1),
            end_date=date(2026, 6, 30),
        )
        self.current = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        self.grade_one = Grade.objects.create(school=self.school, name="الصف الأول", order=1)
        self.grade_two = Grade.objects.create(school=self.school, name="الصف الثاني", order=2)
        self.grade_three = Grade.objects.create(school=self.school, name="الصف الثالث", order=3)
        self.student = Student.objects.create(
            student_number="DEBT-1",
            full_name="طالب الذمم",
            grade=self.grade_three.name,
            guardian_name="ولي طالب الذمم",
            phone="0790000000",
        )
        Enrollment.objects.create(student=self.student, academic_year=self.oldest, grade=self.grade_one, status="completed")
        Enrollment.objects.create(student=self.student, academic_year=self.old, grade=self.grade_two, status="completed")
        Enrollment.objects.create(student=self.student, academic_year=self.current, grade=self.grade_three, status="active")
        self.family = Family.objects.create(school=self.school, guardian_name="ولي طالب الذمم", phone="0790000000")
        FamilyStudent.objects.create(family=self.family, student=self.student, is_active=True)
        self.category = FeeCategory.objects.create(name="رسوم دراسية", amount=Decimal("1000.00"))
        self.oldest_invoice = StudentInvoice.objects.create(
            student=self.student,
            academic_year=self.oldest,
            fee_category=self.category,
            amount=Decimal("200.00"),
            due_date=date(2025, 5, 1),
        )
        self.old_invoice = StudentInvoice.objects.create(
            student=self.student,
            academic_year=self.old,
            fee_category=self.category,
            amount=Decimal("1000.00"),
            due_date=date(2026, 5, 1),
        )
        StudentPayment.objects.create(
            invoice=self.old_invoice,
            amount=Decimal("250.00"),
            payment_method="cash",
            created_by=self.user,
        )
        self.current_invoice = StudentInvoice.objects.create(
            student=self.student,
            academic_year=self.current,
            fee_category=self.category,
            amount=Decimal("800.00"),
            due_date=date(2027, 5, 1),
        )

    def test_snapshot_uses_only_older_year_invoices_and_historical_grade(self):
        snapshot = student_previous_debt_snapshot(self.student, academic_year=self.current)
        self.assertTrue(snapshot["has_debt"])
        self.assertEqual(snapshot["total"], Decimal("950.00"))
        self.assertEqual([row["academic_year"] for row in snapshot["rows"]], [self.oldest, self.old])
        self.assertEqual(snapshot["rows"][0]["grade_label"], self.grade_one.name)
        self.assertEqual(snapshot["rows"][1]["grade_label"], self.grade_two.name)
        self.assertNotIn(self.current.name, snapshot["years_text"])

    def test_legacy_carry_target_is_not_counted_twice_when_sources_exist(self):
        target_invoice = StudentInvoice.objects.create(
            student=self.student,
            academic_year=self.old,
            fee_category=self.category,
            amount=Decimal("200.00"),
            due_date=date(2026, 6, 1),
        )
        closure = FinancialYearClosure.objects.create(
            school=self.school,
            source_year=self.oldest,
            target_year=self.old,
            total_carried=Decimal("200.00"),
            closed_by=self.user,
        )
        carry = FinancialCarryForward.objects.create(
            closure=closure,
            student=self.student,
            amount=Decimal("200.00"),
            target_invoice=target_invoice,
        )
        carry.source_invoices.add(self.oldest_invoice)

        snapshot = student_previous_debt_snapshot(self.student, academic_year=self.current)
        self.assertEqual(snapshot["total"], Decimal("950.00"))
        invoice_ids = {
            row["invoice"].pk
            for year in snapshot["rows"]
            for row in year["invoices"]
        }
        self.assertNotIn(target_invoice.pk, invoice_ids)

    def test_payment_reduces_oldest_debt_only_and_never_touches_current_year(self):
        payment = create_previous_debt_payment(
            student=self.student,
            amount=Decimal("300.00"),
            user=self.user,
            payment_method="cash",
            operation_token=uuid.uuid4(),
            academic_year=self.current,
        )
        self.oldest_invoice.refresh_from_db()
        self.old_invoice.refresh_from_db()
        self.current_invoice.refresh_from_db()
        self.assertEqual(self.oldest_invoice.remaining, Decimal("0.00"))
        self.assertEqual(self.old_invoice.remaining, Decimal("650.00"))
        self.assertEqual(self.current_invoice.remaining, Decimal("800.00"))
        self.assertEqual(payment.total_due_before, Decimal("950.00"))
        self.assertEqual(payment.total_due_after, Decimal("650.00"))
        self.assertEqual(payment.allocations.count(), 2)
        breakdown = previous_debt_receipt_breakdown(payment)
        self.assertTrue(breakdown["is_previous_debt"])
        self.assertEqual([row["academic_year"] for row in breakdown["rows"]], [self.oldest, self.old])

    def test_old_receipt_is_not_mislabelled_without_previous_debt_marker(self):
        payment = create_previous_debt_payment(
            student=self.student,
            amount=Decimal("50.00"),
            user=self.user,
            payment_method="cash",
            operation_token=uuid.uuid4(),
            academic_year=self.current,
        )
        payment.notes = "دفعة رسوم عادية"
        payment.save(update_fields=["notes"])
        self.assertFalse(previous_debt_receipt_breakdown(payment)["is_previous_debt"])

    def test_invalid_amount_is_rejected_without_partial_records(self):
        with self.assertRaises(ValidationError):
            create_previous_debt_payment(
                student=self.student,
                amount="ليس رقمًا",
                user=self.user,
                payment_method="cash",
                operation_token=uuid.uuid4(),
                academic_year=self.current,
            )
        self.assertFalse(FeePayment.objects.exists())

    def test_overpayment_is_rejected_without_partial_records(self):
        with self.assertRaises(ValidationError):
            create_previous_debt_payment(
                student=self.student,
                amount=Decimal("951.00"),
                user=self.user,
                payment_method="cash",
                operation_token=uuid.uuid4(),
                academic_year=self.current,
            )
        self.assertFalse(FeePayment.objects.exists())
        self.assertEqual(self.oldest_invoice.payments.filter(status="posted").count(), 0)
        self.assertEqual(self.old_invoice.payments.filter(status="posted").count(), 1)

    def test_lightweight_summary_matches_canonical_outstanding_debt(self):
        summary = previous_debt_summary(school=self.school, academic_year=self.current)
        self.assertEqual(summary["total"], Decimal("950.00"))
        self.assertEqual(summary["guardians_count"], 1)
        self.assertEqual(summary["students_count"], 1)

    def test_guardian_report_groups_children_and_receipt_remaining(self):
        payment = create_previous_debt_payment(
            student=self.student,
            amount=Decimal("300.00"),
            user=self.user,
            payment_method="cash",
            operation_token=uuid.uuid4(),
            academic_year=self.current,
        )
        report = previous_debt_guardian_report(school=self.school, academic_year=self.current)
        self.assertEqual(report["total"], Decimal("650.00"))
        self.assertEqual(report["guardians_count"], 1)
        self.assertEqual(report["students_count"], 1)
        guardian = report["rows"][0]
        self.assertEqual(guardian["family"], self.family)
        self.assertEqual(guardian["children"][0]["student"], self.student)
        receipt = next(row for row in guardian["receipts"] if row["receipt_number"] == payment.receipt_number)
        self.assertEqual(receipt["amount"], Decimal("300.00"))
        self.assertEqual(receipt["remaining_after"], Decimal("650.00"))
