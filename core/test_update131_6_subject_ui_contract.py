from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.subject_ui_contracts import run_subject_ui_audit
from core.templatetags.opal_subjects import subject_colour


class Update1316SubjectUiContractTests(SimpleTestCase):
    def source(self, relative):
        return (Path(settings.BASE_DIR) / relative).read_text(encoding="utf-8")

    def test_release_identity(self):
        self.assertEqual(self.source("OPAL_VERSION.txt").strip(), "131.7")
        release_name = self.source("OPAL_RELEASE_NAME.txt").strip()
        self.assertIn(f'"version_name": "{release_name}"', self.source("OPAL_UPDATE_MANIFEST.json"))

    def test_subject_colour_validation(self):
        self.assertEqual(subject_colour("#12abEF"), "#12ABEF")
        self.assertEqual(subject_colour("bad"), "#64748B")

    def test_compact_role_gateways_are_deployed(self):
        css = self.source("static/css/opal_erp.css")
        self.assertIn(".opal-compact-module-grid", css)
        self.assertIn(".opal-compact-action-row", css)
        self.assertIn("grid-template-columns:repeat(3,minmax(0,1fr))!important", css)

    def test_subject_colour_coverage_is_deployed(self):
        for relative in (
            "templates/teachers/portal_dashboard.html",
            "templates/parent_portal/marks.html",
            "templates/students/student_360.html",
            "templates/exams/gradebook.html",
            "templates/parent_portal/timetable.html",
        ):
            source = self.source(relative)
            self.assertIn("opal-subject", source, relative)
            self.assertIn("subject_style", source, relative)


    def test_manager_dashboard_compact_coverage_is_deployed(self):
        template = self.source("dashboard/templates/dashboard/home.html")
        css = self.source("static/css/opal_dashboard_executive.css")
        base = self.source("templates/base/base.html")
        self.assertIn("opal-fixed-manager-dashboard", template)
        self.assertIn("opal-dashboard-subject-chip", template)
        self.assertIn("OPAL Update 131.7 — fixed crystal manager dashboard", css)
        self.assertIn("grid-template-columns:repeat(6,minmax(0,1fr))", css)
        self.assertIn("css/opal_dashboard_executive.css", base)

    def test_system_audit_passes(self):
        self.assertEqual(run_subject_ui_audit()["issues"], [])
