from django.contrib.auth.models import User
from django.test import TestCase

from core.models import AuditLog, Branch, DataIntegrityRun, School


class AuditLogSchemaCompatibilityTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة اختبار")
        self.branch = Branch.objects.create(
            school=self.school,
            name="الفرع الرئيسي",
            is_main=True,
        )
        self.user = User.objects.create_user(username="audit-test", password="x")

    def test_audit_log_creation_supplies_compatibility_defaults(self):
        record = AuditLog.objects.create(
            user=self.user,
            school=self.school,
            branch=self.branch,
            action="view",
            model_name="enterprise_ops",
            description="اختبار التوافق",
        )

        self.assertEqual(record.request_id, "")
        self.assertEqual(record.result, "success")

    def test_integrity_run_can_be_scoped_to_school(self):
        run = DataIntegrityRun.objects.create(
            school=self.school,
            created_by=self.user,
        )
        self.assertEqual(run.school_id, self.school.id)
