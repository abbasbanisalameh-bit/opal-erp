from datetime import date, time
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from academics.models import Grade, Section, Subject
from core.models import AcademicYear, Branch, School
from students.models import Student
from teachers.models import Teacher
from timetable.models import TimeSlot, TimetableEntry


class CanonicalOperationFlowTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user("flow_manager", password="pass", is_staff=True)
        self.school = School.objects.create(name="مدرسة المسارات", is_active=True)
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)

    def test_operations_center_lists_canonical_actions_and_audit(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("core:operations_center"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "دليل العمليات الموحد")
        self.assertContains(response, "تسجيل طالب")
        self.assertContains(response, "تسديد الرسوم")
        self.assertContains(response, "الخطة الدراسية")
        self.assertContains(response, "فئات الرسوم")
        self.assertContains(response, "الأقساط")
        self.assertContains(response, "فحص تكامل الوحدات")
        self.assertNotContains(response, reverse("admissions:direct_registration"))
        self.assertContains(response, "من بوابة الدور")

    def test_topbar_search_is_backed_by_role_aware_catalog(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("dashboard:home"))
        self.assertContains(response, 'id="opal-global-operation-search"')
        self.assertContains(response, 'id="opal-operation-catalog"')
        self.assertContains(response, "المكان الرسمي لهذه العملية")

    def test_student_search_preserves_status_filter(self):
        Student.objects.create(student_number="FLOW-A", full_name="أحمد المسار", status="active", is_active=True)
        Student.objects.create(student_number="FLOW-B", full_name="أحمد المسار المؤرشف", status="archived", is_active=False)
        self.client.force_login(self.manager)
        response = self.client.get(reverse("students:student_list"), {"q": "أحمد", "status": "active"})
        self.assertContains(response, "FLOW-A")
        self.assertNotContains(response, "FLOW-B")

    def test_executive_teacher_count_uses_teacher_records_not_all_staff(self):
        from dashboard.views import _executive_snapshot

        User.objects.create_user("another_staff", password="pass", is_staff=True)
        Teacher.objects.create(
            employee_number="FLOW-T-1",
            full_name="معلم المسار",
            school=self.school,
            branch=self.branch,
            is_active=True,
        )
        self.assertEqual(_executive_snapshot()["teachers_count"], 1)

    def test_finance_entry_is_not_available_to_ordinary_authenticated_user(self):
        ordinary = User.objects.create_user("ordinary_flow_user", password="pass")
        self.client.force_login(ordinary)
        response = self.client.get(reverse("admissions:fee_payment_create"))
        self.assertEqual(response.status_code, 302)

    def test_existing_school_fee_features_remain_visible_at_one_canonical_route(self):
        self.client.force_login(self.manager)
        for route, text in (
            ("accounting:fee_category_list", "فئات الرسوم"),
            ("accounting:invoice_list", "رسوم الطلاب"),
            ("accounting:installment_list", "الأقساط"),
            ("accounting:discount_list", "طلبات الخصم"),
            ("academics:subject_list", "المواد والخطة الدراسية"),
        ):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200, route)
            self.assertContains(response, text)

    def test_document_archive_is_management_only(self):
        ordinary = User.objects.create_user("ordinary_document_user", password="pass")
        self.client.force_login(ordinary)
        response = self.client.get(reverse("documents:document_list"))
        self.assertEqual(response.status_code, 302)

    def test_teacher_detail_uses_the_real_timetable_relation(self):
        year = AcademicYear.objects.create(
            school=self.school, name="2026/2027", start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30), is_current=True,
        )
        grade = Grade.objects.create(school=self.school, name="الصف الرابع", order=4)
        section = Section.objects.create(
            academic_year=year, branch=self.branch, grade=grade, name="أ"
        )
        subject = Subject.objects.create(academic_year=year, grade=grade, name="الرياضيات", code="MATH-4")
        teacher = Teacher.objects.create(
            employee_number="FLOW-T-TABLE", full_name="معلم الجدول",
            school=self.school, branch=self.branch,
        )
        slot = TimeSlot.objects.create(
            name="الحصة الأولى", start_time=time(8, 0), end_time=time(8, 45), order=1
        )
        TimetableEntry.objects.create(
            academic_year=year, section=section, subject=subject, teacher=teacher,
            day="sunday", time_slot=slot,
        )
        self.client.force_login(self.manager)
        response = self.client.get(reverse("teachers:teacher_detail", args=[teacher.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "الرياضيات")
        self.assertContains(response, "الحصة الأولى")

    def test_operation_audit_command_reports_read_only_issues(self):
        output = StringIO()
        call_command("audit_operation_flow", "--allow-issues", stdout=output)
        report = output.getvalue()
        self.assertIn("فحص تكامل سير العمليات", report)
        self.assertIn("CURRENT_YEAR", report)
