from pathlib import Path
import json
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class Update131SafeConsolidationContractTests(unittest.TestCase):
    def test_release_identity_and_cache_token(self):
        self.assertEqual(source("OPAL_VERSION.txt").strip(), "131.7")
        release_name = source("OPAL_RELEASE_NAME.txt").strip()
        runtime = source("core/update_engine_runtime.py")
        self.assertIn("def _code_release_identity", runtime)
        self.assertIn("name = code_name or", runtime)
        manifest = json.loads(source("OPAL_UPDATE_MANIFEST.json"))
        self.assertEqual(manifest["version"], "131.7")
        self.assertEqual(manifest["version_name"], release_name)
        self.assertTrue(manifest["code_only"])
        primary_tokens = re.findall(
            r"(?:opal_erp\.css|opal_dashboard_executive\.css|opal_entity_360_consolidation\.css|opal_erp\.js)' %\}\?v=([^\"\s]+)",
            source("templates/base/base.html"),
        )
        self.assertEqual(len(primary_tokens), 4)
        self.assertEqual(len(set(primary_tokens)), 1)

    def test_subject_is_the_single_annual_plan_source(self):
        models = source("academics/models.py")
        for token in (
            "academic_year = models.ForeignKey",
            "weekly_periods = models.PositiveSmallIntegerField",
            "is_required = models.BooleanField",
            "canonical_key = models.CharField",
            "color = models.CharField",
            "uniq_subject_name_per_year_grade",
        ):
            self.assertIn(token, models)
        self.assertNotRegex(source("curriculum/models.py"), r"(?m)^class\s+Curriculum\b")
        assignment = source("teachers/models.py").split("class TeacherAssignment", 1)[1]
        self.assertNotRegex(assignment, r"(?m)^\s+weekly_periods\s*=")

    def test_subject_migration_reuses_canonical_colour(self):
        migration = source("academics/migrations/0016_annual_subject_plan_stage.py")
        self.assertIn("if canonical not in colour_by_key:", migration)
        self.assertNotIn("colour_by_key.setdefault", migration)
        self.assertIn("reverse_unavailable", migration)

    def test_subject_final_model_state_has_explicit_migration(self):
        migration = source("academics/migrations/0018_alter_subject_canonical_key_alter_subject_grade.py")
        self.assertIn('name="canonical_key"', migration)
        self.assertIn('name="grade"', migration)
        self.assertIn("django.db.models.deletion.PROTECT", migration)
        self.assertNotIn("default=", migration)
        self.assertNotIn("blank=True", migration)

    def test_parallel_templates_are_removed(self):
        for relative in (
            "templates/curriculum/curriculum_form.html",
            "templates/curriculum/curriculum_list.html",
            "templates/timetable/smart_builder.html",
            "templates/exams/dashboard.html",
            "templates/exams/mark_list.html",
        ):
            self.assertFalse((ROOT / relative).exists(), relative)

    def test_legacy_routes_are_redirect_only_until_update_132(self):
        timetable = source("timetable/views.py")
        exams = source("exams/views.py")
        curriculum = source("curriculum/views.py")
        for text in (timetable, exams):
            self.assertIn('response["Deprecation"] = "true"', text)
            self.assertIn('response["Sunset"] = "OPAL Update 132.0"', text)
        self.assertIn('"Deprecation": "true"', curriculum)
        self.assertIn('"Sunset": "OPAL Update 132.0"', curriculum)
        all_templates = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "templates").rglob("*.html"))
        for route in (
            "timetable:smart_builder",
            "exams:gradebook",
            "exams:exam_dashboard",
            "exams:mark_list",
            "curriculum:curriculum_list",
        ):
            self.assertNotIn(route, all_templates)

    def test_operation_catalogue_has_one_material_plan_entry(self):
        catalogue = source("core/workflow_catalog.py")
        self.assertIn('_op("subjects", "academics", "المواد والخطة الدراسية"', catalogue)
        self.assertNotIn('_op("curriculum"', catalogue)
        self.assertIn('_op("timetable", "academics", "الجدول والمنشئ الذكي"', catalogue)
        self.assertNotIn('_op("smart-timetable"', catalogue)
        self.assertNotIn('"exam-analysis"', catalogue)
        gateway = source("templates/academics/academic_structure.html")
        self.assertEqual(gateway.count("academics:subject_list"), 1)
        self.assertEqual(gateway.count("timetable:dashboard"), 1)
        self.assertEqual(gateway.count("exams:exam_list"), 1)

    def test_teacher_attendance_is_exception_based(self):
        service = source("timetable/attendance_services.py")
        self.assertIn("No daily ``present`` rows are generated", service)
        self.assertIn("public_teacher_state", service)
        self.assertIn('"label": "معلم غائب"', service)
        self.assertIn('"label": "المعلم غير متاح"', service)
        self.assertNotRegex(
            service,
            r"TeacherAbsence\.objects\.(?:create|get_or_create|update_or_create)\([^)]*status\s*=\s*[\"']present",
        )

    def test_exam_analytics_are_normalized_and_preserve_ties(self):
        analytics = source("exams/analytics.py")
        self.assertIn("def _percentage", analytics)
        self.assertIn('key = (row["average"], row["exam_count"])', analytics)
        self.assertIn('row["rank"] <= rank_limit', analytics)
        self.assertIn('path("", views.gradebook, name="exam_list")', source("exams/urls.py"))

    def test_timetable_display_search_and_print_contract(self):
        template = source("templates/timetable/dashboard.html")
        css = source("static/css/opal_erp.css")
        js = source("static/js/opal_erp.js")
        self.assertIn('id="smart-builder"', template)
        self.assertIn('data-opal-instant-table="off"', template)
        self.assertIn("bodyRows.length < 30", js)
        self.assertIn("opal-screen-only", css)
        self.assertIn("@media print", css)

    def test_section_display_is_not_duplicated(self):
        grade_names = source("academics/grade_names.py")
        models = source("academics/models.py")
        self.assertIn('return f"شعبة {text}"', grade_names)
        self.assertIn('return class_display_name(self.grade.name if self.grade_id else "", self.name)', models)
        self.assertIn('return " ".join(part for part in (grade, section) if part)', grade_names)

    def test_tpi_has_one_update_131_engine(self):
        tpi = source("teachers/tpi.py")
        self.assertIn('TPI_VERSION = "TPI-131"', tpi)
        self.assertIn("وفق استثناءات الدوام المعتمدة إداريًا", tpi)
        self.assertIn("TeacherPerformanceSnapshot", source("teachers/models.py"))


if __name__ == "__main__":
    unittest.main()
