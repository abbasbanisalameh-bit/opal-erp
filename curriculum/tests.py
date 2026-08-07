from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class CurriculumLegacyRedirectTests(TestCase):
    """The retired CRUD surface remains a one-release redirect only."""

    def setUp(self):
        self.staff = User.objects.create_user("curriculum_staff", password="pass", is_staff=True)
        self.client.force_login(self.staff)

    def test_every_legacy_route_redirects_to_canonical_subject_plan(self):
        cases = (
            (reverse("curriculum:curriculum_list"), reverse("academics:subject_list")),
            (reverse("curriculum:curriculum_create"), reverse("academics:subject_create")),
            (reverse("curriculum:curriculum_update", args=[999]), reverse("academics:subject_list")),
            (reverse("curriculum:curriculum_delete", args=[999]), reverse("academics:subject_list")),
        )
        for legacy, successor in cases:
            response = self.client.get(legacy)
            self.assertRedirects(response, successor, fetch_redirect_response=False)
            self.assertEqual(response["Deprecation"], "true")
            self.assertEqual(response["Sunset"], "OPAL Update 132.0")

    def test_legacy_routes_are_not_operational_crud(self):
        response = self.client.post(reverse("curriculum:curriculum_delete", args=[999]))
        self.assertRedirects(response, reverse("academics:subject_list"), fetch_redirect_response=False)
