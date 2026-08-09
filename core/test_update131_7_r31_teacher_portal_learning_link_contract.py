from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class R31TeacherPortalLearningLinkContractTests(unittest.TestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_teacher_portal_passes_learning_access_flag(self):
        source = self.source("teachers/views.py")
        portal = source.split("def portal_dashboard(request):", 1)[1].split("def portal_workspace", 1)[0]
        self.assertIn('"learning_platform_enabled": teacher_learning_access(teacher)', portal)

    def test_teacher_portal_template_has_learning_platform_link(self):
        template = self.source("templates/teachers/portal_dashboard.html")
        self.assertIn("{% if learning_platform_enabled %}", template)
        self.assertIn("learning_platform:erp_teacher_entry", template)
        self.assertIn("منصة أوبال التعليمية", template)

    def test_teacher_access_remains_controlled_by_school_setting(self):
        bridge = self.source("learning_platform/school_bridge.py")
        self.assertIn("def teacher_learning_access(teacher):", bridge)
        self.assertIn("teacher_sso_enabled", bridge)


if __name__ == "__main__":
    unittest.main()
