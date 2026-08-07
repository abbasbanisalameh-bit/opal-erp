from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class Update131SmartTimetableContractTests(TestCase):
    def test_smart_builder_is_merged_into_existing_dashboard_template(self):
        names = {path.name for path in (ROOT / "templates" / "timetable").glob("*.html")}
        self.assertIn("dashboard.html", names)
        self.assertNotIn("smart_builder.html", names)
        source = (ROOT / "templates" / "timetable" / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn('id="smart-builder"', source)
        self.assertIn('value="builder_preview"', source)
        self.assertIn('value="builder_apply"', source)
        self.assertIn('name="source_fingerprint"', source)

    def test_no_parallel_timetable_model_or_new_route(self):
        models_source = (ROOT / "timetable" / "models.py").read_text(encoding="utf-8")
        urls_source = (ROOT / "timetable" / "urls.py").read_text(encoding="utf-8")
        self.assertNotIn("class TimetableDraft", models_source)
        self.assertNotIn("class SmartTimetable", models_source)
        self.assertNotIn("draft/", urls_source)
        self.assertNotIn("proposal/", urls_source)
        self.assertEqual(urls_source.count('path("smart-builder/"'), 1)

    def test_legacy_route_is_redirect_only_and_sunset_next_update(self):
        source = (ROOT / "timetable" / "views.py").read_text(encoding="utf-8")
        self.assertIn('def smart_builder(request):', source)
        self.assertIn('reverse("timetable:dashboard") + "#smart-builder"', source)
        self.assertIn('response["Deprecation"] = "true"', source)
        self.assertIn('response["Sunset"] = "OPAL Update 132.0"', source)

    def test_engine_uses_annual_subject_plan_fingerprint_and_atomic_approval(self):
        source = (ROOT / "timetable" / "services.py").read_text(encoding="utf-8")
        for token in (
            "Subject.objects.filter",
            "BREAK_MARGIN_MINUTES = 120",
            "source_fingerprint",
            "official_entries",
            "transaction.atomic()",
            "CANONICAL_WORKING_DAYS",
            "teacher_day_caps",
        ):
            self.assertIn(token, source)
        self.assertNotIn("Curriculum.objects.filter", source)
