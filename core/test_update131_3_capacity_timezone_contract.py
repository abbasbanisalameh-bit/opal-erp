from pathlib import Path
import ast
from collections import Counter, defaultdict
import random
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Update1313CapacityTimezoneContractTests(unittest.TestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_subject_plan_totals_and_substitutions(self):
        tree = ast.parse(self.source("core/system_data.py"), filename="core/system_data.py")
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_subject_plan_for_grade")
        module = ast.Module(body=[function], type_ignores=[])
        namespace = {}
        exec(compile(module, "core/system_data.py", "exec"), namespace)
        plan = namespace["_subject_plan_for_grade"]

        for grade_order in range(1, 13):
            rows = dict(plan(grade_order))
            self.assertEqual(sum(rows.values()), 19)
            self.assertEqual(rows["التربية الرياضية"], 3)
            self.assertEqual(rows["التربية المهنية"], 2)
            self.assertEqual(rows["التربية الفنية"], 1)
            if grade_order <= 3:
                self.assertEqual(rows["الاجتماعيات"], 3)
                self.assertNotIn("التاريخ", rows)
                self.assertNotIn("الجغرافيا", rows)
                self.assertNotIn("التربية الوطنية", rows)
            else:
                self.assertNotIn("الاجتماعيات", rows)
                self.assertEqual(rows["التاريخ"], 1)
                self.assertEqual(rows["الجغرافيا"], 1)
                self.assertEqual(rows["التربية الوطنية"], 1)
            if grade_order <= 9:
                self.assertEqual(rows["العلوم"], 4)
                self.assertNotIn("الفيزياء", rows)
            else:
                self.assertNotIn("العلوم", rows)
                for subject in ("الفيزياء", "الكيمياء", "الأحياء", "علوم الأرض"):
                    self.assertEqual(rows[subject], 1)

    def test_capacity_equation_is_exact(self):
        source = self.source("core/system_data.py")
        self.assertIn("DEMO_STUDENT_COUNT = 500", source)
        self.assertIn("DEMO_TEACHER_COUNT = 19", source)
        self.assertIn("DEMO_TEACHER_WEEKLY_LOAD = 25", source)
        self.assertIn("DEMO_TEACHER_DAILY_TARGET = 5", source)
        self.assertIn('section_names = ("أ", "ب", "ج") if grade.order == 1 else ("أ", "ب")', source)
        self.assertIn("enforce_daily_teaching_target=True", source)
        self.assertIn('teacher.free_period_policy = "daily"', source)
        self.assertIn("teacher.daily_free_periods = 1", source)
        self.assertIn("No row means present under the official exception-only policy", source)

    def test_deterministic_capacity_schedule_is_feasible(self):
        tree = ast.parse(self.source("core/system_data.py"), filename="core/system_data.py")
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_subject_plan_for_grade")
        namespace = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "core/system_data.py", "exec"), namespace)
        subject_plan = namespace["_subject_plan_for_grade"]

        sections = []
        section_id = 1
        for grade in range(1, 13):
            names = ("أ", "ب", "ج") if grade == 1 else ("أ", "ب")
            for name in names:
                sections.append({"id": section_id, "grade": grade, "name": f"شعبة {name}"})
                section_id += 1

        subject_id = 1
        subjects = {}
        for grade in range(1, 13):
            subjects[grade] = []
            for name, periods in subject_plan(grade):
                subjects[grade].append({"id": subject_id, "name": name, "periods": periods})
                subject_id += 1

        teachers = list(range(1, 20))
        loads = {teacher: 0 for teacher in teachers}
        tasks = [(section, subject, subject["periods"]) for section in sections for subject in subjects[section["grade"]]]
        rng = random.Random(1139)
        by_weight = defaultdict(list)
        for task in tasks:
            by_weight[task[2]].append(task)
        ordered = []
        for weight in sorted(by_weight, reverse=True):
            group = list(by_weight[weight])
            rng.shuffle(group)
            ordered.extend(group)
        assignments = []
        for section, subject, periods in ordered:
            eligible = [teacher for teacher in teachers if loads[teacher] + periods <= 25]
            minimum = min(loads[teacher] for teacher in eligible)
            teacher = rng.choice([item for item in eligible if loads[item] == minimum])
            loads[teacher] += periods
            assignments.append({"teacher": teacher, "section": section, "subject": subject, "required": periods})
        self.assertEqual(set(loads.values()), {25})

        days = ("sunday", "monday", "tuesday", "wednesday", "thursday")
        slots = []
        cursor = 8 * 60
        for index in range(1, 9):
            slots.append((index, cursor, cursor + 40))
            cursor += 45
        placements = {
            "lower": {"after": 3, "shift": 10},
            "upper": {"after": 2, "shift": 10},
            "secondary": {"after": 4, "shift": 10},
        }

        def actual(slot_index, section):
            _, start, end = slots[slot_index]
            group = "lower" if section["grade"] <= 4 else "upper" if section["grade"] <= 8 else "secondary"
            placement = placements[group]
            shift = placement["shift"] if slot_index > placement["after"] else 0
            return start + shift, end + shift

        def overlaps(start, end, old_start, old_end):
            return start < old_end and old_start < end

        section_busy = defaultdict(list)
        teacher_busy = defaultdict(list)
        teacher_daily = Counter()
        daily_subject = Counter()
        created = 0
        for assignment in sorted(assignments, key=lambda item: (item["section"]["grade"], item["section"]["name"], item["subject"]["name"])):
            for _ in range(assignment["required"]):
                candidates = []
                for day_index, day in enumerate(days):
                    if teacher_daily[(assignment["teacher"], day)] >= 5:
                        continue
                    for slot_index, slot in enumerate(slots):
                        start, end = actual(slot_index, assignment["section"])
                        if any(overlaps(start, end, old_start, old_end) for old_start, old_end in section_busy[(assignment["section"]["id"], day)]):
                            continue
                        if any(overlaps(start, end, old_start, old_end) for old_start, old_end in teacher_busy[(assignment["teacher"], day)]):
                            continue
                        adjacent = sum(
                            1 for old_start, old_end in teacher_busy[(assignment["teacher"], day)]
                            if old_end == start or old_start == end
                        )
                        daily_teacher = teacher_daily[(assignment["teacher"], day)]
                        daily_same_subject = daily_subject[(assignment["section"]["id"], assignment["subject"]["id"], day)]
                        score = (
                            daily_same_subject * 40, daily_teacher * 8, adjacent * 5,
                            abs((daily_teacher + 1) - 5), day_index, slot[0], start,
                        )
                        candidates.append((score, day, start, end))
                self.assertTrue(candidates, f"No schedule candidate for {assignment}")
                _, day, start, end = min(candidates, key=lambda item: item[0])
                section_busy[(assignment["section"]["id"], day)].append((start, end))
                teacher_busy[(assignment["teacher"], day)].append((start, end))
                teacher_daily[(assignment["teacher"], day)] += 1
                daily_subject[(assignment["section"]["id"], assignment["subject"]["id"], day)] += 1
                created += 1

        self.assertEqual(created, 475)
        self.assertTrue(all(teacher_daily[(teacher, day)] == 5 for teacher in teachers for day in days))

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
