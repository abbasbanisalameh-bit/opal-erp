from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role
from admissions.models import RegistrationSettings
from announcements.models import Announcement
from core.models import Branch, ProductionDataResetRun, School
from core.production_reset import (
    PRODUCTION_RESET_CONFIRMATION,
    collect_production_reset_preview,
    execute_production_data_reset,
)
from development_center.models import Module
from documents.models import DocumentSettings, DocumentTemplate
from enterprise_ops.models import RolePermissionRule
from learning_platform.models import LearningAISettings, LearningAccount, LearningSubject
from openemis_integration.models import OpenEMISSettings
from parent_portal.models import Family
from students.models import Student
from timetable.models import SchoolScheduleSettings


class ProductionDataResetServiceTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_superuser("production_owner", "owner@example.test", "x")
        self.other_user = User.objects.create_user("trial_user", "trial@example.test", "x")
        self.school = School.objects.create(name="مدرسة التشغيل", is_active=True)
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.role = Role.objects.create(code="principal", name="مدير المدرسة")
        self.permission_rule = RolePermissionRule.objects.create(
            role_code="principal", feature="students", can_view=True, is_active=True,
        )
        self.registration_settings = RegistrationSettings.objects.create(school=self.school)
        self.template = DocumentTemplate.objects.create(
            name="قالب محفوظ", document_type="custom", title="عنوان", body="محتوى",
        )
        self.document_settings = DocumentSettings.objects.create(school=self.school, manager_name="المدير")
        self.schedule_settings = SchoolScheduleSettings.objects.create(school=self.school)
        self.openemis_settings = OpenEMISSettings.objects.create(school=self.school, is_enabled=False)
        self.ai_settings = LearningAISettings.load()
        self.development_module = Module.objects.create(name="وحدة محفوظة", status="completed")

        self.student = Student.objects.create(
            student_number="TRIAL-1", full_name="طالب تجريبي", grade="الأول",
        )
        self.family = Family.objects.create(school=self.school, guardian_name="ولي تجريبي")
        self.learning_account = LearningAccount.objects.create(
            email="learner@example.test", full_name="متعلم تجريبي", password="not-a-real-hash",
        )
        self.learning_subject = LearningSubject.objects.create(name="مادة تجريبية", slug="مادة-تجريبية")
        self.announcement = Announcement.objects.create(title="إعلان تجريبي", message="اختبار")

    def test_preview_does_not_delete_and_returns_signed_snapshot(self):
        preview = collect_production_reset_preview(keep_user=self.manager)
        self.assertGreater(preview["total_records"], 0)
        self.assertTrue(preview["preview_token"])
        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(LearningAccount.objects.count(), 1)
        self.assertEqual(School.objects.count(), 1)

    def test_execute_deletes_operations_and_preserves_manager_and_settings(self):
        preview = collect_production_reset_preview(keep_user=self.manager)
        run = execute_production_data_reset(
            keep_user=self.manager,
            preview_token=preview["preview_token"],
        )

        self.assertEqual(run.status, ProductionDataResetRun.Status.SUCCEEDED)
        self.assertFalse(Student.objects.exists())
        self.assertFalse(Family.objects.exists())
        self.assertFalse(LearningAccount.objects.exists())
        self.assertFalse(LearningSubject.objects.exists())
        self.assertFalse(Announcement.objects.exists())
        self.assertFalse(User.objects.exclude(pk=self.manager.pk).exists())

        self.assertTrue(User.objects.filter(pk=self.manager.pk, is_superuser=True).exists())
        self.assertTrue(School.objects.filter(pk=self.school.pk).exists())
        self.assertTrue(Branch.objects.filter(pk=self.branch.pk).exists())
        self.assertTrue(Role.objects.filter(pk=self.role.pk).exists())
        self.assertTrue(RolePermissionRule.objects.filter(pk=self.permission_rule.pk).exists())
        self.assertTrue(RegistrationSettings.objects.filter(pk=self.registration_settings.pk).exists())
        self.assertTrue(DocumentTemplate.objects.filter(pk=self.template.pk).exists())
        self.assertTrue(DocumentSettings.objects.filter(pk=self.document_settings.pk).exists())
        self.assertTrue(SchoolScheduleSettings.objects.filter(pk=self.schedule_settings.pk).exists())
        self.assertTrue(OpenEMISSettings.objects.filter(pk=self.openemis_settings.pk).exists())
        self.assertTrue(LearningAISettings.objects.filter(pk=self.ai_settings.pk).exists())
        self.assertTrue(Module.objects.filter(pk=self.development_module.pk).exists())
        self.assertFalse(any(run.remaining_counts.values()))

    def test_stale_preview_is_rejected_without_partial_delete(self):
        preview = collect_production_reset_preview(keep_user=self.manager)
        Announcement.objects.create(title="سجل بعد المعاينة", message="تغيير")
        with self.assertRaisesMessage(ValueError, "تغيرت البيانات بعد المعاينة"):
            execute_production_data_reset(
                keep_user=self.manager,
                preview_token=preview["preview_token"],
            )
        self.assertTrue(Student.objects.filter(pk=self.student.pk).exists())
        self.assertTrue(Announcement.objects.filter(title="سجل بعد المعاينة").exists())


class ProductionDataResetViewTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_superuser("reset_view_owner", "view@example.test", "x")
        self.school = School.objects.create(name="مدرسة الواجهة", is_active=True)
        Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        Student.objects.create(student_number="VIEW-1", full_name="طالب واجهة", grade="الأول")
        self.client.force_login(self.manager)

    def test_page_requires_superuser_and_exposes_preview(self):
        response = self.client.get(reverse("core:production_launch_preparation"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "معاينة البيانات التي ستُحذف")
        self.assertContains(response, PRODUCTION_RESET_CONFIRMATION)

    def test_post_requires_exact_confirmation(self):
        response = self.client.get(reverse("core:production_launch_preparation"))
        token = response.context["preview"]["preview_token"]
        response = self.client.post(
            reverse("core:production_launch_preparation"),
            {"preview_token": token, "acknowledged": "yes", "confirmation": "تهيئة"},
            follow=True,
        )
        self.assertContains(response, "اكتب العبارة")
        self.assertTrue(Student.objects.exists())

    def test_confirmed_post_executes_and_opens_report(self):
        response = self.client.get(reverse("core:production_launch_preparation"))
        token = response.context["preview"]["preview_token"]
        response = self.client.post(
            reverse("core:production_launch_preparation"),
            {
                "preview_token": token,
                "acknowledged": "yes",
                "confirmation": PRODUCTION_RESET_CONFIRMATION,
            },
        )
        run = ProductionDataResetRun.objects.get(status=ProductionDataResetRun.Status.SUCCEEDED)
        self.assertRedirects(response, reverse("core:production_reset_report", kwargs={"pk": run.pk}))
        self.assertFalse(Student.objects.exists())
