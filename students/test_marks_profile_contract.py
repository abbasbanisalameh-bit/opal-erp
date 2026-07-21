from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from .student360 import _build_marks_profile


class StudentMarksProfileContractTests(SimpleTestCase):
    @patch("students.student360.StudentMark.objects")
    def test_marks_profile_preserves_order_summary_and_percentage_average(self, objects):
        first = MagicMock(percentage=75.0)
        second = MagicMock(percentage=85.0)
        queryset = objects.filter.return_value.select_related.return_value
        queryset.aggregate.return_value = {
            "count": 2,
            "average": 16,
            "total_marks": 32,
        }
        queryset.order_by.return_value.__getitem__.return_value = [first, second]

        student = object()
        profile = _build_marks_profile(student)

        objects.filter.assert_called_once_with(student=student)
        objects.filter.return_value.select_related.assert_called_once_with("exam", "exam__subject")
        queryset.order_by.assert_called_once_with("-exam__exam_date", "exam__subject__name")
        self.assertEqual(profile["marks"], [first, second])
        self.assertEqual(profile["summary"], {"count": 2, "average": 16, "total_marks": 32})
        self.assertEqual(profile["percentage_average"], 80.0)

    @patch("students.student360.StudentMark.objects")
    def test_empty_marks_profile_is_stable(self, objects):
        queryset = objects.filter.return_value.select_related.return_value
        queryset.aggregate.return_value = {"count": 0, "average": None, "total_marks": None}
        queryset.order_by.return_value.__getitem__.return_value = []

        profile = _build_marks_profile(object())

        self.assertEqual(profile["marks"], [])
        self.assertEqual(profile["summary"], {"count": 0, "average": None, "total_marks": None})
        self.assertEqual(profile["percentage_average"], 0)
