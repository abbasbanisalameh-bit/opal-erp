from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class R33ProductionReadinessAlignmentContractTests(unittest.TestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_card_codes_use_one_secure_generator(self):
        generator = self.source("learning_platform/card_codes.py")
        forms = self.source("learning_platform/forms.py")
        payment = self.source("learning_platform/payment_services.py")
        demo = self.source("core/system_data.py")
        self.assertIn('CARD_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"', generator)
        self.assertIn("secrets.choice", generator)
        self.assertIn("generate_unique_card_code", forms)
        self.assertIn("generate_unique_card_code", payment)
        self.assertIn("generate_unique_card_codes", demo)
        self.assertNotIn('code=f"DEMO-{student.student_number}"', demo)
        self.assertNotIn('f"PAID-{order.pk:08d}', payment)

    def test_readiness_supports_card_sales_without_gateway(self):
        production = self.source("learning_platform/production.py")
        registry = self.source("config/learning_production_registry.py")
        self.assertIn("OPAL_LEARNING_SUBSCRIPTION_SALES_MODE", registry)
        self.assertIn('{"cards", "manual", "payment"}', registry)
        self.assertIn('if sales_mode == "cards":', production)
        self.assertIn("لا تُشترط بوابة دفع خارجية", production)
        self.assertIn('requirement="hosting"', production)
        self.assertIn("warning_breakdown", production)

    def test_current_semester_audit_respects_calendar_boundaries(self):
        audit = self.source("core/operation_audit.py")
        self.assertIn("reference_date = timezone.localdate()", audit)
        self.assertIn("semesters__start_date__lte=reference_date", audit)
        self.assertIn("semesters__end_date__gte=reference_date", audit)
        self.assertIn("خارج حدود الفصل أو أثناء العطلة لا يلزم فصل حالي", audit)

    def test_live_environment_can_write_exact_dependency_lock(self):
        command = self.source("learning_platform/management/commands/write_learning_dependency_lock.py")
        self.assertIn('[sys.executable, "-m", "pip", "freeze"]', command)
        self.assertIn('requirements-lock-r20.txt', command)
        self.assertIn('django==', command)
        self.assertIn('pillow==', command)


if __name__ == "__main__":
    unittest.main()
