import json
from pathlib import Path

from django.test import SimpleTestCase


from core.release_contract_assertions import assert_forward_compatible_release_identity

ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class LearningProductionReleaseContractTests(SimpleTestCase):
    def test_production_models_and_migration_are_canonical(self):
        models_source = source("learning_platform/models.py")
        migration = source("learning_platform/migrations/0006_learning_production_release.py")
        for name in [
            "LearningEmailVerificationRequest",
            "LearningSubscriptionPlan",
            "LearningPaymentOrder",
            "LearningPaymentEvent",
            "LearningAPIToken",
            "LearningRateLimitBucket",
        ]:
            self.assertIn(f"class {name}(models.Model):", models_source)
            self.assertIn(f'name="{name}"', migration)
        for field in [
            "terms_accepted_at",
            "privacy_accepted_at",
            "email_verified_at",
            "failed_login_count",
            "locked_until",
        ]:
            self.assertIn(field, models_source)
            self.assertIn(f'name="{field}"', migration)

    def test_payment_secrets_are_environment_only_and_webhooks_are_signed(self):
        registry = source("config/learning_payment_registry.py")
        payment = source("learning_platform/payment_services.py")
        settings_source = source("config/settings.py")
        for key in [
            "OPAL_LEARNING_PAYMENT_ENABLED",
            "OPAL_LEARNING_PAYMENT_CHECKOUT_URL",
            "OPAL_LEARNING_PAYMENT_API_KEY",
            "OPAL_LEARNING_PAYMENT_WEBHOOK_SECRET",
        ]:
            self.assertIn(key, registry)
        self.assertIn("build_learning_payment_settings", settings_source)
        self.assertIn("def verify_webhook_signature", payment)
        self.assertIn("hmac.compare_digest", payment)
        self.assertIn("idempotency_key", payment)
        self.assertIn("event_amount != order.amount", payment)
        self.assertIn("event_currency != order.currency.upper()", payment)
        self.assertNotIn("api_key = models.", source("learning_platform/models.py"))

    def test_mobile_api_uses_expiring_hashed_tokens_and_role_scope(self):
        api = source("learning_platform/api.py")
        security = source("learning_platform/security_services.py")
        urls = source("learning_platform/urls.py")
        for route in [
            "api_login",
            "api_logout",
            "api_me",
            "api_course_list",
            "api_course_enroll",
            "api_lesson_complete",
            "api_assessment_detail",
            "api_assessment_submit",
            "api_notifications",
            "api_certificates",
            "api_subscription_plans",
            "api_ai_question",
        ]:
            self.assertIn(f'name="{route}"', urls)
        self.assertIn("def api_auth_required", api)
        self.assertIn('request.META.get("HTTP_AUTHORIZATION")', api)
        self.assertIn('startswith("bearer ")', api)
        self.assertIn("token_hash=_opaque_hash", security)
        self.assertIn("expires_at", security)
        self.assertIn("revoke_api_token", api)
        self.assertIn("learner_can_access_course", api)

    def test_security_readiness_backup_and_pwa_surfaces_exist(self):
        for path in [
            "learning_platform/production.py",
            "learning_platform/management/commands/verify_learning_production_readiness.py",
            "learning_platform/management/commands/backup_learning_platform.py",
            "templates/learning_platform/manager_readiness.html",
            "templates/learning_platform/manifest.webmanifest",
            "templates/learning_platform/service-worker.js",
            "docs/LEARNING_MOBILE_API_V1_AR.md",
            "docs/LEARNING_PRODUCTION_RUNBOOK_R20_AR.md",
            "mobile/opal_learning_app/pubspec.yaml",
            "mobile/opal_learning_app/lib/main.dart",
            "templates/learning_platform/legal_acceptance.html",
        ]:
            self.assertTrue((ROOT / path).exists(), path)
        production = source("learning_platform/production.py")
        self.assertIn("collect_learning_readiness_checks", production)
        self.assertIn("MigrationExecutor", production)
        self.assertIn("blocking_failures", production)
        base = source("templates/learning_platform/base.html")
        self.assertIn("mobile_manifest", base)
        self.assertIn("serviceWorker.register", base)
        service_worker = source("templates/learning_platform/service-worker.js")
        self.assertIn("/static/learning_platform/", service_worker)
        self.assertNotIn("cache.put(event.request, copy)); } return response", service_worker)

    def test_runtime_tests_cover_api_payment_webhook_and_readiness(self):
        tests = source("learning_platform/tests.py")
        for test_name in [
            "test_registration_records_legal_acceptance_and_verification_request",
            "test_api_login_me_and_logout_use_hashed_device_token",
            "test_manual_payment_approval_activates_one_subscription_idempotently",
            "test_signed_payment_webhook_is_idempotent",
            "test_pwa_manifest_and_health_endpoint_are_public",
            "test_manager_readiness_and_payment_surfaces_require_erp_manager",
            "test_legacy_account_must_accept_legal_terms_itself",
            "test_paid_webhook_rejects_amount_or_currency_mismatch",
            "test_mobile_assessment_detail_never_exposes_correct_answer",
        ]:
            self.assertIn(f"def {test_name}", tests)

    def test_r20_release_identity_is_coherent(self):
        assert_forward_compatible_release_identity(
            self,
            source,
            min_revision=23,
        )
