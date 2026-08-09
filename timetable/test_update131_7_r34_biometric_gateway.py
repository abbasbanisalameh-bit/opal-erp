import json
from datetime import date, datetime, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from academics.models import Grade, Section, Subject
from core.models import AcademicYear, Branch, School
from teachers.models import Teacher

from .biometric_services import apply_daily_summary, issue_device_token, rebuild_daily_summaries
from .models import BiometricDevice, TeacherAbsence, TeacherBiometricIdentity, TeacherBiometricPunch, TimeSlot, TimetableEntry


class R34BiometricGatewayTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة بصمة R34")
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.user = User.objects.create_superuser("bio-admin", "bio@example.com", "Secret@123")
        self.teacher = Teacher.objects.create(employee_number="BIO-T1", full_name="معلم بصمة", school=self.school, branch=self.branch)
        self.year = AcademicYear.objects.create(
            school=self.school, name="2026/2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 30),
            midyear_break_start=date(2027, 1, 15), midyear_break_end=date(2027, 1, 31), is_current=True,
        )
        grade = Grade.objects.create(school=self.school, name="الصف الأول", order=1)
        section = Section.objects.create(academic_year=self.year, branch=self.branch, grade=grade, name="أ", capacity=30)
        subject = Subject.objects.create(name="رياضيات", academic_year=self.year, grade=grade, weekly_periods=5)
        first = TimeSlot.objects.create(name="الأولى", start_time=time(8, 0), end_time=time(9, 0), order=1)
        last = TimeSlot.objects.create(name="السادسة", start_time=time(12, 0), end_time=time(13, 0), order=6)
        TimetableEntry.objects.create(academic_year=self.year, section=section, subject=subject, teacher=self.teacher, day="sunday", time_slot=first)
        TimetableEntry.objects.create(academic_year=self.year, section=section, subject=subject, teacher=self.teacher, day="sunday", time_slot=last)
        self.device = BiometricDevice.objects.create(school=self.school, branch=self.branch, name="بوابة المدرسة", device_code="R34-DEVICE", vendor="generic")
        self.raw_token = issue_device_token(self.device)
        TeacherBiometricIdentity.objects.create(device=self.device, teacher=self.teacher, device_user_id="17")

    def _push(self, events):
        return self.client.post(
            reverse("timetable:biometric_punch_ingest"),
            data=json.dumps({"events": events}),
            content_type="application/json",
            HTTP_X_OPAL_BIOMETRIC_TOKEN=self.raw_token,
        )

    def test_gateway_maps_punches_and_is_idempotent(self):
        event = {"user_id": "17", "timestamp": "2026-09-06T08:20:00+03:00", "direction": "in", "event_uid": "event-1"}
        first = self._push([event])
        second = self._push([event])
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["data"]["accepted"], 1)
        self.assertEqual(second.json()["data"]["duplicates"], 1)
        self.assertEqual(TeacherBiometricPunch.objects.count(), 1)
        self.assertEqual(TeacherBiometricPunch.objects.get().teacher_id, self.teacher.pk)

    def test_biometric_evidence_does_not_create_official_presence_automatically(self):
        self._push([
            {"user_id": "17", "timestamp": "2026-09-06T08:20:00+03:00", "direction": "in", "event_uid": "event-in"},
            {"user_id": "17", "timestamp": "2026-09-06T12:55:00+03:00", "direction": "out", "event_uid": "event-out"},
        ])
        summary = rebuild_daily_summaries(date(2026, 9, 6), school=self.school)[0]
        self.assertEqual(summary.derived_status, "late")
        self.assertFalse(TeacherAbsence.objects.filter(teacher=self.teacher, date=summary.date).exists())
        apply_daily_summary(summary, user=self.user)
        row = TeacherAbsence.objects.get(teacher=self.teacher, date=summary.date)
        self.assertEqual(row.attendance_status, "late")
        self.assertEqual(row.arrival_time, time(8, 20))
