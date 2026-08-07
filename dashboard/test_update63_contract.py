from django.test import SimpleTestCase

from .workflow import build_attendance_detail_context


class Update63ContractTests(SimpleTestCase):
    def test_attendance_detail_entry_point_exists(self):
        self.assertTrue(callable(build_attendance_detail_context))

    def test_dashboard_template_uses_compact_sections(self):
        from pathlib import Path
        template = Path(__file__).parent / "templates" / "dashboard" / "home.html"
        content = template.read_text(encoding="utf-8")
        self.assertIn("opal-fixed-manager-dashboard", content)
        self.assertIn("no_recent_payment_students", content)
        self.assertNotIn('id="attendanceTrendChart"', content)
