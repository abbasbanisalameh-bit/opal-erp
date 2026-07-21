from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from students.models import Student

from .invoice_list_services import build_invoice_list_context
from .models import FeeCategory, StudentInvoice, StudentPayment


class InvoiceListServiceContractTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            student_number="LIST-51",
            full_name="طالب قائمة الفواتير",
            grade="الأول",
        )
        self.other_student = Student.objects.create(
            student_number="LIST-OTHER",
            full_name="طالب آخر",
            grade="الثاني",
        )
        self.category = FeeCategory.objects.create(name="رسوم قائمة", amount=Decimal("100"))
        self.overdue_invoice = StudentInvoice.objects.create(
            student=self.student,
            fee_category=self.category,
            amount=Decimal("100"),
            due_date=timezone.localdate() - timedelta(days=1),
        )
        StudentPayment.objects.create(invoice=self.overdue_invoice, amount=Decimal("25"))
        self.future_invoice = StudentInvoice.objects.create(
            student=self.other_student,
            fee_category=self.category,
            amount=Decimal("80"),
            due_date=timezone.localdate() + timedelta(days=5),
        )

    def test_context_preserves_filters_and_attaches_financial_snapshot(self):
        context = build_invoice_list_context(query="LIST-51")

        self.assertEqual(context["filters"], {"status": "", "q": "LIST-51", "overdue": False})
        self.assertEqual(context["invoices"], [self.overdue_invoice])
        snapshot = context["invoices"][0].financial_snapshot
        self.assertEqual(snapshot["total_paid"], Decimal("25"))
        self.assertEqual(snapshot["remaining"], Decimal("75"))
        self.assertEqual(snapshot["status"], "partial")

    def test_overdue_filter_keeps_current_invoice_rules(self):
        context = build_invoice_list_context(overdue=True)

        self.assertEqual(context["invoices"], [self.overdue_invoice])
        self.assertTrue(context["filters"]["overdue"])
