from datetime import date

from django.test import TestCase

from core.models import School, Branch, AcademicYear
from academics.models import (
    Grade,
    Section,
    StudentRecord,
    Enrollment,
    Guardian,
    StudentGuardian,
    StudentDocument,
    Subject,
)


class AcademicsModelsTest(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة اختبار")
        self.branch = Branch.objects.create(school=self.school, name="الفرع الرئيسي")
        self.academic_year = AcademicYear.objects.create(
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_active=True,
        )

    def test_create_grade_section_and_subject(self):
        grade = Grade.objects.create(
            school=self.school,
            name="الصف الأول",
            order=1,
        )

        section = Section.objects.create(
            academic_year=self.academic_year,
            branch=self.branch,
            grade=grade,
            name="أ",
            capacity=30,
        )

        subject = Subject.objects.create(
            name="الرياضيات",
            code="MATH1",
            grade=grade,
        )

        self.assertEqual(str(grade), "الصف الأول")
        self.assertEqual(str(section), "الصف الأول - أ")
        self.assertIn("الرياضيات", str(subject))

    def test_create_student_and_enrollment(self):
        grade = Grade.objects.create(
            school=self.school,
            name="الصف الثاني",
            order=2,
        )

        section = Section.objects.create(
            academic_year=self.academic_year,
            branch=self.branch,
            grade=grade,
            name="ب",
        )

        student = StudentRecord.objects.create(
            school=self.school,
            branch=self.branch,
            student_number="ST-001",
            full_name="طالب اختبار",
            gender="male",
        )

        enrollment = Enrollment.objects.create(
            student=student,
            academic_year=self.academic_year,
            grade=grade,
            section=section,
            status="active",
        )

        self.assertEqual(str(student), "طالب اختبار")
        self.assertEqual(enrollment.student, student)
        self.assertEqual(enrollment.grade, grade)
        self.assertEqual(enrollment.section, section)

    def test_create_guardian_and_link_to_student(self):
        student = StudentRecord.objects.create(
            school=self.school,
            branch=self.branch,
            student_number="ST-002",
            full_name="طالبة اختبار",
            gender="female",
        )

        guardian = Guardian.objects.create(
            school=self.school,
            full_name="ولي أمر اختبار",
            relation="father",
            phone="0790000000",
        )

        link = StudentGuardian.objects.create(
            student=student,
            guardian=guardian,
            is_primary=True,
        )

        self.assertEqual(link.student, student)
        self.assertEqual(link.guardian, guardian)
        self.assertTrue(link.is_primary)

    def test_create_student_document(self):
        student = StudentRecord.objects.create(
            school=self.school,
            branch=self.branch,
            student_number="ST-003",
            full_name="طالب وثائق",
            gender="male",
        )

        document = StudentDocument.objects.create(
            student=student,
            document_type="photo",
            title="صورة شخصية",
        )

        self.assertEqual(document.student, student)
        self.assertEqual(document.title, "صورة شخصية")
