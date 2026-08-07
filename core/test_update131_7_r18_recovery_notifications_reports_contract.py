import json
from pathlib import Path

from django.test import SimpleTestCase


from core.release_contract_assertions import assert_forward_compatible_release_identity

ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class LearningRecoveryNotificationsReportsContractTests(SimpleTestCase):
    def test_recovery_and_notification_models_are_canonical(self):
        models_source = source("learning_platform/models.py")
        migration_source = source(
            "learning_platform/migrations/0004_account_recovery_notifications.py"
        )
        for model_name in ["LearningPasswordResetRequest", "LearningNotification"]:
            self.assertIn(f"class {model_name}(models.Model):", models_source)
            self.assertIn(f'name="{model_name}"', migration_source)
        self.assertIn('auth_version = models.PositiveIntegerField', models_source)
        self.assertIn('name="uniq_learning_notification_dedupe"', models_source)

    def test_recovery_services_hash_tokens_and_revoke_old_sessions(self):
        services_source = source("learning_platform/services.py")
        session_source = source("learning_platform/session_auth.py")
        self.assertIn("def create_password_reset_request(account", services_source)
        self.assertIn("def deliver_password_reset_email(reset_request", services_source)
        self.assertIn("def complete_password_reset(reset_request", services_source)
        self.assertIn("def reset_password_by_manager(account", services_source)
        self.assertIn("salted_hmac", services_source)
        self.assertIn("account.auth_version = account.auth_version + 1", services_source)
        self.assertIn("LEARNING_AUTH_VERSION_KEY", session_source)
        self.assertIn("session_auth_version != account.auth_version", session_source)

    def test_notification_and_report_routes_exist_and_are_scoped(self):
        urls_source = source("learning_platform/urls.py")
        views_source = source("learning_platform/views.py")
        for route_name in [
            "password_reset_request",
            "password_reset_confirm",
            "manager_password_reset_requests",
            "manager_account_password_reset",
            "notification_list",
            "notification_open",
            "notification_read_all",
            "manager_report_center",
            "manager_report_export_csv",
        ]:
            self.assertIn(f'name="{route_name}"', urls_source)
        self.assertIn("recipient=request.learning_account", views_source)
        self.assertIn("@platform_manager_required\ndef manager_report_export_csv", views_source)
        self.assertIn("def _csv_safe(value):", views_source)

    def test_runtime_tests_cover_recovery_notifications_and_reports(self):
        tests_source = source("learning_platform/tests.py")
        for test_name in [
            "test_password_reset_email_changes_password_and_invalidates_old_sessions",
            "test_password_reset_request_does_not_disclose_unknown_email",
            "test_manager_can_issue_one_time_temporary_password",
            "test_assignment_submission_and_grading_create_role_notifications",
            "test_notification_inbox_is_scoped_and_marked_read_by_post",
            "test_expiring_subscription_notification_is_idempotent",
            "test_manager_operational_report_and_csv_export",
        ]:
            self.assertIn(f"def {test_name}", tests_source)

    def test_r18_release_identity_is_coherent(self):
        assert_forward_compatible_release_identity(
            self,
            source,
            min_revision=21,
        )
