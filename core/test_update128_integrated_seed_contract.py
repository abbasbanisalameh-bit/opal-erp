from pathlib import Path
import ast
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Update128IntegratedSeedContractTests(unittest.TestCase):
    def test_seed_uses_latest_smart_timetable_chain(self):
        source = (ROOT / "core" / "system_data.py").read_text(encoding="utf-8")
        self.assertIn("build_smart_timetable(", source)
        self.assertIn("apply=True", source)
        self.assertIn("_validate_integrated_academic_demo", source)
        self.assertIn('weekend_days="friday,saturday"', source)
        self.assertGreaterEqual(source.count('event_type="break"'), 2)
        self.assertIn('("استراحة الصفوف الأساسية الدنيا", range(1, 5), 2)', source)
        self.assertIn('("استراحة الصفوف الأساسية العليا", range(5, 9), 3)', source)
        self.assertIn('("استراحة الصفوف الثانوية", range(9, 13), 4)', source)

    def test_no_model_template_or_route_is_added_for_the_seed(self):
        models = (ROOT / "timetable" / "models.py").read_text(encoding="utf-8")
        self.assertNotIn("class Demo", models)
        self.assertNotIn("class Seed", models)
        urls = (ROOT / "core" / "urls.py").read_text(encoding="utf-8")
        self.assertNotIn("seed-demo", urls)
        self.assertFalse((ROOT / "templates" / "core" / "demo_result.html").exists())

    def test_python_files_parse(self):
        for relative in (
            "core/system_data.py",
            "core/views.py",
            "core/management/commands/seed_demo_school.py",
            "core/tests.py",
        ):
            ast.parse((ROOT / relative).read_text(encoding="utf-8"), filename=relative)


if __name__ == "__main__":
    unittest.main()
