from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]
TEACHER_VIEWS = ROOT / "teachers" / "views.py"
TEACHER_LIST_TEMPLATE = ROOT / "templates" / "teachers" / "teacher_list.html"


class Update131TeacherListHotfixContractTests(SimpleTestCase):
    def test_teacher_list_does_not_recalculate_school_tpi(self):
        source = TEACHER_VIEWS.read_text(encoding="utf-8")
        block = source[source.index("def teacher_list"):source.index("def teacher_create")]
        self.assertNotIn("management_tpi_context", block)
        self.assertIn("TeacherPerformanceSnapshot.objects.filter", block)
        self.assertIn("period=tpi_period", block)

    def test_manager_can_still_enter_active_linked_teacher_account(self):
        template = TEACHER_LIST_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("request.user.is_superuser", template)
        self.assertIn("accounts:impersonate_user", template)
        self.assertIn("teacher.user.is_active", template)
        self.assertIn("الدخول بحسابه", template)
