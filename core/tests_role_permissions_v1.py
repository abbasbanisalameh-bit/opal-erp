from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from academics.models import Enrollment, Grade, Section, Subject
from core.models import AcademicYear, Branch, School
from exams.models import Exam, StudentMark
from openemis_integration.models import OpenEMISSyncLog
from parent_portal.models import Family, FamilyStudent
from students.models import Student
from teachers.models import Homework, Teacher, TeacherAssignment


class RolePermissionWorkflowTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة الصلاحيات", is_active=True)
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي")
        self.year = AcademicYear.objects.create(school=self.school, name="2026/2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 30), is_current=True)
        self.grade = Grade.objects.create(school=self.school, name="السابع", order=7)
        self.teacher_user = User.objects.create_user("teacher_perm", password="pass12345")
        self.teacher = Teacher.objects.create(user=self.teacher_user, employee_number="TP-1", full_name="معلم الصلاحيات", school=self.school, branch=self.branch)
        self.other_teacher_user = User.objects.create_user("teacher_other", password="pass12345")
        self.other_teacher = Teacher.objects.create(user=self.other_teacher_user, employee_number="TP-2", full_name="معلم آخر", school=self.school, branch=self.branch)
        self.section = Section.objects.create(academic_year=self.year, branch=self.branch, grade=self.grade, name="أ", homeroom_teacher=self.teacher)
        self.other_section = Section.objects.create(academic_year=self.year, branch=self.branch, grade=self.grade, name="ب", homeroom_teacher=self.other_teacher)
        self.subject = Subject.objects.create(name="رياضيات", grade=self.grade)
        self.assignment = TeacherAssignment.objects.create(teacher=self.teacher, academic_year=self.year, section=self.section, subject=self.subject)
        self.other_assignment = TeacherAssignment.objects.create(teacher=self.teacher, academic_year=self.year, section=self.other_section, subject=self.subject)
        self.student = Student.objects.create(student_number="PS-1", full_name="طالب أول", grade=self.grade.name)
        self.student2 = Student.objects.create(student_number="PS-2", full_name="طالب ثان", grade=self.grade.name)
        Enrollment.objects.create(student=self.student, academic_year=self.year, grade=self.grade, section=self.section, status="active")
        Enrollment.objects.create(student=self.student2, academic_year=self.year, grade=self.grade, section=self.section, status="active")
        self.parent_user = User.objects.create_user("parent_perm", password="pass12345")
        self.family = Family.objects.create(user=self.parent_user, school=self.school, guardian_name="ولي الأمر", phone="0790000000")
        FamilyStudent.objects.create(family=self.family, student=self.student)
        self.manager = User.objects.create_superuser("manager_perm", "manager@example.com", "pass12345")
        self.exam = Exam.objects.create(exam_type="first", academic_year=self.year, semester=self.year.semesters.get(code="first"), grade=self.grade, subject=self.subject, status="open")

    def test_management_cannot_enter_marks(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("exams:exam_marks_bulk", args=[self.exam.pk]))
        self.assertEqual(response.status_code, 403)

    def test_teacher_enters_marks_and_manager_approves_for_parent_and_openemis(self):
        self.client.force_login(self.teacher_user)
        url = reverse("exams:exam_marks_bulk", args=[self.exam.pk]) + f"?assignment={self.assignment.pk}"
        response = self.client.post(url, {"assignment": self.assignment.pk, f"mark_{self.student.pk}": "18", f"mark_{self.student2.pk}": "15"})
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.manager)
        response = self.client.post(reverse("exams:exam_action", args=[self.exam.pk]), {"action": "approve"})
        self.assertEqual(response.status_code, 302)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.status, "published")
        self.assertTrue(self.exam.is_locked)
        self.assertEqual(OpenEMISSyncLog.objects.filter(operation="sync_marks", status="pending").count(), 2)
        self.client.force_login(self.parent_user)
        response = self.client.get(reverse("parent_portal:marks"))
        self.assertContains(response, "18")

    def test_attendance_is_homeroom_only(self):
        self.client.force_login(self.teacher_user)
        allowed = self.client.get(reverse("teachers:portal_attendance_section", args=[self.section.pk]))
        self.assertEqual(allowed.status_code, 200)
        denied = self.client.get(reverse("teachers:portal_attendance", args=[self.other_assignment.pk]))
        self.assertRedirects(denied, reverse("teachers:portal_dashboard"), fetch_redirect_response=False)

    def test_homework_visible_to_parent(self):
        Homework.objects.create(assignment=self.assignment, title="حل الأسئلة", description="صفحة 10", due_date=date.today() + timedelta(days=2), created_by=self.teacher_user)
        self.client.force_login(self.parent_user)
        response = self.client.get(reverse("parent_portal:homework"))
        self.assertContains(response, "حل الأسئلة")

    def test_parent_personal_edit_cannot_change_official_fields(self):
        self.client.force_login(self.parent_user)
        response = self.client.post(reverse("parent_portal:student_personal_update", args=[self.student.pk]), {"phone": "0791234567", "address": "إربد", "blood_type": "A+", "medical_notes": "", "full_name": "اسم ممنوع", "student_number": "CHANGED"})
        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.full_name, "طالب أول")
        self.assertEqual(self.student.student_number, "PS-1")
        self.assertEqual(self.student.phone, "0791234567")

    def test_parent_rank_uses_published_marks_in_same_section(self):
        StudentMark.objects.create(exam=self.exam, student=self.student, mark=Decimal("18"))
        StudentMark.objects.create(exam=self.exam, student=self.student2, mark=Decimal("15"))
        self.exam.status = "published"
        self.exam.is_locked = True
        self.exam.save(update_fields=["status", "is_locked"])
        self.client.force_login(self.parent_user)
        response = self.client.get(reverse("parent_portal:student_detail", args=[self.student.pk]))
        self.assertContains(response, "1 من 2")
