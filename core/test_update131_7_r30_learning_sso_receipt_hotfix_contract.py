from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class R30LearningSSOReceiptHotfixContractTests(unittest.TestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_parent_and_teacher_middleware_allow_learning_gateway(self):
        parent = self.source("parent_portal/middleware.py")
        teacher = self.source("teachers/middleware.py")
        self.assertIn('"/learning/",', parent)
        self.assertIn('"/learning/",', teacher)

    def test_parent_receipt_copy_does_not_advertise_printing(self):
        template = self.source("templates/parent_portal/_guardian_receipt_history.html")
        self.assertIn("can_print_receipts", template)
        self.assertIn("family_receipt_print", template)
        intro = template.split("{% if receipt_history %}", 1)[0]
        self.assertNotIn("طباعة", intro)
        self.assertIn("ولي الأمر يقرأ فقط", intro)


if __name__ == "__main__":
    unittest.main()
