import json
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from academics.models import Enrollment, Grade, Section
from core.models import AcademicYear, Branch, School
from parent_portal.models import Family, FamilyStudent
from students.models import Student
from teachers.models import Teacher

from .models import LearningAccessSettings, LearningAccount, LearningSubject, LearningSubscriptionCard
from .security_services import issue_api_token


class R34MobileSchoolSSOTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة تطبيق R34")
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            midyear_break_start=date(2027, 1, 15),
            midyear_break_end=date(2027, 1, 31),
            is_current=True,
        )
        self.grade = Grade.objects.create(school=self.school, name="الصف الأول", order=1)
        self.section = Section.objects.create(academic_year=self.year, branch=self.branch, grade=self.grade, name="أ", capacity=30)
        self.settings = LearningAccessSettings.objects.create(school=self.school, parent_default_enabled=True, teacher_sso_enabled=True)

    def test_guardian_uses_same_erp_credentials_and_gets_child_learning_token(self):
        user = User.objects.create_user(username="guardian-r34", password="Secret@123")
        family = Family.objects.create(school=self.school, user=user, guardian_name="أحمد خالد", phone="0790000001")
        student = Student.objects.create(student_number="R34-S1", full_name="عمر أحمد خالد", guardian_name=family.guardian_name, grade="", section="")
        Enrollment.objects.create(student=student, academic_year=self.year, grade=self.grade, section=self.section, status="active")
        FamilyStudent.objects.create(family=family, student=student)
        response = self.client.post(
            reverse("learning_platform:api_school_login"),
            data=json.dumps({"username": "guardian-r34", "password": "Secret@123", "device_name": "Android Test"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()["data"]
        self.assertEqual(body["mode"], "guardian")
        self.assertEqual(len(body["profiles"]), 1)
        profile = body["profiles"][0]
        self.assertEqual(profile["profile"]["student_id"], student.pk)
        self.assertTrue(profile["account"]["is_school_managed"])
        self.assertTrue(profile["token"])

    def test_teacher_uses_same_erp_credentials(self):
        user = User.objects.create_user(username="teacher-r34", password="Secret@123")
        teacher = Teacher.objects.create(employee_number="R34-T1", user=user, full_name="معلم التطبيق", school=self.school, branch=self.branch)
        response = self.client.post(
            reverse("learning_platform:api_school_login"),
            data=json.dumps({"username": "teacher-r34", "password": "Secret@123"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()["data"]
        self.assertEqual(body["mode"], "teacher")
        self.assertEqual(body["profiles"][0]["profile"]["teacher_id"], teacher.pk)

    def test_mobile_card_redeem_uses_existing_card_activation_rules(self):
        learner = LearningAccount(email="r34-mobile@example.com", full_name="متعلم موبايل", role=LearningAccount.Role.LEARNER, is_active=True)
        learner.set_password("x")
        learner.terms_accepted_at = timezone.now()
        learner.privacy_accepted_at = timezone.now()
        learner.email_verified_at = timezone.now()
        learner.save()
        subject = LearningSubject.objects.create(name="رياضيات R34", slug="math-r34")
        card = LearningSubscriptionCard.objects.create(code="OPAL-R34-CARD", duration=LearningSubscriptionCard.Duration.MONTHLY)
        card.subjects.add(subject)
        _token_row, raw_token = issue_api_token(learner, device_name="test")
        response = self.client.post(
            reverse("learning_platform:api_subscription_card_redeem"),
            data=json.dumps({"code": card.code}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {raw_token}",
        )
        self.assertEqual(response.status_code, 201)
        card.refresh_from_db()
        self.assertEqual(card.status, LearningSubscriptionCard.Status.REDEEMED)
        self.assertEqual(card.redeemed_by_id, learner.pk)
