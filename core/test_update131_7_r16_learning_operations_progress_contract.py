import json
from pathlib import Path

from django.test import SimpleTestCase


from core.release_contract_assertions import assert_forward_compatible_release_identity

ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class LearningOperationsProgressContractTests(SimpleTestCase):
    def test_progress_model_and_service_are_canonical(self):
        models_source = source("learning_platform/models.py")
        services_source = source("learning_platform/services.py")
        migration_source = source(
            "learning_platform/migrations/0002_learninglessonprogress_and_operational_events.py"
        )

        self.assertIn("class LearningLessonProgress(models.Model):", models_source)
        self.assertIn('name="uniq_learning_lesson_progress"', models_source)
        self.assertIn("def current_entitlement(account, subject", services_source)
        self.assertIn("def enroll_learner(account, course", services_source)
        self.assertIn("def mark_lesson_completed(enrollment, lesson", services_source)
        self.assertIn('name="LearningLessonProgress"', migration_source)

    def test_learning_routes_cover_entitlement_enrollment_and_progress(self):
        urls = source("learning_platform/urls.py")
        views = source("learning_platform/views.py")

        self.assertIn('name="manager_subscription_list"', urls)
        self.assertIn('name="manager_enrollment_list"', urls)
        self.assertIn('name="course_enroll"', urls)
        self.assertIn('name="lesson_detail"', urls)
        self.assertIn('name="lesson_complete"', urls)
        self.assertIn("@require_POST\ndef course_enroll", views)
        self.assertIn("@require_POST\ndef lesson_complete", views)
        self.assertIn("learner_can_access_course", views)

    def test_runtime_tests_cover_subscription_and_course_completion(self):
        tests = source("learning_platform/tests.py")
        self.assertIn(
            "def test_manager_generates_and_cancels_subscription_cards",
            tests,
        )
        self.assertIn(
            "def test_learner_enrolls_and_completes_published_lessons",
            tests,
        )
        self.assertIn(
            "def test_enrollment_requires_active_subscription_for_course_subject",
            tests,
        )
        self.assertIn(
            "def test_teacher_progress_page_is_limited_to_own_course",
            tests,
        )

    def test_r16_release_identity_is_coherent(self):
        assert_forward_compatible_release_identity(
            self,
            source,
            min_revision=19,
        )
