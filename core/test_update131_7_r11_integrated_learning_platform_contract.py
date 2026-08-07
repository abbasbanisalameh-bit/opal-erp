import json
from pathlib import Path

from django.test import SimpleTestCase


from core.release_contract_assertions import assert_forward_compatible_release_identity

ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class IntegratedLearningPlatformContractTests(SimpleTestCase):
    def test_learning_platform_is_installed_inside_opal_under_its_own_prefix(self):
        apps = source("config/app_registry.py")
        urls = source("config/url_groups.py")
        self.assertIn('"learning_platform.apps.LearningPlatformConfig"', apps)
        self.assertIn('path("learning/", include("learning_platform.urls"))', urls)

    def test_learning_identity_does_not_create_a_parallel_school_student(self):
        models = source("learning_platform/models.py")
        self.assertIn("class LearningAccount(models.Model):", models)
        self.assertNotIn("class Student(", models)
        self.assertNotIn("students.Student", models)
        self.assertNotIn("academics.StudentRecord", models)
        self.assertIn("make_password", models)
        self.assertIn("check_password", models)

    def test_learning_session_is_independent_from_django_erp_auth_session(self):
        auth = source("learning_platform/session_auth.py")
        self.assertIn('LEARNING_SESSION_KEY = "opal_learning_account_id"', auth)
        self.assertNotIn("django.contrib.auth import login", auth)
        self.assertIn("request.session.cycle_key()", auth)
        self.assertIn("request.session.pop(LEARNING_SESSION_KEY", auth)

    def test_learning_templates_never_extend_or_include_erp_chrome(self):
        learning_templates = list((ROOT / "templates" / "learning_platform").glob("*.html"))
        self.assertGreaterEqual(len(learning_templates), 9)
        combined = "\n".join(path.read_text(encoding="utf-8") for path in learning_templates)
        self.assertNotIn('base/base.html', combined)
        self.assertNotIn('includes/sidebar.html', combined)
        self.assertNotIn('includes/topbar.html', combined)
        self.assertNotIn('css/opal_erp.css', combined)
        self.assertIn("learning_platform/css/platform.css", combined)

    def test_registration_courses_and_subscription_cards_are_real_routes(self):
        urls = source("learning_platform/urls.py")
        models = source("learning_platform/models.py")
        for route_name in ("register", "login", "dashboard", "course_list", "subscriptions"):
            self.assertIn(f'name="{route_name}"', urls)
        self.assertIn("class LearningCourse(models.Model):", models)
        self.assertIn("class LearningLesson(models.Model):", models)
        self.assertIn("class LearningEnrollment(models.Model):", models)
        self.assertIn("class LearningSubscriptionCard(models.Model):", models)
        self.assertIn('MONTHLY = "monthly"', models)
        self.assertIn('TERMLY = "termly"', models)
        self.assertIn('YEARLY = "yearly"', models)

    def test_financial_scope_remains_subscription_only(self):
        combined = "\n".join(
            source(path)
            for path in (
                "learning_platform/models.py",
                "learning_platform/views.py",
                "templates/learning_platform/subscriptions.html",
            )
        ).lower()
        self.assertNotIn("general ledger", combined)
        self.assertNotIn("journal entry", combined)
        self.assertNotIn("دفتر الأستاذ", combined)
        self.assertNotIn("دفتر اليومية", combined)

    def test_r11_release_identity_is_coherent(self):
        assert_forward_compatible_release_identity(
            self,
            source,
            min_revision=14,
        )
