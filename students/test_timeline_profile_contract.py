from pathlib import Path

from django.test import SimpleTestCase


class StudentTimelineContractTests(SimpleTestCase):
    def test_timeline_builder_is_canonical(self):
        source = Path(__file__).with_name("student360.py").read_text(encoding="utf-8")
        self.assertIn("def _build_student_timeline(", source)
        self.assertIn("activity_timeline = _build_student_timeline(", source)

    def test_legacy_builder_name_is_removed(self):
        source = Path(__file__).with_name("student360.py").read_text(encoding="utf-8")
        self.assertNotIn("def _build_activity_timeline(", source)
