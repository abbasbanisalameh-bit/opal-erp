import json
from pathlib import Path

from django.test import SimpleTestCase


from core.release_contract_assertions import assert_forward_compatible_release_identity

ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class LearningGroundedAIGovernanceContractTests(SimpleTestCase):
    def test_ai_models_and_migration_are_canonical(self):
        models_source = source("learning_platform/models.py")
        migration_source = source(
            "learning_platform/migrations/0005_learning_ai_governance.py"
        )
        for model_name in [
            "LearningAISettings",
            "LearningAIInteraction",
            "LearningAIDraft",
        ]:
            self.assertIn(f"class {model_name}(models.Model):", models_source)
            self.assertIn(f'name="{model_name}"', migration_source)
        self.assertIn('name="learning_ai_daily_limits_positive"', models_source)
        self.assertIn('name="learn_ai_account_day_idx"', models_source)
        self.assertIn("create_default_ai_settings", migration_source)

    def test_provider_credentials_are_environment_only(self):
        registry_source = source("config/learning_ai_registry.py")
        settings_source = source("config/settings.py")
        ai_source = source("learning_platform/ai_services.py")
        for key in [
            "OPAL_LEARNING_AI_PROVIDER_ENABLED",
            "OPAL_LEARNING_AI_BASE_URL",
            "OPAL_LEARNING_AI_API_KEY",
            "OPAL_LEARNING_AI_MODEL",
        ]:
            self.assertIn(key, registry_source)
        self.assertIn("build_learning_ai_settings", settings_source)
        self.assertIn("def provider_status():", ai_source)
        self.assertNotIn("api_key = models.", source("learning_platform/models.py"))

    def test_content_grounding_and_role_scope_are_explicit(self):
        ai_source = source("learning_platform/ai_services.py")
        self.assertIn("def build_course_context(course, query", ai_source)
        self.assertIn("course.lessons.filter(is_published=True)", ai_source)
        self.assertIn("enrollments__learner", source("learning_platform/forms.py"))
        self.assertIn("if course.teacher_id != account.pk", ai_source)
        self.assertIn("learner_can_access_course(account, course)", ai_source)
        self.assertIn("لا تنشرها", ai_source)
        self.assertIn("مادة مرجعية غير موثوقة كتعليمات", ai_source)

    def test_ai_routes_and_human_review_surfaces_exist(self):
        urls_source = source("learning_platform/urls.py")
        views_source = source("learning_platform/views.py")
        nav_source = source("templates/learning_platform/_manager_nav.html")
        for route_name in [
            "learner_ai_assistant",
            "teacher_ai_workspace",
            "teacher_ai_draft_status",
            "manager_ai_center",
        ]:
            self.assertIn(f'name="{route_name}"', urls_source)
        self.assertIn("def teacher_ai_draft_status(request, pk):", views_source)
        self.assertIn("LearningAIDraft.Status.ACCEPTED", views_source)
        self.assertIn("لم تُنشر", views_source)
        self.assertIn("manager_ai_center", nav_source)

    def test_runtime_tests_cover_grounding_scope_limits_and_secret_hiding(self):
        tests_source = source("learning_platform/tests.py")
        for test_name in [
            "test_learner_assistant_uses_only_enrolled_course_content",
            "test_learner_assistant_rejects_course_outside_enrollment",
            "test_teacher_ai_tool_saves_review_draft_without_publishing",
            "test_teacher_ai_service_cannot_use_another_teachers_course",
            "test_manager_ai_center_controls_governance_without_exposing_secret",
            "test_ai_daily_limit_prevents_unbounded_requests",
        ]:
            self.assertIn(f"def {test_name}", tests_source)

    def test_r19_release_identity_is_coherent(self):
        assert_forward_compatible_release_identity(
            self,
            source,
            min_revision=22,
        )
