from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase

from accounts.models import Role, UserProfile
from accounts.workflow import (
    can_manage_roles,
    impersonation_target_kind,
    is_management_user,
    role_code,
)
from core.models import School
from parent_portal.models import Family
from teachers.models import Teacher


class AccountAccessWorkflowContractTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة عقد الصلاحيات", is_active=True)
        self.management_role = Role.objects.create(code="principal", name="مدير المدرسة")
        self.teacher_role = Role.objects.create(code="teacher", name="معلم")

    def test_role_resolution_and_management_policy_are_preserved(self):
        anonymous = AnonymousUser()
        self.assertEqual(role_code(anonymous), "")
        self.assertFalse(is_management_user(anonymous))

        manager = User.objects.create_user("role-manager", password="pass")
        UserProfile.objects.create(user=manager, school=self.school, role=self.management_role)
        self.assertEqual(role_code(manager), "principal")
        self.assertTrue(is_management_user(manager))
        self.assertFalse(can_manage_roles(manager))

        owner = User.objects.create_superuser("role-owner", "owner@example.test", "pass")
        self.assertTrue(is_management_user(owner))
        self.assertTrue(can_manage_roles(owner))

    def test_impersonation_targets_remain_teacher_or_parent_only(self):
        teacher_user = User.objects.create_user("role-teacher", password="pass")
        Teacher.objects.create(
            user=teacher_user,
            employee_number="ROLE-T-1",
            full_name="معلم عقد الصلاحيات",
            school=self.school,
        )
        self.assertEqual(impersonation_target_kind(teacher_user), "teacher")

        parent_user = User.objects.create_user("role-parent", password="pass")
        Family.objects.create(
            user=parent_user,
            school=self.school,
            guardian_name="ولي أمر عقد الصلاحيات",
            phone="0799999999",
        )
        self.assertEqual(impersonation_target_kind(parent_user), "parent")

        staff_user = User.objects.create_user("role-staff", password="pass", is_staff=True)
        self.assertEqual(impersonation_target_kind(staff_user), "")
