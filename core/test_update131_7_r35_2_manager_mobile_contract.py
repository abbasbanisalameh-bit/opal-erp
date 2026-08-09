from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class R352ManagerMobileContractTests(SimpleTestCase):
    def setUp(self):
        self.root = Path(settings.BASE_DIR)
        self.mobile_source = (self.root / "mobile" / "opal_learning_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        self.api_source = (self.root / "learning_platform" / "api.py").read_text(encoding="utf-8")
        self.security_source = (self.root / "learning_platform" / "security_services.py").read_text(encoding="utf-8")

    def test_mobile_has_manager_role_and_native_manager_surfaces(self):
        self.assertIn("role == 'manager'", self.mobile_source)
        self.assertIn("ManagerDashboardPage", self.mobile_source)
        self.assertIn("ManagerAccountsPage", self.mobile_source)
        self.assertIn("ManagerCoursesPage", self.mobile_source)
        self.assertIn("ManagerCardsPage", self.mobile_source)
        self.assertIn("ManagerAccessPage", self.mobile_source)

    def test_manager_login_uses_erp_school_login_not_second_password(self):
        self.assertIn("is_management_user(user)", self.api_source)
        self.assertIn("issue_manager_api_token", self.api_source)
        self.assertIn('"mode": "manager"', self.api_source)
        self.assertIn('"role": "manager"', self.api_source)

    def test_manager_token_is_separate_short_lived_and_hashed(self):
        self.assertIn('raw_token = "olm_"', self.security_source)
        self.assertIn('_opaque_hash("manager-api-token", raw_token)', self.security_source)
        self.assertIn("OPAL_LEARNING_MANAGER_API_TOKEN_HOURS", self.security_source)
        self.assertIn("is_management_user(token.user)", self.security_source)

    def test_manager_mobile_uses_existing_secure_card_generator(self):
        self.assertIn("LearningSubscriptionBatchForm", self.api_source)
        self.assertIn("manager/subscription-cards/generate/", self.mobile_source)
        self.assertNotIn("OPAL-000001", self.mobile_source)
