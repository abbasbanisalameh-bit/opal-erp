from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class ReceiptPrintUpdate123Tests(SimpleTestCase):
    def _template(self, name):
        return (Path(settings.BASE_DIR) / "templates" / "admissions" / name).read_text(encoding="utf-8")

    def test_fee_receipt_is_standalone_two_copy_landscape_sheet(self):
        text = self._template("fee_payment_receipt.html")
        self.assertNotIn('{% extends "base/base.html" %}', text)
        self.assertIn("{% for copy_title in receipt_copies %}", text)
        self.assertIn("size:A4 landscape", text)
        self.assertIn("grid-template-columns:1fr 1fr", text)
        self.assertIn(".screen-toolbar{display:none!important}", text)

    def test_registration_receipt_is_standalone_two_copy_landscape_sheet(self):
        text = self._template("registration_receipt.html")
        self.assertNotIn('{% extends "base/base.html" %}', text)
        self.assertIn("{% for copy_title in receipt_copies %}", text)
        self.assertIn("size:A4 landscape", text)
        self.assertIn("grid-template-columns:1fr 1fr", text)
        self.assertIn(".screen-toolbar{display:none!important}", text)
