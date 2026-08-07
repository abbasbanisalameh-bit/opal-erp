from pathlib import Path
import ast
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Update129HorizontalTimetableContractTests(unittest.TestCase):
    def test_every_timetable_display_uses_one_day_row_matrix(self):
        templates = (
            "templates/timetable/dashboard.html",
            "templates/timetable/print.html",
            "templates/teachers/portal_timetable.html",
            "templates/teachers/portal_dashboard.html",
            "templates/teachers/teacher_detail.html",
            "templates/parent_portal/timetable.html",
            "templates/students/student_360.html",
        )
        for relative in templates:
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("opal-timetable-grid", source, relative)
            self.assertIn("اليوم / الحصة", source, relative)
            self.assertIn("opal-keep-grid", source, relative)

    def test_matrix_is_central_and_does_not_create_parallel_models_or_routes(self):
        workflow = (ROOT / "timetable/workflow.py").read_text(encoding="utf-8")
        self.assertIn("def build_horizontal_schedule_matrix", workflow)
        self.assertIn("item.time_slot.order", workflow)
        models = (ROOT / "timetable/models.py").read_text(encoding="utf-8")
        self.assertNotIn("class TimetableMatrix", models)
        self.assertNotIn("class HorizontalTimetable", models)

    def test_deployment_is_guarded_by_system_check(self):
        checks = (ROOT / "core/checks.py").read_text(encoding="utf-8")
        self.assertIn("def _horizontal_timetable_matrix_issues", checks)
        self.assertIn('id="opal.E130"', checks)
        self.assertIn('version != "131.7"', checks)

    def test_changed_python_files_parse(self):
        for relative in (
            "timetable/workflow.py",
            "teachers/views.py",
            "parent_portal/views.py",
            "students/student360.py",
        ):
            ast.parse((ROOT / relative).read_text(encoding="utf-8"), filename=relative)


if __name__ == "__main__":
    unittest.main()
