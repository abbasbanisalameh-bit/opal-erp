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
        self.assertContains(response, "إدخال البيانات التجريبية")

    def test_seed_is_comprehensive_and_reset_removes_all_operational_data(self):
        from collections import Counter
        from core.system_data import reset_all_operational_data, seed_system_data
        from students.models import Student
        from teachers.models import Teacher, TeacherDocument, TeacherPerformanceSnapshot
        from accounting.models import Receipt
        from parent_portal.models import Family, FamilyStudent, TeacherMonthlyEvaluation
        from academics.models import Grade, Section, Subject
        from teachers.models import TeacherAssignment
        from timetable.models import SchoolDayEvent, TimeSlot, TimetableEntry
        from admissions.models import FeePayment, FeePaymentAllocation
        from attendance_v2.models import AttendanceRegister
        from enterprise_ops.models import MonthlyServiceEvaluation, RolePermissionRule
        from learning_platform.models import (
            LearningAccount, LearningCourse, LearningLesson, LearningStudentProfile,
            LearningSubscriptionCard, LearningTeacherProfile,
        )

        Student.objects.create(student_number="OLD-WITNESS", full_name="سجل قديم", grade="الأول")
        result = seed_system_data(user=self.user)
        self.assertEqual(result["students"], 500)
        self.assertEqual(result["teachers"], 30)
        self.assertEqual(result["families"], 200)
        self.assertEqual(result["sections"], 30)
        self.assertEqual(result["teacher_weekly_load"], 30)
        self.assertEqual(result["teacher_daily_target"], 6)
        self.assertTrue(result["schedule_verified"])
        self.assertEqual(result["learning_accounts"], 530)
        self.assertEqual(result["learning_courses"], 330)
        self.assertEqual(result["learning_lessons"], 660)

        self.assertEqual(Student.objects.count(), 500)
        self.assertEqual(Teacher.objects.count(), 30)
        self.assertEqual(TeacherDocument.objects.count(), 60)
        self.assertEqual(Family.objects.count(), 200)
        self.assertEqual(Grade.objects.count(), 12)
        self.assertEqual(Section.objects.count(), 30)
        self.assertEqual(Subject.objects.filter(academic_year__is_current=True).count(), 132)
        self.assertEqual(TeacherAssignment.objects.count(), 330)
        self.assertEqual(TimeSlot.objects.filter(generated_for_smart_schedule=False).count(), 8)
        self.assertEqual(TimetableEntry.objects.count(), 900)

        breaks = list(SchoolDayEvent.objects.filter(event_type="break").prefetch_related("sections"))
        self.assertEqual(len(breaks), 3)
        self.assertTrue(all(item.effective_duration_minutes == 20 for item in breaks))
        self.assertEqual(sorted(item.sections.count() for item in breaks), [8, 10, 12])
        section_breaks = Counter()
        for item in breaks:
            for section_id in item.sections.values_list("pk", flat=True):
                section_breaks[section_id] += 1
        self.assertEqual(len(section_breaks), 30)
        self.assertEqual(set(section_breaks.values()), {1})

        self.assertFalse(Teacher.objects.exclude(weekly_teaching_load=30).exists())
        self.assertFalse(Teacher.objects.exclude(free_period_policy="daily").exists())
        self.assertFalse(Teacher.objects.filter(daily_free_periods__lt=1).exists())
        days = ("sunday", "monday", "tuesday", "wednesday", "thursday")
        for teacher in Teacher.objects.all():
            self.assertEqual(
                sum(assignment.subject.weekly_periods for assignment in teacher.assignments.select_related("subject")),
                30,
            )
            for day in days:
                self.assertEqual(TimetableEntry.objects.filter(teacher=teacher, day=day).count(), 6)

        homeroom_ids = list(Section.objects.order_by("pk").values_list("homeroom_teacher_id", flat=True))
        self.assertNotIn(None, homeroom_ids)
        self.assertEqual(len(set(homeroom_ids)), 30)

        family_sizes = Counter(
            FamilyStudent.objects.filter(is_active=True).values_list("family_id", flat=True)
        )
        self.assertEqual(Counter(family_sizes.values()), Counter({1: 50, 2: 50, 3: 50, 4: 50}))
        self.assertEqual(set(FamilyStudent.objects.values_list("relation", flat=True)), {"والد"})
        for link in FamilyStudent.objects.select_related("family", "student"):
            guardian = link.family.guardian_name.split()
            child = link.student.full_name.split()
            self.assertGreaterEqual(len(guardian), 4)
            self.assertGreaterEqual(len(child), 4)
            self.assertEqual(child[1], guardian[0])
            self.assertEqual(child[2], guardian[1])
            self.assertEqual(child[-1], guardian[-1])
        self.assertEqual(Student.objects.values("full_name").distinct().count(), 500)
        self.assertEqual(Family.objects.values("guardian_name").distinct().count(), 200)

        self.assertEqual(FeePayment.objects.filter(scope="all_siblings", is_deleted=False).count(), 200)
        self.assertEqual(FeePayment.objects.values("guardian_name").distinct().count(), 200)
        self.assertGreater(FeePaymentAllocation.objects.count(), 0)
        self.assertGreater(Receipt.objects.count(), 0)

        self.assertEqual(LearningAccount.objects.filter(is_school_managed=True).count(), 530)
        self.assertEqual(LearningStudentProfile.objects.count(), 500)
        self.assertEqual(LearningTeacherProfile.objects.count(), 30)
        self.assertEqual(LearningCourse.objects.filter(academic_section__isnull=False, status="published").count(), 330)
        self.assertEqual(LearningLesson.objects.filter(course__academic_section__isnull=False, is_published=True).count(), 660)
        self.assertEqual(LearningSubscriptionCard.objects.count(), 500)
        self.assertEqual(LearningSubscriptionCard.objects.filter(status="redeemed").count(), 250)
        self.assertEqual(LearningSubscriptionCard.objects.filter(status="available").count(), 250)
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
        self.assertFalse(LearningStudentProfile.objects.exists())
        self.assertFalse(LearningTeacherProfile.objects.exists())
        self.assertFalse(LearningCourse.objects.exists())
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

    def test_superuser_can_launch_integrated_seed_from_system_settings(self):
        from unittest.mock import patch

        result = {"students": 500, "families": 200, "teachers": 30}
        with patch("core.system_data.seed_system_data", return_value=result) as seed_service:
            response = self.client.post(
                reverse("core:system_settings"),
                {"action": "seed_system"},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "500 طالب")
        self.assertContains(response, "200 ولي أمر")
        self.assertContains(response, "30 معلم")
        seed_service.assert_called_once_with(user=self.user)

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
