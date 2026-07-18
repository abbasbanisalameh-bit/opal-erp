from decimal import Decimal

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase
from django.utils import timezone

from accounting.models import FeeCategory, Receipt, StudentInvoice, StudentPayment
from admissions.models import FeePayment, FeePaymentAllocation
from core.models import School
from students.models import Student

from .receipt_services import build_guardian_receipt_history


class GuardianReceiptHistoryTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة الاختبار")
        self.cashier = get_user_model().objects.create_user(username="cashier")
        self.first = Student.objects.create(
            student_number="REC-1", full_name="الطالب الأول", grade="الأول"
        )
        self.second = Student.objects.create(
            student_number="REC-2", full_name="الطالب الثاني", grade="الثاني"
        )

    def test_history_combines_canonical_and_older_receipts_with_allocations(self):
        canonical = FeePayment.objects.create(
            school=self.school,
            receipt_number="FEE-100",
            scope="all_siblings",
            main_student=self.first,
            total_amount=Decimal("150.00"),
            total_due_before=Decimal("500.00"),
            total_due_after=Decimal("350.00"),
            created_by=self.cashier,
        )
        FeePaymentAllocation.objects.create(
            fee_payment=canonical,
            student=self.first,
            amount=Decimal("75.00"),
        )
        FeePaymentAllocation.objects.create(
            fee_payment=canonical,
            student=self.second,
            amount=Decimal("75.00"),
        )

        category = FeeCategory.objects.create(name="رسوم سابقة", amount=Decimal("90.00"))
        invoice = StudentInvoice.objects.create(
            student=self.first,
            fee_category=category,
            amount=Decimal("90.00"),
            due_date=timezone.localdate(),
        )
        older_payment = StudentPayment.objects.create(
            invoice=invoice,
            amount=Decimal("90.00"),
            created_by=self.cashier,
        )
        Receipt.objects.create(payment=older_payment, receipt_number="OLD-9")

        history = build_guardian_receipt_history([self.first, self.second])

        self.assertEqual({item["receipt_number"] for item in history}, {"FEE-100", "OLD-9"})
        canonical_row = next(item for item in history if item["receipt_number"] == "FEE-100")
        self.assertEqual(canonical_row["receiver"], "cashier")
        self.assertEqual(
            {item["student_name"] for item in canonical_row["allocations"]},
            {"الطالب الأول", "الطالب الثاني"},
        )

    def test_receipt_component_is_read_only_without_open_or_print_links(self):
        html = render_to_string(
            "parent_portal/_guardian_receipt_history.html",
            {
                "receipt_history": [
                    {
                        "receipt_number": "READ-1",
                        "created_at": timezone.now(),
                        "amount": Decimal("20.00"),
                        "payment_type": "تسديد رسوم طالب",
                        "children_names": "طالب اختبار",
                        "receiver": "المحاسب",
                        "receiver_title": "محاسب",
                        "status_label": "معتمد",
                        "allocations": [
                            {"student_name": "طالب اختبار", "amount": Decimal("20.00")}
                        ],
                    }
                ]
            },
        )
        self.assertNotIn("<a ", html)
        self.assertNotIn("طباعة", html)
        self.assertIn("توزيع المبلغ", html)
