from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from academics.models import Enrollment, Grade, Section, Subject
from core.models import AcademicYear, Branch, School
from students.models import Student
from teachers.models import Teacher, TeacherAssignment

from .models import Exam, StudentMark


class UnifiedExamWorkflowTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة الامتحانات الموحدة", is_active=True)
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        self.semester = self.year.semesters.get(code="first")
        self.grade = Grade.objects.create(school=self.school, name="السادس", order=6)
        self.section = Section.objects.create(
            academic_year=self.year, branch=self.branch, grade=self.grade, name="أ"
        )
        self.subject = Subject.objects.create(academic_year=self.year, name="اللغة العربية", grade=self.grade)
        self.teacher_user = User.objects.create_user("arabic_teacher", password="pass12345")
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            school=self.school,
            branch=self.branch,
            employee_number="T-AR-1",
            full_name="أحمد المعلم",
        )
        self.assignment = TeacherAssignment.objects.create(
            teacher=self.teacher,
            academic_year=self.year,
            section=self.section,
            subject=self.subject,
        )
        self.manager = User.objects.create_superuser("exam_manager", "manager@example.test", "pass12345")
        self.students = []
        for index in range(2):
            student = Student.objects.create(
                student_number=f"EX-{index + 1}", full_name=f"طالب {index + 1}", grade=self.grade.name
            )
            Enrollment.objects.create(
                student=student,
                academic_year=self.year,
                grade=self.grade,
                section=self.section,
                status="active",
            )
            self.students.append(student)

    def test_manager_exam_is_linked_to_exact_assignment_and_teacher_submits(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse("exams:exam_create"), {
            "academic_year": self.year.pk,
            "semester": self.semester.pk,
            "grade": self.grade.pk,
            "section": self.section.pk,
            "subject": self.subject.pk,
            "exam_type": "first",
            "max_mark": "20",
            "pass_percentage": "50",
            "weight": "25",
        })
        self.assertEqual(response.status_code, 302)
        exam = Exam.objects.get()
        self.assertEqual(exam.teacher_assignment, self.assignment)
        self.assertEqual(exam.section, self.section)
        self.assertEqual(exam.status, "open")

        self.client.force_login(self.teacher_user)
        response = self.client.post(
            reverse("exams:exam_marks_bulk", args=[exam.pk]),
            {
                "assignment": self.assignment.pk,
                "action": "submit",
                f"mark_{self.students[0].pk}": "18",
                f"mark_{self.students[1].pk}": "17",
            },
        )
        self.assertEqual(response.status_code, 302)
        exam.refresh_from_db()
        self.assertEqual(exam.status, "submitted")
        self.assertEqual(exam.submitted_by, self.teacher_user)
        self.assertEqual(StudentMark.objects.filter(exam=exam).count(), 2)

    def test_gradebook_shows_four_assessments_horizontally(self):
        exam_types = ["first", "second", "third", "final"]
        for exam_type, mark in zip(exam_types, [15, 16, 17, 35]):
            exam = Exam.objects.create(
                exam_type=exam_type,
                academic_year=self.year,
                semester=self.semester,
                grade=self.grade,
                section=self.section,
                subject=self.subject,
                teacher_assignment=self.assignment,
                status="published",
                max_mark=40 if exam_type == "final" else 20,
                is_locked=True,
            )
            StudentMark.objects.create(exam=exam, student=self.students[0], mark=Decimal(mark))
        self.client.force_login(self.manager)
        response = self.client.get(reverse("exams:exam_list"), {
            "academic_year": self.year.pk,
            "semester": self.semester.pk,
            "grade": self.grade.pk,
            "section": self.section.pk,
            "subject": self.subject.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "الامتحان الأول")
        self.assertContains(response, "الامتحان الثاني")
        self.assertContains(response, "الامتحان الثالث")
        self.assertContains(response, "الامتحان النهائي")
        self.assertContains(response, "83")
