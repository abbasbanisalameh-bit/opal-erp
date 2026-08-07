import json
from pathlib import Path

from django.test import SimpleTestCase


from core.release_contract_assertions import assert_forward_compatible_release_identity

ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class LearningAssessmentsCertificatesContractTests(SimpleTestCase):
    def test_canonical_assessment_submission_and_certificate_models_exist(self):
        models_source = source("learning_platform/models.py")
        migration_source = source(
            "learning_platform/migrations/0003_learning_assessments_submissions_certificates.py"
        )
        for model_name in [
            "LearningAssessment",
            "LearningQuestion",
            "LearningSubmission",
            "LearningCertificate",
        ]:
            self.assertIn(f"class {model_name}(models.Model):", models_source)
            self.assertIn(f'name="{model_name}"', migration_source)
        self.assertIn('name="uniq_learning_submission_attempt"', models_source)
        self.assertIn('related_name="certificate"', models_source)

    def test_services_cover_auto_grading_manual_grading_and_certificates(self):
        services_source = source("learning_platform/services.py")
        self.assertIn("def submit_quiz(enrollment, assessment, answers", services_source)
        self.assertIn("def submit_assignment(enrollment, assessment, answer_text", services_source)
        self.assertIn("def grade_assignment(submission", services_source)
        self.assertIn("def issue_certificate(enrollment)", services_source)
        self.assertIn("def revoke_certificate(enrollment", services_source)
        self.assertIn("passed_assessments", services_source)

    def test_routes_are_separated_by_manager_teacher_and_learner_role(self):
        urls_source = source("learning_platform/urls.py")
        views_source = source("learning_platform/views.py")
        for route_name in [
            "manager_assessment_list",
            "manager_question_list",
            "manager_submission_list",
            "manager_submission_grade",
            "teacher_submission_list",
            "teacher_submission_grade",
            "assessment_detail",
            "certificate_detail",
            "certificate_verify",
        ]:
            self.assertIn(f'name="{route_name}"', urls_source)
        self.assertIn("assessment__course__teacher=account", views_source)
        self.assertIn("@require_http_methods([\"GET\", \"POST\"])\ndef assessment_detail", views_source)

    def test_runtime_tests_cover_quiz_assignment_certificate_and_scope(self):
        tests_source = source("learning_platform/tests.py")
        self.assertIn(
            "def test_quiz_is_auto_graded_and_issues_certificate_after_all_requirements",
            tests_source,
        )
        self.assertIn(
            "def test_assignment_waits_for_teacher_grading_then_completes_course",
            tests_source,
        )
        self.assertIn(
            "def test_teacher_cannot_grade_another_teachers_assignment",
            tests_source,
        )
        self.assertIn(
            "def test_manager_builds_quiz_then_publishes_it_after_questions_exist",
            tests_source,
        )

    def test_r17_release_identity_is_coherent(self):
        assert_forward_compatible_release_identity(
            self,
            source,
            min_revision=20,
        )
