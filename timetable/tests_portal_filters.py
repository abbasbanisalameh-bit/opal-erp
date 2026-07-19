from datetime import date, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from academics.models import Enrollment, Grade, Section, Subject
from core.models import AcademicYear, Branch, School
from parent_portal.models import Family, FamilyStudent
from students.models import Student
from teachers.models import Teacher, TeacherAssignment

from .models import TimeSlot, TimetableEntry


class TimetablePortalFilterTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة الجداول", is_active=True)
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        self.grade = Grade.objects.create(school=self.school, name="الخامس", order=5)
        self.section_a = Section.objects.create(academic_year=self.year, branch=self.branch, grade=self.grade, name="أ")
        self.section_b = Section.objects.create(academic_year=self.year, branch=self.branch, grade=self.grade, name="ب")
        self.math = Subject.objects.create(grade=self.grade, name="رياضيات", code="M5")
        self.arabic = Subject.objects.create(grade=self.grade, name="لغة عربية", code="A5")
        self.slot1 = TimeSlot.objects.create(name="الأولى", start_time=time(8), end_time=time(8, 45), order=1)
        self.slot2 = TimeSlot.objects.create(name="الثانية", start_time=time(9), end_time=time(9, 45), order=2)

        self.teacher_user = User.objects.create_user("filter_teacher")
        self.teacher = Teacher.objects.create(user=self.teacher_user, school=self.school, branch=self.branch, employee_number="TF-1", full_name="معلم الفلاتر")
        TeacherAssignment.objects.create(teacher=self.teacher, academic_year=self.year, section=self.section_a, subject=self.math)
        TeacherAssignment.objects.create(teacher=self.teacher, academic_year=self.year, section=self.section_b, subject=self.arabic)
        TimetableEntry.objects.create(academic_year=self.year, section=self.section_a, subject=self.math, teacher=self.teacher, day="sunday", time_slot=self.slot1)
        TimetableEntry.objects.create(academic_year=self.year, section=self.section_b, subject=self.arabic, teacher=self.teacher, day="monday", time_slot=self.slot2)

        self.parent_user = User.objects.create_user("filter_parent")
        self.family = Family.objects.create(school=self.school, user=self.parent_user, guardian_name="ولي الجدول", phone="0790000022", family_code="TFAM-1")
        self.student = Student.objects.create(student_number="TT-1", full_name="طالب الجدول", grade=self.grade.name, section=self.section_a.name)
        FamilyStudent.objects.create(family=self.family, student=self.student)
        Enrollment.objects.create(student=self.student, academic_year=self.year, grade=self.grade, section=self.section_a, status="active")
        self.manager = User.objects.create_user("filter_manager", is_staff=True)

    def test_teacher_filters_by_day_section_and_subject(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse("teachers:portal_timetable"), {
            "day": "sunday", "section": self.section_a.pk, "subject": self.math.pk,
        })
        self.assertEqual(response.status_code, 200)
        entries = list(response.context["entries"])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].subject, self.math)

    def test_parent_filters_by_student_day_and_subject(self):
        self.client.force_login(self.parent_user)
        response = self.client.get(reverse("parent_portal:timetable"), {
            "student": self.student.pk, "day": "sunday", "subject": self.math.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "طالب الجدول")
        rows = response.context["rows"]
        entries = list(rows[0]["entries"])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].subject, self.math)

    def test_manager_filters_by_teacher_day_subject_and_grade(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("timetable:dashboard"), {
            "teacher": self.teacher.pk,
            "day": "monday",
            "subject": self.arabic.pk,
            "grade": self.grade.pk,
        })
        self.assertEqual(response.status_code, 200)
        entries = list(response.context["entries"])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].subject, self.arabic)
