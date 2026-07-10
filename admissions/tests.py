from decimal import Decimal

from django.test import SimpleTestCase

from admissions.financial_services import distribute_amount


class FamilyPaymentDistributionTests(SimpleTestCase):
    def test_skips_fully_paid_students_and_splits_evenly(self):
        rows = [
            {"student": "A", "total": Decimal("100"), "paid": Decimal("100"), "remaining": Decimal("0")},
            {"student": "B", "total": Decimal("100"), "paid": Decimal("0"), "remaining": Decimal("100")},
            {"student": "C", "total": Decimal("100"), "paid": Decimal("50"), "remaining": Decimal("50")},
        ]
        data, left = distribute_amount(rows, Decimal("60"))
        self.assertEqual(left, Decimal("0.00"))
        self.assertEqual(data[0]["allocated"], Decimal("0.00"))
        self.assertEqual(data[1]["allocated"], Decimal("30.00"))
        self.assertEqual(data[2]["allocated"], Decimal("30.00"))

    def test_caps_each_student_at_remaining_balance(self):
        rows = [
            {"student": "A", "total": Decimal("10"), "paid": Decimal("0"), "remaining": Decimal("10")},
            {"student": "B", "total": Decimal("100"), "paid": Decimal("0"), "remaining": Decimal("100")},
        ]
        data, left = distribute_amount(rows, Decimal("50"))
        self.assertEqual(left, Decimal("0.00"))
        self.assertEqual(data[0]["allocated"], Decimal("10.00"))
        self.assertEqual(data[1]["allocated"], Decimal("40.00"))

    def test_returns_excess_for_validation(self):
        rows = [
            {"student": "A", "total": Decimal("10"), "paid": Decimal("0"), "remaining": Decimal("10")},
        ]
        data, left = distribute_amount(rows, Decimal("12.50"))
        self.assertEqual(data[0]["allocated"], Decimal("10.00"))
        self.assertEqual(left, Decimal("2.50"))
