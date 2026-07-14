from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from students.models import Student

from .models import DiscountRequest, FeeCategory, Installment, Receipt, StudentInvoice, StudentPayment
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
