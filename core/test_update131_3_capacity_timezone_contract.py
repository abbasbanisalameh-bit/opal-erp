from pathlib import Path
import ast
from collections import Counter, defaultdict
import random
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Update1313CapacityTimezoneContractTests(unittest.TestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def _system_data_namespace(self):
        tree = ast.parse(self.source("core/system_data.py"), filename="core/system_data.py")
        names = {"_subject_plan_for_grade", "_guardian_index"}
        body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        namespace = {}
        exec(compile(ast.Module(body=body, type_ignores=[]), "core/system_data.py", "exec"), namespace)
        return namespace

    def test_r29_subject_plan_is_thirty_periods_with_daily_core(self):
        plan = self._system_data_namespace()["_subject_plan_for_grade"]
        for grade_order in range(1, 13):
            rows = dict(plan(grade_order))
            self.assertEqual(sum(rows.values()), 30)
            self.assertEqual(rows["اللغة العربية"], 5)
            self.assertEqual(rows["الرياضيات"], 5)
            self.assertEqual(rows["العلوم"], 5)
            self.assertEqual(rows["التربية المهنية"], 2)
            self.assertEqual(rows["التربية الرياضية"], 2)

    def test_r29_capacity_equation_and_family_distribution_are_exact(self):
        source = self.source("core/system_data.py")
        self.assertIn("DEMO_STUDENT_COUNT = 500", source)
        self.assertIn("DEMO_GUARDIAN_COUNT = 200", source)
        self.assertIn("DEMO_TEACHER_COUNT = 30", source)
        self.assertIn("DEMO_TEACHER_WEEKLY_LOAD = 30", source)
        self.assertIn("DEMO_TEACHER_DAILY_TARGET = 6", source)
        self.assertIn('section_names = ("أ", "ب", "ج") if grade.order <= 6 else ("أ", "ب")', source)
        self.assertIn("duration_minutes=20", source)
        self.assertIn("enforce_daily_teaching_target=True", source)
        self.assertIn('teacher.free_period_policy = "daily"', source)
        self.assertIn("teacher.daily_free_periods = 1", source)

        guardian_index = self._system_data_namespace()["_guardian_index"]
        family_sizes = Counter(guardian_index(student_index)[0] for student_index in range(1, 501))
        self.assertEqual(len(family_sizes), 200)
        self.assertEqual(Counter(family_sizes.values()), Counter({1: 50, 2: 50, 3: 50, 4: 50}))
        self.assertEqual(sum(family_sizes.values()), 500)

    def test_r29_weekly_capacity_equation_is_balanced(self):
        plan = self._system_data_namespace()["_subject_plan_for_grade"]
        section_count = 6 * 3 + 6 * 2
        weekly_section_periods = sum(periods for _name, periods in plan(1))
        self.assertEqual(section_count, 30)
        self.assertEqual(weekly_section_periods, 30)
        self.assertEqual(section_count * weekly_section_periods, 30 * 30)
        self.assertEqual(30 * 30, 30 * 6 * 5)

    def test_server_authoritative_jordan_clock(self):
        preferences = self.source("config/site_preferences.py")
        context = self.source("core/context_processors.py")
        base = self.source("templates/base/base.html")
        js = self.source("static/js/opal_erp.js")
        self.assertIn('OPAL_TIME_ZONE', preferences)
        self.assertIn('Asia/Amman', preferences)
        self.assertIn('"opal_server_now": timezone.now()', context)
        self.assertIn('data-opal-time-zone', base)
        self.assertIn('data-opal-server-now', base)
        self.assertIn('opalServerStart', js)
        self.assertIn('timeZone: opalClockZone', js)

    def test_runtime_gate_is_registered(self):
        checks = self.source("core/checks.py")
        contracts = self.source("core/capacity_timezone_contracts.py")
        self.assertIn("run_capacity_timezone_audit", checks)
        self.assertIn('id="opal.E133"', checks)
        self.assertIn("def run_capacity_timezone_audit", contracts)

    def test_no_parallel_model_page_or_route(self):
        models = self.source("teachers/models.py") + self.source("core/models.py") + self.source("timetable/models.py")
        self.assertNotIn("class DemoCapacity", models)
        self.assertNotIn("class SchoolTimeZone", models)
        self.assertFalse((ROOT / "templates" / "core" / "capacity_seed.html").exists())
        urls = self.source("core/urls.py")
        self.assertNotIn("capacity-seed", urls)


if __name__ == "__main__":
    unittest.main()
