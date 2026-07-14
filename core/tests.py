from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.conf import settings
from django.urls import NoReverseMatch, reverse
from django.contrib.auth.models import User

from .models import AcademicYear, Branch, School, Semester


class AcademicPeriodValidationTest(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة اختبار")
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )

    def test_only_one_current_academic_year_per_school(self):
        next_year = AcademicYear.objects.create(
            school=self.school,
            name="2027/2028",
            start_date=date(2027, 9, 1),
            end_date=date(2028, 6, 30),
            is_current=True,
        )
        self.year.refresh_from_db()
        self.assertFalse(self.year.is_current)
        self.assertTrue(next_year.is_current)

    def test_semester_dates_must_be_inside_year(self):
        semester = Semester(
            academic_year=self.year,
            name="الفصل الأول",
            start_date=date(2026, 8, 20),
            end_date=date(2027, 1, 20),
        )
        with self.assertRaises(ValidationError):
            semester.full_clean()

    def test_only_one_current_semester_per_year(self):
        first = Semester.objects.create(
            academic_year=self.year,
            name="الفصل الأول",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 1, 20),
            is_current=True,
        )
        second = Semester.objects.create(
            academic_year=self.year,
            name="الفصل الثاني",
            start_date=date(2027, 1, 21),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        first.refresh_from_db()
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)


class OptionalModuleSeparationTests(TestCase):
    def test_optional_modules_are_hidden_in_school_settings(self):
        self.assertFalse(settings.OPAL_ENABLE_OPENEMIS)
        self.assertFalse(settings.OPAL_ENABLE_DEVELOPMENT_CENTER)
        with self.assertRaises(NoReverseMatch):
            reverse("openemis:settings")
        with self.assertRaises(NoReverseMatch):
            reverse("development_center:dashboard")


class SiteOnlyDataEntryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("manager", password="x", is_staff=True)
        self.school = School.objects.create(name="مدرسة الموقع", is_active=True)
        self.client.force_login(self.user)

    def test_django_admin_route_is_not_an_operational_data_entry_route(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 404)

    def test_branch_is_created_from_the_site_screen(self):
        response = self.client.post(reverse("core:branch_list"), {
            "name": "فرع الموقع",
            "phone": "0790000000",
            "address": "عمان",
            "is_main": "on",
            "is_active": "on",
        })
        self.assertRedirects(response, reverse("core:branch_list"))
        self.assertTrue(Branch.objects.filter(school=self.school, name="فرع الموقع", is_main=True).exists())


class DemoDataSafetyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("demo_owner", "owner@example.test", "x")
        self.school = School.objects.create(name="مدرسة المختبر", is_active=True)

    def test_superuser_sees_demo_lab_buttons(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:system_settings"))
        self.assertContains(response, "إضافة بيانات تجريبية")
        self.assertContains(response, "تصفير البيانات التجريبية")

    def test_seed_and_reset_only_touch_demo_people(self):
        from core.demo_data import reset_demo_school, seed_demo_school
        from students.models import Student
        from teachers.models import Teacher, TeacherDocument
        from accounting.models import Receipt
        from parent_portal.models import Family

        real = Student.objects.create(student_number="REAL-WITNESS", full_name="طالب حقيقي", grade="الأول")
        result = seed_demo_school(student_count=4, teacher_count=2, user=self.user)
        self.assertEqual(result["students"], 4)
        self.assertEqual(Student.objects.filter(is_demo=True).count(), 4)
        self.assertEqual(Teacher.objects.filter(is_demo=True).count(), 2)
        self.assertEqual(TeacherDocument.objects.filter(teacher__is_demo=True).count(), 4)
        self.assertEqual(Receipt.objects.filter(payment__invoice__student__is_demo=True).count(), 4)
        self.assertEqual(Family.objects.count(), 2)

        reset_demo_school()
        self.assertFalse(Student.objects.filter(is_demo=True).exists())
        self.assertFalse(Teacher.objects.filter(is_demo=True).exists())
        self.assertTrue(Student.objects.filter(pk=real.pk, student_number="REAL-WITNESS").exists())


class DataIntegrityCenterTests(TestCase):
    def setUp(self):
        from academics.models import Grade, Section
        from students.models import Student

        self.user = User.objects.create_superuser("integrity_owner", "integrity@example.test", "x")
        self.school = School.objects.create(name="مدرسة السلامة", is_active=True)
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.year = AcademicYear.objects.create(
            school=self.school, name="2026/2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 30), is_current=True
        )
        self.grade = Grade.objects.create(school=self.school, name="الأول")
        self.section = Section.objects.create(academic_year=self.year, branch=self.branch, grade=self.grade, name="أ")
        self.student = Student.objects.create(
            student_number="INT-1", national_id="DUP-NID", full_name="طالب التعارض", grade="صف خاطئ", section="شعبة خاطئة"
        )
        Student.objects.create(student_number="INT-2", national_id="DUP-NID", full_name="طالب مكرر", grade="الأول", status="archived", is_active=False)

    def _create_fixable_conflicts(self):
        from academics.models import Enrollment, Subject
        from accounting.models import FeeCategory, StudentInvoice, StudentPayment
        from exams.models import Exam
        from teachers.models import Teacher

        Enrollment.objects.create(student=self.student, academic_year=self.year, grade=self.grade, section=self.section, status="active")
        teacher_user = User.objects.create_user("mismatch_teacher", password="x", is_active=True)
        teacher = Teacher.objects.create(user=teacher_user, employee_number="INT-T-1", full_name="معلم متوقف", school=self.school, branch=self.branch, is_active=False)
        category = FeeCategory.objects.create(name="اختبار السلامة", amount=100)
        invoice = StudentInvoice.objects.create(student=self.student, academic_year=self.year, fee_category=category, amount=100, due_date=date.today())
        StudentPayment.objects.create(invoice=invoice, amount=50)
        StudentInvoice.objects.filter(pk=invoice.pk).update(status="open", paid=False)
        subject = Subject.objects.create(name="رياضيات", grade=self.grade)
        exam = Exam.objects.create(name="امتحان منشور", exam_type="monthly", academic_year=self.year, grade=self.grade, subject=subject, status="published", is_locked=False)
        return teacher, teacher_user, invoice, exam

    def test_scan_detects_but_does_not_change_data(self):
        from core.data_integrity import run_integrity_audit
        from academics.models import Enrollment

        self._create_fixable_conflicts()
        run = run_integrity_audit(fix_safe=False, user=self.user)
        codes = set(run.issues.values_list("code", flat=True))
        self.assertIn("STUDENT_DUPLICATE_NATIONAL_ID", codes)
        self.assertIn("STUDENT_ACADEMIC_SNAPSHOT_MISMATCH", codes)
        self.student.refresh_from_db()
        self.assertEqual(self.student.grade, "صف خاطئ")
        self.assertEqual(run.fixed_count, 0)

    def test_safe_fix_repairs_certain_fields_but_never_merges_duplicates(self):
        from core.data_integrity import run_integrity_audit
        from students.models import Student

        teacher, teacher_user, invoice, exam = self._create_fixable_conflicts()
        run = run_integrity_audit(fix_safe=True, user=self.user)
        self.student.refresh_from_db(); teacher_user.refresh_from_db(); invoice.refresh_from_db(); exam.refresh_from_db()
        self.assertEqual(self.student.grade, self.grade.name)
        self.assertEqual(self.student.section, self.section.name)
        self.assertFalse(teacher_user.is_active)
        self.assertEqual(invoice.status, "partial")
        self.assertTrue(exam.is_locked)
        duplicate = run.issues.get(code="STUDENT_DUPLICATE_NATIONAL_ID")
        self.assertFalse(duplicate.is_fixable)
        self.assertFalse(duplicate.is_fixed)
        self.assertEqual(Student.objects.filter(national_id="DUP-NID").count(), 2)

    def test_integrity_center_is_visible_to_superuser(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:integrity_center"))
        self.assertContains(response, "فحص وإصلاح آمن")
