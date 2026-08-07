from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from announcements.models import Announcement
from academics.models import Enrollment, Grade, Section, Subject
from core.models import AcademicYear, Branch, School
from parent_portal.models import Family, FamilyStudent
from students.models import Student
from teachers.models import Teacher, TeacherAssignment

from .evaluation_services import monthly_evaluation_prompt_for_user, submit_monthly_evaluations
from .models import BroadcastMessage, FeedbackTicket, MonthlyServiceEvaluation, Notification
from parent_portal.models import TeacherMonthlyEvaluation


class CommunicationCenterTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة التواصل", is_active=True)
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.manager = User.objects.create_user("communication_manager", is_staff=True)
        self.teacher_user = User.objects.create_user("communication_teacher")
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            school=self.school,
            branch=self.branch,
            employee_number="TC-1",
            full_name="معلم التواصل",
        )
        self.parent_user = User.objects.create_user("communication_parent")
        self.family = Family.objects.create(
            school=self.school,
            user=self.parent_user,
            guardian_name="ولي أمر التواصل",
            phone="0790000001",
            family_code="FC-1",
        )

    def test_feedback_is_a_simple_unfiltered_message_flow_and_uses_dashboard_badge(self):
        self.client.force_login(self.teacher_user)
        url = reverse("enterprise_ops:feedback_list")
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "إرسال شكوى أو اقتراح")
        self.assertNotContains(page, 'name="q"')
        self.assertNotContains(page, "تقييم جودة التدريس")

        response = self.client.post(url, {
            "kind": "complaint",
            "message": "تفاصيل الشكوى",
        })
        self.assertEqual(response.status_code, 302)
        item = FeedbackTicket.objects.get()
        self.assertEqual(item.sender, self.teacher_user)
        self.assertEqual(item.message, "تفاصيل الشكوى")
        self.assertIsNone(item.teaching_quality_rating)
        self.assertIsNone(item.electronic_services_rating)
        self.assertFalse(Notification.objects.filter(recipient=self.manager, event_key__startswith=f"feedback:{item.pk}:").exists())
        self.client.force_login(self.manager)
        dashboard = self.client.get(reverse("dashboard:home"))
        self.assertEqual(dashboard.context["new_feedback_count"], 1)
        self.assertRedirects(self.client.get(reverse("enterprise_ops:feedback_create")), url)

    def test_teacher_monthly_evaluation_is_separate_and_required_once_per_month(self):
        today = date(2026, 7, 26)
        prompt = monthly_evaluation_prompt_for_user(self.teacher_user, today=today)
        self.assertEqual(prompt["audience"], "teacher")
        self.assertEqual(prompt["stage"], "teacher_services")
        self.assertEqual(prompt["teacher_rows"], [])

        self.client.force_login(self.teacher_user)
        response = self.client.post(reverse("enterprise_ops:submit_monthly_evaluations"), {"service_rating": "5"})
        self.assertEqual(response.status_code, 200)
        rating = MonthlyServiceEvaluation.objects.get(user=self.teacher_user)
        self.assertEqual(rating.electronic_services_rating, 5)

    def test_parent_has_the_same_unfiltered_page_and_monthly_modal(self):
        self.client.force_login(self.parent_user)
        response = self.client.get(reverse("enterprise_ops:feedback_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "إرسال شكوى أو اقتراح")
        self.assertNotContains(response, 'name="q"')
        self.assertContains(response, "opal-monthly-eval-overlay")
        self.assertContains(response, "},5000)")

    def test_parent_completes_teacher_evaluation_before_general_school_evaluation(self):
        year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_current=True,
        )
        grade = Grade.objects.create(school=self.school, name="السابع", order=7)
        section = Section.objects.create(
            academic_year=year,
            branch=self.branch,
            grade=grade,
            name="أ",
        )
        subject = Subject.objects.create(academic_year=year, grade=grade, name="رياضيات")
        TeacherAssignment.objects.create(
            teacher=self.teacher,
            academic_year=year,
            section=section,
            subject=subject,
        )
        student = Student.objects.create(student_number="COMM-1", full_name="طالب التواصل")
        Enrollment.objects.create(
            student=student,
            academic_year=year,
            grade=grade,
            section=section,
            status="active",
        )
        FamilyStudent.objects.create(family=self.family, student=student)
        today = date(2026, 7, 26)

        teacher_prompt = monthly_evaluation_prompt_for_user(self.parent_user, today=today)
        self.assertEqual(teacher_prompt["stage"], "parent_teacher")
        submit_monthly_evaluations(
            self.parent_user,
            {f"rating_{self.teacher.pk}": "5"},
            today=today,
        )
        teaching_prompt = monthly_evaluation_prompt_for_user(self.parent_user, today=today)
        self.assertEqual(teaching_prompt["stage"], "parent_teaching_quality")
        submit_monthly_evaluations(
            self.parent_user,
            {"teaching_rating": "4"},
            today=today,
        )
        electronic_prompt = monthly_evaluation_prompt_for_user(self.parent_user, today=today)
        self.assertEqual(electronic_prompt["stage"], "parent_electronic_services")
        submit_monthly_evaluations(
            self.parent_user,
            {"service_rating": "3"},
            today=today,
        )
        self.assertIsNone(monthly_evaluation_prompt_for_user(self.parent_user, today=today))
        rating = MonthlyServiceEvaluation.objects.get(user=self.parent_user, period=today.replace(day=1))
        self.assertEqual(rating.teaching_quality_rating, 4)
        self.assertEqual(rating.electronic_services_rating, 3)

    def test_circular_and_direct_teacher_alert_create_audible_notifications(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse("enterprise_ops:broadcast_create"), {
            "message_type": "circular",
            "audience": "all",
            "specific_teacher": "",
            "title": "تعميم عام",
            "message": "نص التعميم",
        })
        self.assertEqual(response.status_code, 302)
        circular = BroadcastMessage.objects.get(title="تعميم عام")
        self.assertEqual(circular.recipients_count, 3)
        self.assertTrue(Notification.objects.filter(recipient=self.teacher_user, sound_enabled=True).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.parent_user, sound_enabled=True).exists())

        response = self.client.post(reverse("enterprise_ops:broadcast_create"), {
            "message_type": "teacher_alert",
            "audience": "parents",  # clean() must force teachers/direct recipient.
            "specific_teacher": self.teacher.pk,
            "title": "تنبيه مباشر",
            "message": "راجع الجدول",
        })
        self.assertEqual(response.status_code, 302)
        direct = BroadcastMessage.objects.get(title="تنبيه مباشر")
        self.assertEqual(direct.audience, "teachers")
        self.assertEqual(direct.recipients_count, 1)
        self.assertTrue(Notification.objects.filter(recipient=self.teacher_user, title="تنبيه مباشر").exists())
        self.assertFalse(Notification.objects.filter(recipient=self.parent_user, title="تنبيه مباشر").exists())


    def test_management_communication_dashboard_shows_satisfaction_summary(self):
        TeacherMonthlyEvaluation.objects.create(
            family=self.family,
            teacher=self.teacher,
            period=date.today().replace(day=1),
            teaching_quality_rating=5,
        )
        MonthlyServiceEvaluation.objects.create(
            user=self.parent_user,
            school=self.school,
            period=date.today().replace(day=1),
            teaching_quality_rating=5,
            electronic_services_rating=4,
        )
        self.client.force_login(self.manager)
        response = self.client.get(reverse("enterprise_ops:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('dashboard:home')}#opal-communication-actions")
        dashboard = self.client.get(reverse("dashboard:home"))
        self.assertContains(dashboard, "مؤشرات رضا المستخدمين")
        self.assertEqual(dashboard.context["overall_rating_average"], 4.5)
        # School satisfaction and per-teacher evaluation are two independent
        # canonical datasets; do not combine them into one participation count.
        self.assertEqual(dashboard.context["feedback_total"], 1)
        self.assertEqual(dashboard.context["teacher_evaluation_total"], 1)
        self.assertEqual(dashboard.context["feedback_parent_responses"], 1)
        self.assertContains(dashboard, "opal-overview-meter")

    def test_reports_audit_and_announcement_management_are_available(self):
        for user in (self.teacher_user, self.parent_user):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("enterprise_ops:report_center")).status_code, 302)
            self.assertEqual(self.client.get(reverse("enterprise_ops:audit_log")).status_code, 302)

        self.client.force_login(self.manager)
        response = self.client.post(reverse("announcements:create"), {
            "title": "إعلان إداري",
            "message": "رسالة الإعلان",
            "announcement_type": "info",
            "speed_seconds": 20,
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        announcement = Announcement.objects.get(title="إعلان إداري")
        self.client.post(reverse("announcements:toggle", args=[announcement.pk]))
        announcement.refresh_from_db()
        self.assertFalse(announcement.is_active)
        self.client.post(reverse("announcements:delete", args=[announcement.pk]))
        self.assertFalse(Announcement.objects.filter(pk=announcement.pk).exists())
