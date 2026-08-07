import json
from pathlib import Path

from django.test import SimpleTestCase


from core.release_contract_assertions import assert_forward_compatible_release_identity

ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class LearningPlatformArabicSlugRuntimeFixContractTests(SimpleTestCase):
    def test_public_course_route_accepts_unicode_slug_values(self):
        urls = source("learning_platform/urls.py")
        forms = source("learning_platform/forms.py")
        models = source("learning_platform/models.py")

        self.assertIn(
            'path("courses/<str:slug>/", views.course_detail, name="course_detail")',
            urls,
        )
        self.assertNotIn('courses/<slug:slug>/', urls)
        self.assertIn("allow_unicode=True", forms)
        self.assertIn('slug = models.SlugField("المعرف", max_length=240, unique=True, allow_unicode=True)', models)

    def test_runtime_regression_covers_arabic_slug_surfaces(self):
        tests = source("learning_platform/tests.py")
        self.assertIn(
            "def test_arabic_course_slug_renders_public_and_manager_surfaces",
            tests,
        )
        self.assertIn('reverse("learning_platform:course_detail", args=[course.slug])', tests)
        self.assertIn('reverse("learning_platform:manager_course_list")', tests)

    def test_r15_release_identity_is_coherent(self):
        assert_forward_compatible_release_identity(
            self,
            source,
            min_revision=18,
        )
