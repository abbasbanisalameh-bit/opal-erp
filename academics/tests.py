from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

from admissions.models import GradeFee
from core.models import AcademicYear, Branch, School
from students.models import Student
from teachers.models import Teacher

from .lifecycle import perform_lifecycle_action
from .models import Enrollment, Grade, Guardian, Section, StudentDocument, StudentGuardian, StudentLifecycleEvent, Subject


class AcademicsModelsTest(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة اختبار")
        self.branch = Branch.objects.create(school=self.school, name="الفرع الرئيسي")
        self.year = AcademicYear.objects.create(
            school=self.school, name="2026/2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 30), is_current=True
        )
        self.next_year = AcademicYear.objects.create(
            school=self.school, name="2027/2028", start_date=date(2027, 9, 1), end_date=date(2028, 6, 30)
        )
        self.grade = Grade.objects.create(school=self.school, name="الصف الأول", order=1)
        self.next_grade = Grade.objects.create(school=self.school, name="الصف الثاني", order=2)
        self.section = Section.objects.create(academic_year=self.year, branch=self.branch, grade=self.grade, name="أ", capacity=30)
        self.next_section = Section.objects.create(academic_year=self.next_year, branch=self.branch, grade=self.next_grade, name="أ", capacity=1)
        self.student = Student.objects.create(student_number="ST-001", full_name="طالب اختبار", grade=self.grade.name, section=self.section.name)

    def test_create_grade_section_subject_and_enrollment(self):
        subject = Subject.objects.create(name="الرياضيات", code="MATH1", grade=self.grade)
        enrollment = Enrollment.objects.create(student=self.student, academic_year=self.year, grade=self.grade, section=self.section)
        self.assertEqual(str(self.section), "الصف الأول - أ")
        self.assertIn("الرياضيات", str(subject))
        self.assertEqual(enrollment.student, self.student)
        self.assertEqual(self.section.available_seats, 29)

    def test_guardian_and_document_use_official_student(self):
        guardian = Guardian.objects.create(school=self.school, full_name="ولي أمر اختبار", relation="father", phone="0790000000")
        link = StudentGuardian.objects.create(student=self.student, guardian=guardian, is_primary=True)
        document = StudentDocument.objects.create(student=self.student, document_type="photo", title="صورة شخصية")
        self.assertTrue(link.is_primary)
        self.assertEqual(document.student, self.student)

    def test_promote_closes_old_enrollment_and_creates_event(self):
        old = Enrollment.objects.create(student=self.student, academic_year=self.year, grade=self.grade, section=self.section)
        event = perform_lifecycle_action(
            student=self.student,
            action="promote",
            target_year=self.next_year,
            target_grade=self.next_grade,
            target_section=self.next_section,
            effective_date=date(2027, 9, 1),
        )
        old.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(old.status, "completed")
        self.assertEqual(event.action, "promote")
        self.assertEqual(self.student.grade, self.next_grade.name)
        self.assertTrue(Enrollment.objects.filter(student=self.student, academic_year=self.next_year, status="active").exists())
        self.assertEqual(StudentLifecycleEvent.objects.count(), 1)

    def test_promotion_rejects_full_section(self):
        other = Student.objects.create(student_number="ST-002", full_name="طالب آخر", grade=self.next_grade.name)
        Enrollment.objects.create(student=other, academic_year=self.next_year, grade=self.next_grade, section=self.next_section)
        with self.assertRaises(ValidationError):
            perform_lifecycle_action(
                student=self.student,
                action="reenroll",
                target_year=self.next_year,
                target_grade=self.next_grade,
                target_section=self.next_section,
            )


class AcademicStructureFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="safe-password")
        self.school = School.objects.create(name="مدرسة الهيكل", is_active=True)
        self.branch = Branch.objects.create(school=self.school, name="الفرع الرئيسي", is_main=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        self.teacher = Teacher.objects.create(
            school=self.school,
            branch=self.branch,
            employee_number="T-STRUCT-1",
            full_name="معلم الصف",
        )
        self.client.force_login(self.user)

    def test_configuring_grade_creates_fee_default_section_and_homeroom_teacher(self):
        response = self.client.post(reverse("academics:academic_structure"), {
            "action": "configure_grade",
            "academic_year": self.year.pk,
            "grade-name": "الصف الأول",
            "grade-order": 1,
            "grade-tuition_fee": "1250.00",
            "grade-section_count": 1,
            "grade-homeroom_teacher": self.teacher.pk,
        })
        self.assertRedirects(response, f"{reverse('academics:academic_structure')}?year={self.year.pk}")
        grade = Grade.objects.get(school=self.school, name="الصف الأول")
        self.assertEqual(GradeFee.objects.get(school=self.school, academic_year=self.year, grade=grade).tuition_fee, 1250)
        section = Section.objects.get(academic_year=self.year, grade=grade)
        self.assertTrue(section.is_default)
        self.assertEqual(section.homeroom_teacher, self.teacher)

    def test_configuring_existing_grade_updates_fee_without_duplicate_or_section_loss(self):
        grade = Grade.objects.create(school=self.school, name="الصف الثاني", order=2)
        GradeFee.objects.create(school=self.school, academic_year=self.year, grade=grade, tuition_fee=100)
        section = Section.objects.create(academic_year=self.year, branch=self.branch, grade=grade, name="أ")
        self.client.post(reverse("academics:academic_structure"), {
            "action": "configure_grade",
            "academic_year": self.year.pk,
            "grade-name": "الصف الثاني",
            "grade-order": 2,
            "grade-tuition_fee": "150.00",
            "grade-section_count": 3,
        })
        self.assertEqual(GradeFee.objects.filter(school=self.school, academic_year=self.year, grade=grade).count(), 1)
        self.assertEqual(GradeFee.objects.get(school=self.school, academic_year=self.year, grade=grade).tuition_fee, 150)
        self.assertEqual(Section.objects.filter(academic_year=self.year, grade=grade).count(), 1)
        self.assertTrue(Section.objects.filter(pk=section.pk).exists())
