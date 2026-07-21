from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from students.student360 import _build_family_profile


class StudentFamilyProfileContractTests(SimpleTestCase):
    @patch("students.student360.find_sibling_students")
    @patch("students.student360.FamilyStudent.objects")
    def test_builds_family_guardian_and_sibling_context(self, family_objects, find_siblings):
        student = SimpleNamespace(pk=7)
        family = SimpleNamespace(guardian_name="Guardian")
        family_link = SimpleNamespace(family=family)
        guardian_link = SimpleNamespace(family=family)

        first_query = MagicMock()
        first_query.select_related.return_value.first.return_value = family_link
        second_query = MagicMock()
        second_query.select_related.return_value.order_by.return_value.__iter__.return_value = iter([guardian_link])
        family_objects.filter.side_effect = [first_query, second_query]

        sibling_queryset = MagicMock()
        sibling_queryset.exclude.return_value.__iter__.return_value = iter([SimpleNamespace(pk=8)])
        find_siblings.return_value = sibling_queryset

        profile = _build_family_profile(student)

        self.assertIs(profile["family_link"], family_link)
        self.assertIs(profile["family"], family)
        self.assertEqual([row.pk for row in profile["siblings"]], [8])
        self.assertEqual(profile["guardian_links"], [guardian_link])
        find_siblings.assert_called_once_with(student)
        sibling_queryset.exclude.assert_called_once_with(pk=7)

    @patch("students.student360.find_sibling_students")
    @patch("students.student360.FamilyStudent.objects")
    def test_returns_stable_empty_family_values(self, family_objects, find_siblings):
        student = SimpleNamespace(pk=3)
        first_query = MagicMock()
        first_query.select_related.return_value.first.return_value = None
        second_query = MagicMock()
        second_query.select_related.return_value.order_by.return_value.__iter__.return_value = iter([])
        family_objects.filter.side_effect = [first_query, second_query]
        sibling_queryset = MagicMock()
        sibling_queryset.exclude.return_value.__iter__.return_value = iter([])
        find_siblings.return_value = sibling_queryset

        profile = _build_family_profile(student)

        self.assertIsNone(profile["family_link"])
        self.assertIsNone(profile["family"])
        self.assertEqual(profile["siblings"], [])
        self.assertEqual(profile["guardian_links"], [])
