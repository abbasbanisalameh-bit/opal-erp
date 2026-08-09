from collections import Counter
from pathlib import Path
import ast
import unittest


ROOT = Path(__file__).resolve().parents[1]


class R29RelationalDemoContractTests(unittest.TestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def _function(self, name):
        tree = ast.parse(self.source("core/system_data.py"), filename="core/system_data.py")
        node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name)
        namespace = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "core/system_data.py", "exec"), namespace)
        return namespace[name]

    def test_exact_people_and_family_contract(self):
        source = self.source("core/system_data.py")
        self.assertIn("DEMO_STUDENT_COUNT = 500", source)
        self.assertIn("DEMO_GUARDIAN_COUNT = 200", source)
        self.assertIn("DEMO_TEACHER_COUNT = 30", source)
        guardian_index = self._function("_guardian_index")
        family_sizes = Counter(guardian_index(index)[0] for index in range(1, 501))
        self.assertEqual(len(family_sizes), 200)
        self.assertEqual(Counter(family_sizes.values()), Counter({1: 50, 2: 50, 3: 50, 4: 50}))

    def test_exact_weekly_plan_contract(self):
        plan = dict(self._function("_subject_plan_for_grade")(1))
        self.assertEqual(sum(plan.values()), 30)
        self.assertEqual(plan["اللغة العربية"], 5)
        self.assertEqual(plan["الرياضيات"], 5)
        self.assertEqual(plan["العلوم"], 5)
        self.assertEqual(plan["التربية المهنية"], 2)
        self.assertEqual(plan["التربية الرياضية"], 2)

    def test_sections_homeroom_load_and_break_contract(self):
        source = self.source("core/system_data.py")
        self.assertIn('section_names = ("أ", "ب", "ج") if grade.order <= 6 else ("أ", "ب")', source)
        self.assertIn("DEMO_TEACHER_WEEKLY_LOAD = 30", source)
        self.assertIn("DEMO_TEACHER_DAILY_TARGET = 6", source)
        self.assertIn("teacher = teachers[section_index]", source)
        self.assertIn('section.homeroom_teacher = teacher', source)
        self.assertIn("duration_minutes=20", source)
        self.assertIn("cursor = end_dt + timedelta(minutes=10)", source)
        self.assertIn("enforce_daily_teaching_target=True", source)

    def test_demo_seed_builds_learning_identities_content_and_cards(self):
        source = self.source("core/system_data.py")
        for token in (
            "ensure_student_learning_account(student)",
            "ensure_teacher_learning_account(teacher)",
            "academic_subject=assignment.subject",
            "academic_section=assignment.section",
            "LearningLesson.objects.bulk_create",
            "LearningSubscriptionCard.objects.bulk_create",
            "Counter({1: 50, 2: 50, 3: 50, 4: 50})",
            'scope="all_siblings"',
        ):
            self.assertIn(token, source)

    def test_seed_button_is_reenabled_but_direct_reset_stays_blocked(self):
        views = self.source("core/views.py")
        template = self.source("templates/core/system_settings.html")
        self.assertIn('if action == "reset_all":', views)
        self.assertIn("التصفير المباشر متوقف", views)
        self.assertIn('if action == "seed_system":', views)
        self.assertIn("seed_system_data(user=request.user)", views)
        self.assertIn('value="seed_system"', template)
        self.assertIn("إدخال البيانات التجريبية", template)


if __name__ == "__main__":
    unittest.main()
