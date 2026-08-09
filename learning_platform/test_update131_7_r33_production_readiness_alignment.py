from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.models import AcademicYear, School
from core.operation_audit import build_operation_audit

from learning_platform.card_codes import CARD_CODE_ALPHABET, new_card_code
from learning_platform.production import collect_learning_readiness_checks


class R33SecureSubscriptionCardTests(TestCase):
    def test_generated_card_codes_are_high_entropy_unique_and_human_readable(self):
        codes = {new_card_code(prefix="OPAL") for _ in range(1000)}
        self.assertEqual(len(codes), 1000)
        for code in codes:
            parts = code.split("-")
            self.assertEqual(parts[0], "OPAL")
            self.assertEqual(len(parts[1:]), 5)
            self.assertTrue(all(len(part) == 4 for part in parts[1:]))
            token = "".join(parts[1:])
            self.assertEqual(len(token), 20)
            self.assertTrue(all(character in CARD_CODE_ALPHABET for character in token))
            self.assertNotIn("0", token)
            self.assertNotIn("1", token)
            self.assertNotIn("I", token)
            self.assertNotIn("O", token)

    def test_card_candidate_does_not_embed_predictable_identifiers(self):
        student_number = "2026000001"
        order_number = "00000015"
        for _ in range(100):
            code = new_card_code(prefix="OPAL")
            self.assertNotIn(student_number, code)
            self.assertNotIn(order_number, code)


class R33OperationAuditSemesterTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة اختبار R33", is_active=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            midyear_break_start=date(2027, 1, 16),
            midyear_break_end=date(2027, 1, 31),
            is_current=True,
        )

    def _semester_issue(self, reference_date):
        with patch("core.operation_audit.timezone.localdate", return_value=reference_date):
            report = build_operation_audit()
        return next(item for item in report["integration_issues"] if item["code"] == "CURRENT_SEMESTER")

    def test_pre_year_period_does_not_require_current_semester(self):
        issue = self._semester_issue(date(2026, 8, 9))
        self.assertEqual(issue["count"], 0)

    def test_midyear_break_does_not_require_current_semester(self):
        issue = self._semester_issue(date(2027, 1, 20))
        self.assertEqual(issue["count"], 0)

    def test_date_inside_open_term_requires_current_semester(self):
        issue = self._semester_issue(date(2026, 9, 15))
        self.assertEqual(issue["count"], 1)
        first = self.year.semesters.get(code="first")
        first.is_current = True
        first.save(update_fields=["is_current"])
        issue = self._semester_issue(date(2026, 9, 15))
        self.assertEqual(issue["count"], 0)


@override_settings(
    OPAL_LEARNING_BACKUP_DIR="/tmp/opal_r33_backup_test",
    MEDIA_ROOT="/tmp/opal_r33_media_test",
)
class R33ReadinessSalesModeTests(TestCase):
    @override_settings(
        OPAL_LEARNING_PUBLIC_LAUNCH=True,
        OPAL_LEARNING_SUBSCRIPTION_SALES_MODE="cards",
        OPAL_LEARNING_EMAIL_ENABLED=False,
    )
    def test_card_sales_mode_does_not_require_external_gateway(self):
        result = collect_learning_readiness_checks(include_migrations=False)
        check = next(item for item in result["checks"] if item["code"] == "subscription_sales")
        self.assertEqual(check["status"], "pass")
        self.assertFalse(check["blocking"])
        self.assertIn("بطاقات الاشتراك", check["detail"])
        self.assertEqual(result["subscription_sales_mode"], "cards")

    @override_settings(
        OPAL_LEARNING_PUBLIC_LAUNCH=True,
        OPAL_LEARNING_SUBSCRIPTION_SALES_MODE="manual",
        OPAL_LEARNING_PAYMENT_ENABLED=True,
        OPAL_LEARNING_PAYMENT_PROVIDER="manual",
        OPAL_LEARNING_MANUAL_PAYMENT_ALLOWED=True,
    )
    def test_manual_mode_is_not_considered_public_checkout(self):
        result = collect_learning_readiness_checks(include_migrations=False)
        check = next(item for item in result["checks"] if item["code"] == "subscription_sales")
        self.assertEqual(check["status"], "fail")
        self.assertTrue(check["blocking"])

    @override_settings(OPAL_LEARNING_SUBSCRIPTION_SALES_MODE="cards")
    def test_sqlite_warning_is_classified_as_hosting_constraint(self):
        result = collect_learning_readiness_checks(include_migrations=False)
        check = next(item for item in result["checks"] if item["code"] == "database")
        self.assertEqual(check["requirement"], "hosting")
