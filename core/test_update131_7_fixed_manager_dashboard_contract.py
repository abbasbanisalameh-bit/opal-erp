from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.fixed_dashboard_contracts import run_fixed_dashboard_audit


class Update1317FixedManagerDashboardContractTests(SimpleTestCase):
    def source(self, relative):
        return (Path(settings.BASE_DIR) / relative).read_text(encoding="utf-8")

    def test_release_identity(self):
        self.assertEqual(self.source("OPAL_VERSION.txt").strip(), "131.7")
        release_name = self.source("OPAL_RELEASE_NAME.txt").strip()
        self.assertIn(f'"version_name": "{release_name}"', self.source("OPAL_UPDATE_MANIFEST.json"))

    def test_customizer_is_retired(self):
        root = Path(settings.BASE_DIR)
        template = self.source("dashboard/templates/dashboard/home.html")
        views = self.source("dashboard/views.py")
        self.assertNotIn("opal-dashboard-layout-form", template)
        self.assertNotIn("opal-dashboard-layout-data", template)
        self.assertNotIn("save_dashboard_layout", views)
        self.assertFalse((root / "dashboard/layout.py").exists())
        self.assertFalse((root / "static/js/opal_dashboard_layout.js").exists())

    def test_requested_order_and_fixed_sections(self):
        template = self.source("dashboard/templates/dashboard/home.html")
        markers = [
            "opal-manager-quick-row",
            "opal-teacher-performance-row",
            "opal-top-students-panel",
            "opal-satisfaction-fixed",
            "مصادر التقييم وملخص المتابعة",
            "الإيرادات والمتأخرون عن السداد",
            "المعلمون المشغولون والمتفرغون",
            "opal-live-operation-title",
            "opal-actions-fixed-row",
            "غياب الطلبة والمعلمين اليوم",
            "opal-latest-students-title",
        ]
        positions = [template.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))

    def test_latest_students_and_top_grade_matrix(self):
        workflow = self.source("dashboard/workflow.py")
        self.assertIn('latest_enrollments = Enrollment.objects.filter(', workflow)
        self.assertIn("top_students_matrix", workflow)
        self.assertIn('row.get("rank") == 1', workflow)

    def test_crystal_visual_contract(self):
        css = self.source("static/css/opal_theme_system.css")
        self.assertIn("fixed crystal manager dashboard", css)
        self.assertIn("border:1px dashed rgba(216,173,79", css)
        self.assertIn("grid-template-columns:repeat(6,minmax(0,1fr))", css)

    def test_system_audit_passes(self):
        self.assertEqual(run_fixed_dashboard_audit()["issues"], [])
