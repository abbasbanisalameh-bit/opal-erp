from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]


class Update130ProductionStabilityContractTests(SimpleTestCase):
    def test_mobile_shell_is_viewport_bound_and_hides_page_overflow(self):
        css = (ROOT / "static/css/opal_erp.css").read_text(encoding="utf-8")
        self.assertIn(
            "OPAL Update 130: production timetable state and mobile containment",
            css,
        )
        self.assertIn("overflow-x: clip", css)
        self.assertIn("position: fixed !important", css)
        self.assertIn("width: min(86dvw, 330px) !important", css)
        self.assertIn("height: 100dvh !important", css)

    def test_interactive_timetables_render_the_current_lesson_state(self):
        templates = (
            "templates/timetable/dashboard.html",
            "templates/teachers/portal_timetable.html",
            "templates/teachers/portal_dashboard.html",
            "templates/teachers/teacher_detail.html",
            "templates/parent_portal/timetable.html",
            "templates/students/student_360.html",
        )
        for relative in templates:
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("day.is_today", source, relative)
            self.assertIn("item.is_current_lesson", source, relative)
            self.assertIn("opal-current-lesson-badge", source, relative)

    def test_legacy_admission_deletion_waits_for_document_fk_removal(self):
        source = (
            ROOT / "admissions/migrations/0013_delete_admissionapplication.py"
        ).read_text(encoding="utf-8")
        self.assertIn('("documents", "0007_remove_candidate_documents")', source)
        self.assertIn("DeleteModel", source)

    def test_release_identity_and_asset_cache_are_current(self):
        version = (ROOT / "OPAL_VERSION.txt").read_text(encoding="utf-8").strip()
        release_name = (ROOT / "OPAL_RELEASE_NAME.txt").read_text(encoding="utf-8").strip()
        manifest = (ROOT / "OPAL_UPDATE_MANIFEST.json").read_text(encoding="utf-8")
        base = (ROOT / "templates/base/base.html").read_text(encoding="utf-8")
        self.assertEqual(version, "131.7")
        self.assertIn(f'"version_name": "{release_name}"', manifest)
        self.assertRegex(base, r"opal_erp\.css' %\}\?v=[^\"\s]+")
        self.assertRegex(base, r"opal_erp\.js' %\}\?v=[^\"\s]+")

    def test_update_engine_keeps_verified_database_safety(self):
        source = (ROOT / "core/update_engine_runtime.py").read_text(encoding="utf-8")
        self.assertIn("PRAGMA quick_check", source)
        self.assertIn("def subprocess_backup", source)
        self.assertIn("for attempt in range(3)", source)
        self.assertIn("DEFAULT_DATABASE_SAFETY_KEEP = 5", source)
        self.assertIn("def _prune_database_safety_snapshots", source)
        self.assertIn("removed = _prune_database_safety_snapshots", source)
