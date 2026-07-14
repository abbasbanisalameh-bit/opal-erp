from decimal import Decimal
from types import SimpleNamespace
from django.test import SimpleTestCase

from admissions.financial_services import money


class FinanceMoneyTests(SimpleTestCase):
    def test_money_rounding_is_stable(self):
        self.assertEqual(money("10.005"), Decimal("10.01"))

    def test_empty_value_is_zero(self):
        self.assertEqual(money(None), Decimal("0.00"))
