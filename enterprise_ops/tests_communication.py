from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from announcements.models import Announcement
from core.models import Branch, School
from parent_portal.models import Family
from teachers.models import Teacher

from .models import BroadcastMessage, FeedbackTicket, Notification


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

    def test_feedback_requires_two_separate_ratings_and_notifies_management(self):
        self.client.force_login(self.teacher_user)
        url = reverse("enterprise_ops:feedback_create")
        incomplete = self.client.post(url, {
            "kind": "complaint",
            "title": "شكوى",
            "message": "تفاصيل الشكوى",
            "teaching_quality_rating": "4",
        })
        self.assertEqual(incomplete.status_code, 200)
        self.assertEqual(FeedbackTicket.objects.count(), 0)

        complete = self.client.post(url, {
            "kind": "complaint",
            "title": "شكوى",
            "message": "تفاصيل الشكوى",
            "teaching_quality_rating": "4",
            "electronic_services_rating": "3",
        })
        self.assertEqual(complete.status_code, 302)
        item = FeedbackTicket.objects.get()
        self.assertEqual(item.sender, self.teacher_user)
        self.assertEqual(item.teaching_quality_rating, 4)
        self.assertEqual(item.electronic_services_rating, 3)
        self.assertTrue(Notification.objects.filter(recipient=self.manager, event_key__startswith=f"feedback:{item.pk}:").exists())

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

    def test_reports_audit_and_announcement_management_are_available(self):
        for user in (self.teacher_user, self.parent_user):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("enterprise_ops:report_center")).status_code, 200)
            self.assertEqual(self.client.get(reverse("enterprise_ops:audit_log")).status_code, 200)

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
