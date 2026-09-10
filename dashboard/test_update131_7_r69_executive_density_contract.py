from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "dashboard" / "templates" / "dashboard" / "home.html"
CSS = ROOT / "static" / "css" / "opal_dashboard_executive.css"


class Update1317R69ExecutiveDensityContractTests(SimpleTestCase):
    def test_zero_previous_debt_uses_clear_state(self):
        source = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("opal-previous-debt-dashboard-bar {% if previous_debt_total %}has-debt{% else %}is-clear{% endif %}", source)
        self.assertIn("لا توجد متبقيات رسوم سابقة مسجلة على الطلبة", source)

    def test_empty_teacher_evaluations_do_not_render_two_large_blank_panels(self):
        source = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("{% if teacher_evaluation_total %}", source)
        self.assertIn("opal-dashboard-data-empty opal-teacher-evaluations-empty", source)
        self.assertIn("لذلك لم يعرض النظام ترتيبًا أو مخططًا فارغًا", source)

    def test_adaptive_empty_state_and_clear_finance_styles_exist(self):
        source = CSS.read_text(encoding="utf-8")
        self.assertIn("OPAL Update 131.7 R69", source)
        self.assertIn("opal-previous-debt-dashboard-bar.is-clear", source)
        self.assertIn("opal-dashboard-data-empty", source)
