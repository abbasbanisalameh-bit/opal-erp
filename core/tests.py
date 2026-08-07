from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.conf import settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.db import models

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
        first = self.year.semesters.get(code="first")
        second = self.year.semesters.get(code="second")
        first.is_current = True
        first.save()
        second.is_current = True
        second.save()
        first.refresh_from_db()
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)
        self.assertEqual(self.year.semesters.count(), 2)


class OptionalModuleVisibilityTests(TestCase):
    def test_openemis_and_development_center_are_visible(self):
        self.assertTrue(settings.OPAL_ENABLE_OPENEMIS)
        self.assertTrue(settings.OPAL_ENABLE_DEVELOPMENT_CENTER)
        self.assertEqual(reverse("openemis:settings"), "/openemis/settings/")
        self.assertEqual(reverse("development_center:dashboard"), "/development/")


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


class SystemDataCenterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("data_owner", "owner@example.test", "x")
        self.school = School.objects.create(name="مدرسة المختبر", is_active=True)

    def test_superuser_sees_production_launch_preparation_entry(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:system_settings"))
        self.assertContains(response, "تهيئة التشغيل الفعلي")
        self.assertContains(response, reverse("core:production_launch_preparation"))
        self.assertNotContains(response, 'name="action" value="reset_all"')
        self.assertNotContains(response, "مختبر البيانات التجريبية")

    def test_seed_is_comprehensive_and_reset_removes_all_operational_data(self):
        from core.system_data import reset_all_operational_data, seed_system_data
        from students.models import Student
        from teachers.models import Teacher, TeacherDocument, TeacherPerformanceSnapshot
        from accounting.models import Receipt
        from parent_portal.models import Family, TeacherMonthlyEvaluation
        from parent_portal.models import FamilyStudent
        from academics.models import Grade, Section, Subject
        from teachers.models import TeacherAssignment
        from timetable.models import SchoolDayEvent, TimeSlot
        from admissions.models import FeePayment
        from documents.models import IssuedDocument
        from exams.models import Exam, StudentMark
        from timetable.models import TeacherAbsence, TimetableEntry
        from attendance_v2.models import Attendance, AttendanceRegister
        from enterprise_ops.models import MonthlyServiceEvaluation, RolePermissionRule

        Student.objects.create(student_number="OLD-WITNESS", full_name="سجل قديم", grade="الأول")
        result = seed_system_data(user=self.user)
        self.assertEqual(result["students"], 500)
        self.assertEqual(result["teachers"], 19)
        self.assertEqual(result["families"], 300)
        self.assertEqual(Student.objects.filter(is_demo=True).count(), 0)
        self.assertEqual(Teacher.objects.filter(is_demo=True).count(), 0)
        self.assertEqual(TeacherDocument.objects.count(), 38)
        self.assertGreater(Receipt.objects.count(), 0)
        self.assertEqual(Family.objects.count(), 300)
        self.assertEqual(Grade.objects.count(), 12)
        self.assertEqual(Section.objects.count(), 25)
        self.assertEqual(StudentMark.objects.count(), 52640)
        self.assertEqual(IssuedDocument.objects.count(), 819)
        self.assertEqual(Receipt.objects.count() + FeePayment.objects.count(), 800)
        self.assertEqual(result["schedule_verified"], True)
        self.assertEqual(Subject.objects.filter(academic_year__is_current=True).count(), 159)
        self.assertEqual(TeacherAssignment.objects.count(), 329)
        self.assertEqual(TimeSlot.objects.filter(generated_for_smart_schedule=False).count(), 8)
        self.assertEqual(SchoolDayEvent.objects.filter(event_type="break").count(), 3)
        self.assertFalse(SchoolDayEvent.objects.filter(event_type="break", start_time__isnull=True).exists())
        self.assertEqual(sorted(item.sections.count() for item in SchoolDayEvent.objects.filter(event_type="break")), [8, 8, 9])
        self.assertEqual(TimetableEntry.objects.count(), 475)
        self.assertEqual(result["teacher_weekly_load"], 25)
        self.assertEqual(result["teacher_daily_target"], 5)
        self.assertFalse(Teacher.objects.exclude(weekly_teaching_load=25).exists())
        self.assertFalse(Teacher.objects.exclude(free_period_policy="daily").exists())
        self.assertFalse(Teacher.objects.exclude(daily_free_periods=1).exists())
        for teacher in Teacher.objects.all():
            self.assertEqual(
                sum(assignment.subject.weekly_periods for assignment in teacher.assignments.select_related("subject")),
                25,
            )
        self.assertEqual(AttendanceRegister.objects.count(), 250)
        self.assertFalse(Attendance.objects.exclude(status__in={"absent", "departed"}).exists())
        self.assertEqual(TeacherAbsence.objects.count(), 25)
        self.assertTrue(TeacherMonthlyEvaluation.objects.exists())
        self.assertEqual(MonthlyServiceEvaluation.objects.count(), 319)
        self.assertFalse(Exam.objects.filter(teacher_assignment__isnull=True).exists())
        relations = set(FamilyStudent.objects.values_list("relation", flat=True))
        self.assertTrue({"والد", "والدة", "عم ووصي", "الأخ الأكبر", "جد وولي"}.issubset(relations))
        mixed_family = Family.objects.filter(children__relation="والد").filter(children__relation="عم ووصي").distinct()
        self.assertTrue(mixed_family.exists())
        child_counts = sorted(
            Family.objects.annotate(total=models.Count("children")).values_list("total", flat=True)
        )
        self.assertEqual(child_counts.count(1), 150)
        self.assertEqual(child_counts.count(2), 100)
        self.assertEqual(child_counts.count(3), 50)
        self.assertEqual(Student.objects.exclude(national_id="").count(), 500)
        self.assertEqual(Teacher.objects.exclude(national_id="").count(), 19)
        self.assertEqual(Student.objects.values("full_name").distinct().count(), 500)
        self.assertEqual(Teacher.objects.values("full_name").distinct().count(), 19)
        self.assertEqual(Family.objects.values("guardian_name").distinct().count(), 300)
        self.assertFalse(Student.objects.filter(student_number="OLD-WITNESS").exists())

        permission_rule = RolePermissionRule.objects.create(
            role_code="teacher", feature="attendance", can_view=True, is_active=True,
        )
        teacher = Teacher.objects.order_by("pk").first()
        academic_year = AcademicYear.objects.get(is_current=True)
        TeacherPerformanceSnapshot.objects.create(
            teacher=teacher, academic_year=academic_year,
            period=date.today().replace(day=1), score=80,
            evidence_coverage=100, rank=1, is_closed=True,
        )

        reset_all_operational_data(keep_user=self.user)
        self.assertFalse(Student.objects.exists())
        self.assertFalse(Teacher.objects.exists())
        self.assertFalse(Family.objects.exists())
        self.assertTrue(User.objects.filter(pk=self.user.pk, is_superuser=True).exists())
        self.assertTrue(RolePermissionRule.objects.filter(pk=permission_rule.pk).exists())
        self.assertFalse(TeacherPerformanceSnapshot.objects.exists())
        self.assertFalse(AttendanceRegister.objects.exists())
        self.assertFalse(MonthlyServiceEvaluation.objects.exists())


class SystemDataCenterActionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("data_action_owner", "actions@example.test", "x")
        School.objects.create(name="مدرسة إجراءات البيانات", is_active=True)
        self.client.force_login(self.user)

    def test_legacy_seed_action_is_blocked_and_redirected_to_safe_workflow(self):
        from unittest.mock import patch

        with patch("core.system_data.seed_system_data") as seed_service:
            response = self.client.post(
                reverse("core:system_settings"),
                {"action": "seed_system"},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "تم إيقاف التصفير المباشر")
        self.assertContains(response, "تهيئة التشغيل الفعلي")
        seed_service.assert_not_called()

    def test_legacy_reset_action_is_blocked_without_calling_service(self):
        from unittest.mock import patch

        with patch("core.system_data.reset_all_operational_data") as reset_service:
            response = self.client.post(
                reverse("core:system_settings"),
                {"action": "reset_all", "confirmation": "تصفير"},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "تم إيقاف التصفير المباشر")
        reset_service.assert_not_called()


class DataIntegrityCenterTests(TestCase):
    def setUp(self):
        from academics.models import Grade, Section, Subject
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
        Student.objects.create(student_number="INT-2", national_id="UNIQUE-NID-2", full_name="طالب ثان", grade="الأول", status="archived", is_active=False)

    def _create_fixable_conflicts(self):
        from academics.models import Enrollment, Subject
        from students.models import Student
        from accounting.models import FeeCategory, StudentInvoice, StudentPayment
        from exams.models import Exam
        from teachers.models import Teacher

        Enrollment.objects.create(student=self.student, academic_year=self.year, grade=self.grade, section=self.section, status="active")
        # Simulate legacy/stale denormalized display fields after the canonical enrollment exists.
        Student.objects.filter(pk=self.student.pk).update(grade="صف خاطئ", section="شعبة خاطئة")
        self.student.refresh_from_db()
        teacher_user = User.objects.create_user("mismatch_teacher", password="x", is_active=True)
        teacher = Teacher.objects.create(user=teacher_user, employee_number="INT-T-1", full_name="معلم متوقف", school=self.school, branch=self.branch, is_active=False)
        category = FeeCategory.objects.create(name="اختبار السلامة", amount=100)
        invoice = StudentInvoice.objects.create(student=self.student, academic_year=self.year, fee_category=category, amount=100, due_date=date.today())
        StudentPayment.objects.create(invoice=invoice, amount=50)
        StudentInvoice.objects.filter(pk=invoice.pk).update(status="open", paid=False)
        subject = Subject.objects.create(academic_year=self.year, name="رياضيات", grade=self.grade)
        exam = Exam.objects.create(name="امتحان منشور", exam_type="first", academic_year=self.year, semester=self.year.semesters.get(code="first"), grade=self.grade, subject=subject, status="published", is_locked=False)
        return teacher, teacher_user, invoice, exam

    def test_scan_detects_but_does_not_change_data(self):
        from core.data_integrity import run_integrity_audit
        from academics.models import Enrollment

        self._create_fixable_conflicts()
        run = run_integrity_audit(fix_safe=False, user=self.user)
        codes = set(run.issues.values_list("code", flat=True))
        self.assertNotIn("STUDENT_DUPLICATE_NATIONAL_ID", codes)
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
        self.assertEqual(Student.objects.filter(national_id="DUPNID").count(), 1)

    def test_integrity_center_is_visible_to_superuser(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:integrity_center"))
        self.assertContains(response, "فحص وإصلاح آمن")
