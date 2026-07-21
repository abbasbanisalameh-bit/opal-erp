from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase

from .student360 import _build_finance_profile


class StudentFinanceProfileContractTests(SimpleTestCase):
    @patch("students.student360.student_finance_snapshot")
    def test_partial_finance_profile_preserves_labels_and_rate(self, snapshot):
        snapshot.return_value = {
            "total": Decimal("1000.00"),
            "paid": Decimal("250.00"),
            "remaining": Decimal("750.00"),
            "status": "partial",
        }
        student = object()

        profile = _build_finance_profile(student)

        snapshot.assert_called_once_with(student)
        self.assertEqual(profile["total"], Decimal("1000.00"))
        self.assertEqual(profile["paid"], Decimal("250.00"))
        self.assertEqual(profile["remaining"], Decimal("750.00"))
        self.assertEqual(profile["status"], "partial")
        self.assertEqual(profile["status_label"], "مسدد جزئيًا")
        self.assertEqual(profile["status_class"], "warning")
        self.assertEqual(profile["payment_rate"], 25.0)

    @patch("students.student360.student_finance_snapshot")
    def test_zero_total_has_stable_zero_payment_rate(self, snapshot):
        snapshot.return_value = {
            "total": Decimal("0.00"),
            "paid": Decimal("0.00"),
            "remaining": Decimal("0.00"),
            "status": "paid",
        }

        profile = _build_finance_profile(object())

        self.assertEqual(profile["payment_rate"], 0)
        self.assertEqual(profile["status_label"], "مسدد بالكامل")
        self.assertEqual(profile["status_class"], "success")
