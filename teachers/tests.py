from datetime import date

from django.test import TestCase

from academics.models import Grade, Section, Subject
from core.models import AcademicYear, Branch, School

from .forms import TeacherAssignmentForm, TeacherForm
from .models import Teacher


class CanonicalTeacherEntryTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة المعلم")
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي")
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
        )
        self.grade = Grade.objects.create(school=self.school, name="الأول")
        self.section = Section.objects.create(
            academic_year=self.year, branch=self.branch, grade=self.grade, name="أ"
        )
        self.subject = Subject.objects.create(name="رياضيات", grade=self.grade)
        self.teacher = Teacher.objects.create(
            school=self.school, branch=self.branch, employee_number="T-CAN-1", full_name="معلم موحد"
        )

    def test_teacher_form_does_not_link_user_account(self):
        self.assertNotIn("user", TeacherForm(instance=self.teacher).fields)

    def test_assignment_rejects_section_from_another_school(self):
        other_school = School.objects.create(name="مدرسة أخرى")
        other_branch = Branch.objects.create(school=other_school, name="فرع آخر")
        other_year = AcademicYear.objects.create(
            school=other_school,
            name="2026/2027 أخرى",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
        )
        other_grade = Grade.objects.create(school=other_school, name="الأول")
        other_section = Section.objects.create(
            academic_year=other_year, branch=other_branch, grade=other_grade, name="ب"
        )
        form = TeacherAssignmentForm(
            data={
                "academic_year": self.year.pk,
                "section": other_section.pk,
                "subject": self.subject.pk,
                "is_primary": True,
                "is_active": True,
            },
            teacher=self.teacher,
        )
        self.assertFalse(form.is_valid())
