import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from students.models import Student

from .models import (
    LearningAccount,
    LearningAIDraft,
    LearningAIInteraction,
    LearningAISettings,
    LearningAssessment,
    LearningAuditEvent,
    LearningCertificate,
    LearningCourse,
    LearningEnrollment,
    LearningLesson,
    LearningLessonProgress,
    LearningNotification,
    LearningPasswordResetRequest,
    LearningEmailVerificationRequest,
    LearningAPIToken,
    LearningPaymentEvent,
    LearningPaymentOrder,
    LearningRateLimitBucket,
    LearningSubscriptionPlan,
    LearningQuestion,
    LearningSubject,
    LearningSubmission,
    LearningSubscriptionCard,
)
from .ai_services import run_grounded_assistance
from .services import grade_assignment, submit_assignment
from .payment_services import create_payment_order, mark_order_paid, process_payment_webhook
from .session_auth import LEARNING_AUTH_VERSION_KEY, LEARNING_SESSION_KEY
from .security_services import issue_api_token


class LearningPlatformIntegrationTests(TestCase):
    password = "Opal-Learning-2026!secure"

    def create_account(self, *, email="learner@example.com", role=LearningAccount.Role.LEARNER):
        account = LearningAccount(email=email, full_name="متعلم أوبال", role=role)
        account.set_password(self.password)
        account.save()
        return account

    def learning_login(self, account):
        session = self.client.session
        session[LEARNING_SESSION_KEY] = account.pk
        session[LEARNING_AUTH_VERSION_KEY] = account.auth_version
        session.save()

    def test_public_pages_use_learning_shell_without_erp_chrome(self):
        response = self.client.get(reverse("learning_platform:landing"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "learning_platform/base.html")
        self.assertContains(response, "منصة أوبال التعليمية")
        self.assertNotContains(response, "OPAL ERP")
        self.assertNotContains(response, "opal-sidebar")
        self.assertNotContains(response, "css/opal_erp.css")

    def test_registration_creates_only_an_independent_learning_account(self):
        school_students_before = Student.objects.count()
        erp_users_before = User.objects.count()
        response = self.client.post(
            reverse("learning_platform:register"),
            {
                "full_name": "ليان أحمد",
                "email": "Layan@Example.com",
                "phone": "0790000000",
                "password1": self.password,
                "password2": self.password,
                "accept_terms": "on",
            },
        )
        self.assertRedirects(response, reverse("learning_platform:dashboard"))
        account = LearningAccount.objects.get(email="layan@example.com")
        self.assertTrue(account.check_password(self.password))
        self.assertEqual(self.client.session[LEARNING_SESSION_KEY], account.pk)
        self.assertEqual(Student.objects.count(), school_students_before)
        self.assertEqual(User.objects.count(), erp_users_before)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(
            LearningAuditEvent.objects.filter(
                account=account,
                action=LearningAuditEvent.Action.REGISTERED,
            ).exists()
        )

    def test_erp_manager_opens_platform_management_without_learning_account(self):
        manager = User.objects.create_user(
            username="erp-platform-manager",
            password="Manager-2026!secure",
            is_staff=True,
        )
        self.client.force_login(manager)

        response = self.client.get(reverse("learning_platform:manager_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "learning_platform/manager_dashboard.html")
        self.assertContains(response, "إدارة منصة أوبال التعليمية")
        self.assertContains(response, "العودة إلى OPAL ERP")
        self.assertNotIn(LEARNING_SESSION_KEY, self.client.session)
        self.assertEqual(LearningAccount.objects.count(), 0)

    def test_manager_gateway_uses_erp_login_and_rejects_non_management_user(self):
        response = self.client.get(reverse("learning_platform:manager_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))
        self.assertNotIn(reverse("learning_platform:login"), response.url)

        regular_user = User.objects.create_user("erp-regular", password="pass")
        self.client.force_login(regular_user)
        response = self.client.get(reverse("learning_platform:manager_dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_independent_manager_account_cannot_use_learning_login(self):
        account = self.create_account(
            email="legacy-manager@example.com",
            role=LearningAccount.Role.MANAGER,
        )
        response = self.client.post(
            reverse("learning_platform:login"),
            {"email": account.email, "password": self.password},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "مدير المنصة يدخل من حساب OPAL ERP")
        self.assertNotIn(LEARNING_SESSION_KEY, self.client.session)

    def test_learning_login_is_separate_from_erp_authentication(self):
        erp_user = User.objects.create_user(username="erp-manager", password="Manager-2026!secure")
        account = self.create_account()
        self.client.force_login(erp_user)

        response = self.client.post(
            reverse("learning_platform:login"),
            {"email": account.email, "password": self.password},
        )

        self.assertRedirects(response, reverse("learning_platform:dashboard"))
        session = self.client.session
        self.assertEqual(int(session["_auth_user_id"]), erp_user.pk)
        self.assertEqual(session[LEARNING_SESSION_KEY], account.pk)

    def test_learning_logout_does_not_log_out_the_erp_user(self):
        erp_user = User.objects.create_user(username="erp-owner", password="Owner-2026!secure")
        account = self.create_account()
        self.client.force_login(erp_user)
        self.learning_login(account)

        response = self.client.post(reverse("learning_platform:logout"))

        self.assertRedirects(response, reverse("learning_platform:landing"))
        session = self.client.session
        self.assertEqual(int(session["_auth_user_id"]), erp_user.pk)
        self.assertNotIn(LEARNING_SESSION_KEY, session)

    def test_private_learning_page_redirects_to_learning_login_only(self):
        response = self.client.get(reverse("learning_platform:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("learning_platform:login")))
        self.assertNotIn(reverse("login"), response.url)

    def test_learning_errors_keep_the_learning_identity(self):
        response = self.client.get("/learning/page-that-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "منصة أوبال التعليمية", status_code=404)
        self.assertNotContains(response, "OPAL ERP", status_code=404)

        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            reverse("learning_platform:login"),
            {"email": "nobody@example.com", "password": "invalid"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "انتهت صلاحية النموذج", status_code=403)
        self.assertNotContains(response, "OPAL ERP", status_code=403)

    def test_catalog_displays_published_courses_only(self):
        teacher = self.create_account(email="teacher@example.com", role=LearningAccount.Role.TEACHER)
        subject = LearningSubject.objects.create(name="الرياضيات", slug="math")
        LearningCourse.objects.create(
            subject=subject,
            teacher=teacher,
            title="الرياضيات بثقة",
            slug="math-confidence",
            status=LearningCourse.Status.PUBLISHED,
        )
        LearningCourse.objects.create(
            subject=subject,
            teacher=teacher,
            title="مسودة خاصة",
            slug="private-draft",
            status=LearningCourse.Status.DRAFT,
        )

        response = self.client.get(reverse("learning_platform:course_list"))

        self.assertContains(response, "الرياضيات بثقة")
        self.assertNotContains(response, "مسودة خاصة")

    def test_subscription_card_is_redeemed_once_for_learning_account(self):
        account = self.create_account()
        card = LearningSubscriptionCard.objects.create(
            code="opal-2026-card",
            duration=LearningSubscriptionCard.Duration.MONTHLY,
            grants_all_subjects=True,
        )
        self.learning_login(account)
        before = timezone.now()

        response = self.client.post(
            reverse("learning_platform:subscriptions"),
            {"code": "OPAL-2026-CARD"},
        )

        self.assertRedirects(response, reverse("learning_platform:subscriptions"))
        card.refresh_from_db()
        self.assertEqual(card.status, LearningSubscriptionCard.Status.REDEEMED)
        self.assertEqual(card.redeemed_by, account)
        self.assertGreaterEqual(card.expires_at, before + timedelta(days=29))
        self.assertLessEqual(card.expires_at, before + timedelta(days=31))
        self.assertTrue(card.is_current)

        second_client = self.client_class()
        session = second_client.session
        second_account = self.create_account(email="second@example.com")
        session[LEARNING_SESSION_KEY] = second_account.pk
        session.save()
        response = second_client.post(
            reverse("learning_platform:subscriptions"),
            {"code": "OPAL-2026-CARD"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "غير صالح أو مستخدم مسبقًا")


    def test_erp_manager_creates_teacher_with_independent_platform_login(self):
        manager = User.objects.create_user(
            username="content-manager",
            password="Manager-2026!secure",
            is_staff=True,
        )
        erp_users_before = User.objects.count()
        students_before = Student.objects.count()
        self.client.force_login(manager)

        response = self.client.post(
            reverse("learning_platform:manager_teacher_create"),
            {
                "full_name": "سارة محمود",
                "email": "Teacher@Example.com",
                "phone": "0791111111",
                "password1": self.password,
                "password2": self.password,
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("learning_platform:manager_account_list"))
        teacher = LearningAccount.objects.get(email="teacher@example.com")
        self.assertEqual(teacher.role, LearningAccount.Role.TEACHER)
        self.assertTrue(teacher.check_password(self.password))
        self.assertEqual(User.objects.count(), erp_users_before)
        self.assertEqual(Student.objects.count(), students_before)

        self.client.logout()
        response = self.client.post(
            reverse("learning_platform:login"),
            {"email": teacher.email, "password": self.password},
        )
        self.assertRedirects(response, reverse("learning_platform:dashboard"))
        self.assertEqual(self.client.session[LEARNING_SESSION_KEY], teacher.pk)

    def test_manager_account_toggle_is_post_only_and_blocks_login(self):
        manager = User.objects.create_user("manager-toggle", password="Manager-2026!secure", is_staff=True)
        teacher = self.create_account(email="toggle@example.com", role=LearningAccount.Role.TEACHER)
        self.client.force_login(manager)

        url = reverse("learning_platform:manager_account_toggle", args=[teacher.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)
        self.assertRedirects(response, reverse("learning_platform:manager_account_list"))
        teacher.refresh_from_db()
        self.assertFalse(teacher.is_active)

        self.client.logout()
        response = self.client.post(
            reverse("learning_platform:login"),
            {"email": teacher.email, "password": self.password},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "البريد الإلكتروني أو كلمة المرور غير صحيحة")

    def test_manager_content_workflow_requires_published_lesson_before_course_publish(self):
        manager = User.objects.create_user("content-owner", password="Manager-2026!secure", is_staff=True)
        teacher = self.create_account(email="course-teacher@example.com", role=LearningAccount.Role.TEACHER)
        self.client.force_login(manager)

        response = self.client.post(
            reverse("learning_platform:manager_subject_create"),
            {"name": "العلوم", "slug": "", "is_active": "on"},
        )
        self.assertRedirects(response, reverse("learning_platform:manager_subject_list"))
        subject = LearningSubject.objects.get(name="العلوم")
        self.assertTrue(subject.slug)

        response = self.client.post(
            reverse("learning_platform:manager_course_create"),
            {
                "subject": subject.pk,
                "teacher": teacher.pk,
                "title": "العلوم ببساطة",
                "slug": "",
                "summary": "دورة تأسيسية في العلوم.",
                "grade_label": "الصف السابع",
                "cover_color": "#7254d8",
            },
        )
        course = LearningCourse.objects.get(title="العلوم ببساطة")
        self.assertEqual(course.status, LearningCourse.Status.DRAFT)
        self.assertRedirects(
            response,
            reverse("learning_platform:manager_lesson_list", args=[course.pk]),
        )

        publish_url = reverse("learning_platform:manager_course_status", args=[course.pk])
        response = self.client.post(publish_url, {"action": "publish"}, follow=True)
        course.refresh_from_db()
        self.assertEqual(course.status, LearningCourse.Status.DRAFT)
        self.assertContains(response, "يجب نشر درس واحد على الأقل")

        response = self.client.post(
            reverse("learning_platform:manager_lesson_create", args=[course.pk]),
            {
                "title": "مقدمة في المادة",
                "slug": "",
                "content": "محتوى الدرس الأول.",
                "video_url": "",
                "duration_minutes": 15,
                "order": 1,
                "is_published": "on",
            },
        )
        self.assertRedirects(
            response,
            reverse("learning_platform:manager_lesson_list", args=[course.pk]),
        )
        lesson = LearningLesson.objects.get(course=course)
        self.assertTrue(lesson.is_published)

        response = self.client.post(publish_url, {"action": "publish"})
        self.assertRedirects(response, reverse("learning_platform:manager_course_list"))
        course.refresh_from_db()
        self.assertEqual(course.status, LearningCourse.Status.PUBLISHED)

        public_response = self.client.get(reverse("learning_platform:course_list"))
        self.assertContains(public_response, "العلوم ببساطة")
        detail_response = self.client.get(reverse("learning_platform:course_detail", args=[course.slug]))
        self.assertContains(detail_response, "مقدمة في المادة")

    def test_arabic_course_slug_renders_public_and_manager_surfaces(self):
        manager = User.objects.create_user(
            "arabic-slug-manager",
            password="Manager-2026!secure",
            is_staff=True,
        )
        teacher = self.create_account(
            email="arabic-slug-teacher@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        subject = LearningSubject.objects.create(name="اللغة الإنجليزية", slug="اللغة-الإنجليزية")
        course = LearningCourse.objects.create(
            subject=subject,
            teacher=teacher,
            title="كورس اللغة الإنجليزية للصف الثاني ثانوي",
            slug="كورس-اللغة-الانجليزية-للصف-الثاني-ثانوي",
            status=LearningCourse.Status.PUBLISHED,
        )
        LearningLesson.objects.create(
            course=course,
            title="الدرس الأول",
            slug="الدرس-الأول",
            order=1,
            is_published=True,
        )

        detail_url = reverse("learning_platform:course_detail", args=[course.slug])
        self.assertEqual(self.client.get(reverse("learning_platform:landing")).status_code, 200)
        self.assertEqual(self.client.get(reverse("learning_platform:course_list")).status_code, 200)
        self.assertEqual(self.client.get(detail_url).status_code, 200)

        self.client.force_login(manager)
        self.assertEqual(
            self.client.get(reverse("learning_platform:manager_course_list")).status_code,
            200,
        )

    def test_platform_management_pages_reject_non_management_erp_user(self):
        regular_user = User.objects.create_user("regular-content-user", password="pass")
        self.client.force_login(regular_user)
        protected_names = [
            "learning_platform:manager_account_list",
            "learning_platform:manager_teacher_create",
            "learning_platform:manager_subject_list",
            "learning_platform:manager_subject_create",
            "learning_platform:manager_course_list",
            "learning_platform:manager_course_create",
            "learning_platform:manager_subscription_list",
            "learning_platform:manager_subscription_generate",
            "learning_platform:manager_enrollment_list",
            "learning_platform:manager_submission_list",
        ]
        for name in protected_names:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)


    def test_manager_generates_and_cancels_subscription_cards(self):
        manager = User.objects.create_user(
            "subscription-manager",
            password="Manager-2026!secure",
            is_staff=True,
        )
        subject = LearningSubject.objects.create(name="الفيزياء", slug="الفيزياء")
        self.client.force_login(manager)

        response = self.client.post(
            reverse("learning_platform:manager_subscription_generate"),
            {
                "duration": LearningSubscriptionCard.Duration.MONTHLY,
                "subjects": [subject.pk],
                "quantity": 2,
                "prefix": "TEST-26",
            },
        )
        self.assertRedirects(response, reverse("learning_platform:manager_subscription_list"))
        cards = list(LearningSubscriptionCard.objects.order_by("id"))
        self.assertEqual(len(cards), 2)
        self.assertTrue(all(card.code.startswith("TEST-26-") for card in cards))
        self.assertTrue(all(card.subjects.filter(pk=subject.pk).exists() for card in cards))
        self.assertEqual(
            LearningAuditEvent.objects.filter(
                action=LearningAuditEvent.Action.SUBSCRIPTION_CREATED,
            ).count(),
            2,
        )

        cancel_url = reverse("learning_platform:manager_subscription_cancel", args=[cards[0].pk])
        self.assertEqual(self.client.get(cancel_url).status_code, 405)
        response = self.client.post(cancel_url)
        self.assertRedirects(response, reverse("learning_platform:manager_subscription_list"))
        cards[0].refresh_from_db()
        self.assertEqual(cards[0].status, LearningSubscriptionCard.Status.CANCELLED)

    def test_learner_enrolls_and_completes_published_lessons(self):
        teacher = self.create_account(
            email="operations-teacher@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        learner = self.create_account(email="operations-learner@example.com")
        subject = LearningSubject.objects.create(name="اللغة العربية", slug="اللغة-العربية")
        course = LearningCourse.objects.create(
            subject=subject,
            teacher=teacher,
            title="مهارات اللغة العربية",
            slug="مهارات-اللغة-العربية",
            status=LearningCourse.Status.PUBLISHED,
        )
        first = LearningLesson.objects.create(
            course=course,
            title="الدرس الأول",
            slug="الدرس-الأول",
            order=1,
            is_published=True,
        )
        second = LearningLesson.objects.create(
            course=course,
            title="الدرس الثاني",
            slug="الدرس-الثاني",
            order=2,
            is_published=True,
        )
        card = LearningSubscriptionCard.objects.create(
            code="ARABIC-ACCESS-1",
            duration=LearningSubscriptionCard.Duration.MONTHLY,
        )
        card.subjects.add(subject)
        card.activate(learner)
        self.learning_login(learner)

        response = self.client.post(reverse("learning_platform:course_enroll", args=[course.slug]))
        self.assertRedirects(
            response,
            reverse("learning_platform:lesson_detail", args=[course.slug, first.slug]),
        )
        enrollment = LearningEnrollment.objects.get(learner=learner, course=course)
        self.assertEqual(enrollment.progress_percent, 0)

        response = self.client.post(
            reverse("learning_platform:lesson_complete", args=[course.slug, first.slug])
        )
        self.assertRedirects(
            response,
            reverse("learning_platform:lesson_detail", args=[course.slug, second.slug]),
        )
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.progress_percent, 50)
        self.assertEqual(enrollment.status, LearningEnrollment.Status.ACTIVE)

        response = self.client.post(
            reverse("learning_platform:lesson_complete", args=[course.slug, second.slug])
        )
        self.assertRedirects(response, reverse("learning_platform:course_detail", args=[course.slug]))
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.progress_percent, 100)
        self.assertEqual(enrollment.status, LearningEnrollment.Status.COMPLETED)
        self.assertIsNotNone(enrollment.completed_at)
        self.assertEqual(
            LearningLessonProgress.objects.filter(
                enrollment=enrollment,
                completed_at__isnull=False,
            ).count(),
            2,
        )

    def test_enrollment_requires_active_subscription_for_course_subject(self):
        teacher = self.create_account(
            email="restricted-teacher@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        learner = self.create_account(email="restricted-learner@example.com")
        subject = LearningSubject.objects.create(name="الكيمياء", slug="الكيمياء")
        course = LearningCourse.objects.create(
            subject=subject,
            teacher=teacher,
            title="أساسيات الكيمياء",
            slug="أساسيات-الكيمياء",
            status=LearningCourse.Status.PUBLISHED,
        )
        LearningLesson.objects.create(
            course=course,
            title="المقدمة",
            slug="المقدمة",
            order=1,
            is_published=True,
        )
        self.learning_login(learner)

        response = self.client.post(reverse("learning_platform:course_enroll", args=[course.slug]))
        self.assertRedirects(response, reverse("learning_platform:subscriptions"))
        self.assertFalse(LearningEnrollment.objects.filter(learner=learner, course=course).exists())

    def test_teacher_progress_page_is_limited_to_own_course(self):
        teacher = self.create_account(
            email="owner-teacher@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        other_teacher = self.create_account(
            email="other-teacher@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        learner = self.create_account(email="teacher-view-learner@example.com")
        subject = LearningSubject.objects.create(name="الأحياء", slug="الأحياء")
        own_course = LearningCourse.objects.create(
            subject=subject,
            teacher=teacher,
            title="أحياء متقدمة",
            slug="أحياء-متقدمة",
            status=LearningCourse.Status.PUBLISHED,
        )
        other_course = LearningCourse.objects.create(
            subject=subject,
            teacher=other_teacher,
            title="أحياء أخرى",
            slug="أحياء-أخرى",
            status=LearningCourse.Status.PUBLISHED,
        )
        LearningEnrollment.objects.create(learner=learner, course=own_course)
        self.learning_login(teacher)

        response = self.client.get(
            reverse("learning_platform:teacher_course_learners", args=[own_course.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, learner.full_name)
        self.assertEqual(
            self.client.get(
                reverse("learning_platform:teacher_course_learners", args=[other_course.pk])
            ).status_code,
            404,
        )

    def test_quiz_is_auto_graded_and_issues_certificate_after_all_requirements(self):
        teacher = self.create_account(
            email="quiz-teacher@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        learner = self.create_account(email="quiz-learner@example.com")
        subject = LearningSubject.objects.create(name="الرياضيات المتقدمة", slug="الرياضيات-المتقدمة")
        course = LearningCourse.objects.create(
            subject=subject,
            teacher=teacher,
            title="دورة الجبر",
            slug="دورة-الجبر",
            status=LearningCourse.Status.PUBLISHED,
        )
        lesson = LearningLesson.objects.create(
            course=course,
            title="المعادلات",
            slug="المعادلات",
            order=1,
            is_published=True,
        )
        assessment = LearningAssessment.objects.create(
            course=course,
            title="اختبار الجبر",
            slug="اختبار-الجبر",
            assessment_type=LearningAssessment.Type.QUIZ,
            max_score=100,
            pass_score=60,
            max_attempts=2,
            order=1,
            is_required=True,
            is_published=True,
        )
        question = LearningQuestion.objects.create(
            assessment=assessment,
            text="كم يساوي 2 + 2؟",
            choice_a="3",
            choice_b="4",
            choice_c="5",
            choice_d="6",
            correct_choice=LearningQuestion.Choice.B,
            points=1,
            order=1,
        )
        card = LearningSubscriptionCard.objects.create(
            code="QUIZ-CARD-1",
            duration=LearningSubscriptionCard.Duration.MONTHLY,
        )
        card.subjects.add(subject)
        card.activate(learner)
        self.learning_login(learner)
        self.client.post(reverse("learning_platform:course_enroll", args=[course.slug]))
        enrollment = LearningEnrollment.objects.get(learner=learner, course=course)

        self.client.post(reverse("learning_platform:lesson_complete", args=[course.slug, lesson.slug]))
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.progress_percent, 50)
        self.assertEqual(enrollment.status, LearningEnrollment.Status.ACTIVE)

        response = self.client.post(
            reverse("learning_platform:assessment_detail", args=[course.slug, assessment.slug]),
            {f"question_{question.pk}": LearningQuestion.Choice.B},
        )
        self.assertRedirects(
            response,
            reverse("learning_platform:assessment_detail", args=[course.slug, assessment.slug]),
        )
        submission = LearningSubmission.objects.get(enrollment=enrollment, assessment=assessment)
        self.assertEqual(submission.status, LearningSubmission.Status.GRADED)
        self.assertEqual(submission.score, Decimal("100.00"))
        self.assertTrue(submission.is_passed)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.progress_percent, 100)
        self.assertEqual(enrollment.status, LearningEnrollment.Status.COMPLETED)
        certificate = LearningCertificate.objects.get(enrollment=enrollment)
        self.assertTrue(certificate.is_active)
        self.assertEqual(
            self.client.get(reverse("learning_platform:certificate_detail", args=[course.slug])).status_code,
            200,
        )
        verify_response = self.client.get(
            reverse("learning_platform:certificate_verify", args=[certificate.verification_code])
        )
        self.assertContains(verify_response, "شهادة صحيحة وفعالة")
        self.assertContains(verify_response, learner.full_name)

    def test_assignment_waits_for_teacher_grading_then_completes_course(self):
        teacher = self.create_account(
            email="assignment-teacher@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        learner = self.create_account(email="assignment-learner@example.com")
        subject = LearningSubject.objects.create(name="الكتابة", slug="الكتابة")
        course = LearningCourse.objects.create(
            subject=subject,
            teacher=teacher,
            title="مهارات الكتابة",
            slug="مهارات-الكتابة",
            status=LearningCourse.Status.PUBLISHED,
        )
        lesson = LearningLesson.objects.create(
            course=course,
            title="بناء الفقرة",
            slug="بناء-الفقرة",
            order=1,
            is_published=True,
        )
        assessment = LearningAssessment.objects.create(
            course=course,
            title="واجب كتابة فقرة",
            slug="واجب-كتابة-فقرة",
            assessment_type=LearningAssessment.Type.ASSIGNMENT,
            max_score=20,
            pass_score=12,
            max_attempts=2,
            order=1,
            is_required=True,
            is_published=True,
        )
        card = LearningSubscriptionCard.objects.create(
            code="ASSIGNMENT-CARD-1",
            duration=LearningSubscriptionCard.Duration.MONTHLY,
        )
        card.subjects.add(subject)
        card.activate(learner)
        self.learning_login(learner)
        self.client.post(reverse("learning_platform:course_enroll", args=[course.slug]))
        self.client.post(reverse("learning_platform:lesson_complete", args=[course.slug, lesson.slug]))
        enrollment = LearningEnrollment.objects.get(learner=learner, course=course)

        response = self.client.post(
            reverse("learning_platform:assessment_detail", args=[course.slug, assessment.slug]),
            {"answer_text": "هذه فقرة تعليمية مكتملة تتضمن فكرة رئيسة وتفاصيل داعمة."},
        )
        self.assertRedirects(
            response,
            reverse("learning_platform:assessment_detail", args=[course.slug, assessment.slug]),
        )
        submission = LearningSubmission.objects.get(enrollment=enrollment, assessment=assessment)
        self.assertEqual(submission.status, LearningSubmission.Status.SUBMITTED)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.progress_percent, 50)
        self.assertFalse(LearningCertificate.objects.filter(enrollment=enrollment).exists())

        self.learning_login(teacher)
        response = self.client.get(
            reverse("learning_platform:teacher_submission_list", args=[course.pk])
        )
        self.assertContains(response, learner.full_name)
        response = self.client.post(
            reverse("learning_platform:teacher_submission_grade", args=[submission.pk]),
            {"score": "18", "feedback": "إجابة منظمة وواضحة."},
        )
        self.assertRedirects(
            response,
            reverse("learning_platform:teacher_submission_list", args=[course.pk]),
        )
        submission.refresh_from_db()
        self.assertEqual(submission.status, LearningSubmission.Status.GRADED)
        self.assertEqual(submission.score, Decimal("18.00"))
        self.assertTrue(submission.is_passed)
        self.assertEqual(submission.graded_by, teacher)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, LearningEnrollment.Status.COMPLETED)
        self.assertTrue(LearningCertificate.objects.filter(enrollment=enrollment, revoked_at__isnull=True).exists())

    def test_teacher_cannot_grade_another_teachers_assignment(self):
        owner = self.create_account(
            email="grading-owner@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        outsider = self.create_account(
            email="grading-outsider@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        learner = self.create_account(email="grading-learner@example.com")
        subject = LearningSubject.objects.create(name="التاريخ", slug="التاريخ")
        course = LearningCourse.objects.create(
            subject=subject, teacher=owner, title="تاريخ الأردن", slug="تاريخ-الأردن"
        )
        assessment = LearningAssessment.objects.create(
            course=course,
            title="واجب تاريخي",
            slug="واجب-تاريخي",
            assessment_type=LearningAssessment.Type.ASSIGNMENT,
            order=1,
        )
        enrollment = LearningEnrollment.objects.create(learner=learner, course=course)
        submission = LearningSubmission.objects.create(
            assessment=assessment,
            enrollment=enrollment,
            answer_text="إجابة تاريخية مطولة.",
        )
        self.learning_login(outsider)
        self.assertEqual(
            self.client.get(
                reverse("learning_platform:teacher_submission_grade", args=[submission.pk])
            ).status_code,
            404,
        )

    def test_manager_builds_quiz_then_publishes_it_after_questions_exist(self):
        manager = User.objects.create_user(
            "assessment-manager",
            password="Manager-2026!secure",
            is_staff=True,
        )
        teacher = self.create_account(
            email="assessment-builder@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        subject = LearningSubject.objects.create(name="الحاسوب", slug="الحاسوب")
        course = LearningCourse.objects.create(
            subject=subject,
            teacher=teacher,
            title="أساسيات الحاسوب",
            slug="أساسيات-الحاسوب",
            status=LearningCourse.Status.PUBLISHED,
        )
        LearningLesson.objects.create(
            course=course,
            title="المقدمة",
            slug="المقدمة",
            order=1,
            is_published=True,
        )
        self.client.force_login(manager)
        response = self.client.post(
            reverse("learning_platform:manager_assessment_create", args=[course.pk]),
            {
                "title": "اختبار الحاسوب",
                "slug": "",
                "assessment_type": LearningAssessment.Type.QUIZ,
                "instructions": "اختر الإجابة الصحيحة.",
                "max_score": 10,
                "pass_score": 6,
                "max_attempts": 2,
                "order": 1,
                "is_required": "on",
                "due_at": "",
            },
        )
        assessment = LearningAssessment.objects.get(course=course)
        self.assertRedirects(
            response,
            reverse("learning_platform:manager_question_list", args=[assessment.pk]),
        )
        self.assertFalse(assessment.is_published)
        response = self.client.post(
            reverse("learning_platform:manager_question_create", args=[assessment.pk]),
            {
                "text": "أي جهاز يعالج البيانات؟",
                "choice_a": "المعالج",
                "choice_b": "الشاشة",
                "choice_c": "لوحة المفاتيح",
                "choice_d": "الطابعة",
                "correct_choice": LearningQuestion.Choice.A,
                "points": 1,
                "order": 1,
            },
        )
        self.assertRedirects(
            response,
            reverse("learning_platform:manager_question_list", args=[assessment.pk]),
        )
        response = self.client.post(
            reverse("learning_platform:manager_assessment_update", args=[assessment.pk]),
            {
                "title": assessment.title,
                "slug": assessment.slug,
                "assessment_type": assessment.assessment_type,
                "instructions": assessment.instructions,
                "max_score": assessment.max_score,
                "pass_score": assessment.pass_score,
                "max_attempts": assessment.max_attempts,
                "order": assessment.order,
                "is_required": "on",
                "is_published": "on",
                "due_at": "",
            },
        )
        self.assertRedirects(
            response,
            reverse("learning_platform:manager_assessment_list", args=[course.pk]),
        )
        assessment.refresh_from_db()
        self.assertTrue(assessment.is_published)


    @override_settings(
        OPAL_LEARNING_EMAIL_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="learning@example.com",
    )
    def test_password_reset_email_changes_password_and_invalidates_old_sessions(self):
        account = self.create_account(email="recover@example.com")
        old_client = Client()
        old_session = old_client.session
        old_session[LEARNING_SESSION_KEY] = account.pk
        old_session[LEARNING_AUTH_VERSION_KEY] = account.auth_version
        old_session.save()

        response = self.client.post(
            reverse("learning_platform:password_reset_request"),
            {"email": account.email},
        )
        self.assertRedirects(response, reverse("learning_platform:password_reset_done"))
        reset_request = LearningPasswordResetRequest.objects.get(account=account)
        self.assertEqual(
            reset_request.delivery_status,
            LearningPasswordResetRequest.DeliveryStatus.SENT,
        )
        self.assertEqual(len(mail.outbox), 1)
        reset_url = next(
            line.strip() for line in mail.outbox[0].body.splitlines() if line.startswith("http")
        )
        reset_path = urlparse(reset_url).path
        new_password = "Opal-New-Password-2026!"
        response = self.client.post(
            reset_path,
            {"password1": new_password, "password2": new_password},
        )
        self.assertRedirects(response, reverse("learning_platform:login"))
        account.refresh_from_db()
        reset_request.refresh_from_db()
        self.assertTrue(account.check_password(new_password))
        self.assertEqual(account.auth_version, 2)
        self.assertIsNotNone(reset_request.used_at)
        old_response = old_client.get(reverse("learning_platform:dashboard"))
        self.assertEqual(old_response.status_code, 302)
        self.assertTrue(old_response.url.startswith(reverse("learning_platform:login")))

    @override_settings(
        OPAL_LEARNING_EMAIL_ENABLED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_password_reset_request_does_not_disclose_unknown_email(self):
        response = self.client.post(
            reverse("learning_platform:password_reset_request"),
            {"email": "unknown@example.com"},
        )
        self.assertRedirects(response, reverse("learning_platform:password_reset_done"))
        self.assertEqual(LearningPasswordResetRequest.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_manager_can_issue_one_time_temporary_password(self):
        account = self.create_account(email="temporary@example.com")
        manager = User.objects.create_user(
            "recovery-manager",
            password="Manager-2026!secure",
            is_staff=True,
        )
        self.client.force_login(manager)
        response = self.client.post(
            reverse("learning_platform:manager_account_password_reset", args=[account.pk]),
            {"confirm": "on"},
        )
        self.assertEqual(response.status_code, 200)
        temporary_password = response.context["temporary_password"]
        self.assertTrue(temporary_password.startswith("Opal-"))
        account.refresh_from_db()
        self.assertTrue(account.check_password(temporary_password))
        self.assertEqual(account.auth_version, 2)
        self.assertTrue(
            LearningAuditEvent.objects.filter(
                account=account,
                action=LearningAuditEvent.Action.PASSWORD_RESET_BY_MANAGER,
            ).exists()
        )

    def test_assignment_submission_and_grading_create_role_notifications(self):
        teacher = self.create_account(
            email="notice-teacher@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        learner = self.create_account(email="notice-learner@example.com")
        subject = LearningSubject.objects.create(name="الإشعارات", slug="الإشعارات")
        course = LearningCourse.objects.create(
            subject=subject,
            teacher=teacher,
            title="دورة الإشعارات",
            slug="دورة-الإشعارات",
            status=LearningCourse.Status.PUBLISHED,
        )
        assessment = LearningAssessment.objects.create(
            course=course,
            title="واجب الإشعار",
            slug="واجب-الإشعار",
            assessment_type=LearningAssessment.Type.ASSIGNMENT,
            max_score=10,
            pass_score=6,
            order=1,
            is_published=True,
        )
        card = LearningSubscriptionCard.objects.create(
            code="NOTICE-CARD-1",
            duration=LearningSubscriptionCard.Duration.MONTHLY,
        )
        card.subjects.add(subject)
        card.activate(learner)
        enrollment = LearningEnrollment.objects.create(learner=learner, course=course)
        submission = submit_assignment(
            enrollment,
            assessment,
            "إجابة تعليمية كافية لإرسال الواجب إلى المدرّس.",
        )
        self.assertTrue(
            teacher.notifications.filter(
                notification_type=LearningNotification.Type.ASSESSMENT,
                dedupe_key=f"assignment-submitted:{submission.pk}",
            ).exists()
        )
        grade_assignment(
            submission,
            score=8,
            feedback="جيد",
            grader=teacher,
        )
        self.assertTrue(
            learner.notifications.filter(
                notification_type=LearningNotification.Type.ASSESSMENT,
                title="تم تصحيح واجبك",
            ).exists()
        )

    def test_notification_inbox_is_scoped_and_marked_read_by_post(self):
        owner = self.create_account(email="notice-owner@example.com")
        other = self.create_account(email="notice-other@example.com")
        notice = LearningNotification.objects.create(
            recipient=owner,
            title="تنبيه خاص",
            body="هذا التنبيه يخص صاحب الحساب فقط.",
            action_url=reverse("learning_platform:dashboard"),
        )
        LearningNotification.objects.create(
            recipient=other,
            title="تنبيه حساب آخر",
            body="لا يجب أن يظهر.",
        )
        self.learning_login(owner)
        response = self.client.get(reverse("learning_platform:notification_list"))
        self.assertContains(response, "تنبيه خاص")
        self.assertNotContains(response, "تنبيه حساب آخر")
        response = self.client.post(
            reverse("learning_platform:notification_open", args=[notice.pk])
        )
        self.assertRedirects(response, reverse("learning_platform:dashboard"))
        notice.refresh_from_db()
        self.assertIsNotNone(notice.read_at)

    def test_expiring_subscription_notification_is_idempotent(self):
        learner = self.create_account(email="expiring@example.com")
        card = LearningSubscriptionCard.objects.create(
            code="EXPIRING-CARD-1",
            duration=LearningSubscriptionCard.Duration.MONTHLY,
            status=LearningSubscriptionCard.Status.REDEEMED,
            redeemed_by=learner,
            activated_at=timezone.now() - timedelta(days=27),
            expires_at=timezone.now() + timedelta(days=3),
        )
        self.learning_login(learner)
        self.client.get(reverse("learning_platform:dashboard"))
        self.client.get(reverse("learning_platform:dashboard"))
        self.assertEqual(
            learner.notifications.filter(
                dedupe_key__startswith=f"subscription-expiring:{card.pk}:"
            ).count(),
            1,
        )

    def test_manager_operational_report_and_csv_export(self):
        manager = User.objects.create_user(
            "report-manager",
            password="Manager-2026!secure",
            is_staff=True,
        )
        teacher = self.create_account(
            email="report-teacher@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        learner = self.create_account(email="report-learner@example.com")
        subject = LearningSubject.objects.create(name="تقارير", slug="تقارير")
        course = LearningCourse.objects.create(
            subject=subject,
            teacher=teacher,
            title="دورة التقارير",
            slug="دورة-التقارير",
        )
        LearningEnrollment.objects.create(
            learner=learner,
            course=course,
            progress_percent=40,
        )
        self.client.force_login(manager)
        response = self.client.get(reverse("learning_platform:manager_report_center"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "التقارير التشغيلية")
        self.assertContains(response, "دورة التقارير")
        csv_response = self.client.get(reverse("learning_platform:manager_report_export_csv"))
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("text/csv", csv_response["Content-Type"])
        payload = csv_response.content.decode("utf-8-sig")
        self.assertIn("report-learner@example.com", payload)
        self.assertIn("دورة التقارير", payload)


    def test_learner_assistant_uses_only_enrolled_course_content(self):
        teacher = self.create_account(
            email="ai-teacher@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        learner = self.create_account(email="ai-learner@example.com")
        subject = LearningSubject.objects.create(name="العلوم", slug="science-ai")
        course = LearningCourse.objects.create(
            subject=subject,
            teacher=teacher,
            title="أساسيات الطاقة",
            slug="energy-basics",
            status=LearningCourse.Status.PUBLISHED,
            summary="تشرح الدورة صور الطاقة وتحولاتها.",
        )
        lesson = LearningLesson.objects.create(
            course=course,
            title="الطاقة الحركية",
            slug="kinetic-energy",
            content="الطاقة الحركية هي الطاقة التي يمتلكها الجسم بسبب حركته. تزداد بزيادة سرعة الجسم.",
            order=1,
            is_published=True,
        )
        card = LearningSubscriptionCard.objects.create(
            code="AI-LEARNER-CARD",
            duration=LearningSubscriptionCard.Duration.MONTHLY,
            grants_all_subjects=True,
        )
        card.activate(learner)
        LearningEnrollment.objects.create(learner=learner, course=course)
        self.learning_login(learner)

        response = self.client.post(
            reverse("learning_platform:learner_ai_assistant"),
            {"course": course.pk, "question": "ما معنى الطاقة الحركية؟"},
        )

        interaction = LearningAIInteraction.objects.get(account=learner)
        self.assertRedirects(
            response,
            f"{reverse('learning_platform:learner_ai_assistant')}?interaction={interaction.pk}",
        )
        self.assertEqual(interaction.status, LearningAIInteraction.Status.LOCAL_REFERENCE)
        self.assertEqual(interaction.source_lesson_ids, [lesson.pk])
        self.assertIn("الطاقة الحركية", interaction.response)
        self.assertFalse(LearningAIDraft.objects.exists())
        page = self.client.get(
            reverse("learning_platform:learner_ai_assistant"),
            {"interaction": interaction.pk},
        )
        self.assertContains(page, "المراجع المستخدمة")
        self.assertContains(page, "الدرس: الطاقة الحركية")

    def test_learner_assistant_rejects_course_outside_enrollment(self):
        teacher = self.create_account(
            email="scope-teacher@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        learner = self.create_account(email="scope-learner@example.com")
        subject = LearningSubject.objects.create(name="الفيزياء", slug="physics-ai")
        course = LearningCourse.objects.create(
            subject=subject,
            teacher=teacher,
            title="دورة غير مسجل بها",
            slug="not-enrolled-course",
            status=LearningCourse.Status.PUBLISHED,
        )
        LearningLesson.objects.create(
            course=course,
            title="درس خاص",
            slug="private-lesson",
            content="محتوى لا يجوز عرضه لمتعلم غير مسجل في الدورة.",
            order=1,
            is_published=True,
        )
        self.learning_login(learner)

        response = self.client.post(
            reverse("learning_platform:learner_ai_assistant"),
            {"course": course.pk, "question": "اعرض المحتوى"},
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertIn("course", form.errors)
        self.assertNotIn(course, form.fields["course"].queryset)
        self.assertFalse(LearningAIInteraction.objects.exists())

    def test_teacher_ai_tool_saves_review_draft_without_publishing(self):
        teacher = self.create_account(
            email="draft-teacher@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        subject = LearningSubject.objects.create(name="اللغة العربية", slug="arabic-ai")
        course = LearningCourse.objects.create(
            subject=subject,
            teacher=teacher,
            title="مهارات القراءة",
            slug="reading-skills",
            status=LearningCourse.Status.DRAFT,
        )
        LearningLesson.objects.create(
            course=course,
            title="الفكرة الرئيسة",
            slug="main-idea",
            content="الفكرة الرئيسة هي المعنى العام الذي يجمع تفاصيل النص ويربط بينها.",
            order=1,
            is_published=True,
        )
        lessons_before = LearningLesson.objects.count()
        assessments_before = LearningAssessment.objects.count()
        self.learning_login(teacher)

        response = self.client.post(
            reverse("learning_platform:teacher_ai_workspace"),
            {
                "course": course.pk,
                "tool": LearningAIInteraction.Type.TEACHER_OUTLINE,
                "title": "خطة الفكرة الرئيسة",
                "prompt": "خطة درس قصيرة لتعليم الفكرة الرئيسة للصف السابع",
            },
        )

        draft = LearningAIDraft.objects.get(teacher=teacher, course=course)
        self.assertRedirects(
            response,
            f"{reverse('learning_platform:teacher_ai_workspace')}?draft={draft.pk}",
        )
        self.assertEqual(draft.status, LearningAIDraft.Status.DRAFT)
        self.assertIn("مسودة خطة درس", draft.content)
        self.assertEqual(LearningLesson.objects.count(), lessons_before)
        self.assertEqual(LearningAssessment.objects.count(), assessments_before)
        course.refresh_from_db()
        self.assertEqual(course.status, LearningCourse.Status.DRAFT)

        response = self.client.post(
            reverse("learning_platform:teacher_ai_draft_status", args=[draft.pk]),
            {"action": "accept"},
        )
        self.assertRedirects(
            response,
            f"{reverse('learning_platform:teacher_ai_workspace')}?draft={draft.pk}",
        )
        draft.refresh_from_db()
        self.assertEqual(draft.status, LearningAIDraft.Status.ACCEPTED)
        course.refresh_from_db()
        self.assertEqual(course.status, LearningCourse.Status.DRAFT)

    def test_teacher_ai_service_cannot_use_another_teachers_course(self):
        first_teacher = self.create_account(
            email="first-ai-teacher@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        second_teacher = self.create_account(
            email="second-ai-teacher@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        subject = LearningSubject.objects.create(name="الرياضيات المتقدمة", slug="advanced-math-ai")
        course = LearningCourse.objects.create(
            subject=subject,
            teacher=second_teacher,
            title="دورة المدرس الثاني",
            slug="second-teacher-course",
        )
        LearningLesson.objects.create(
            course=course,
            title="مقدمة",
            slug="intro",
            content="محتوى الدورة الخاصة بالمدرس الثاني فقط.",
            order=1,
            is_published=True,
        )

        with self.assertRaises(PermissionDenied):
            run_grounded_assistance(
                first_teacher,
                course,
                LearningAIInteraction.Type.TEACHER_SUMMARY,
                "أنشئ ملخصًا",
            )
        self.assertFalse(LearningAIInteraction.objects.exists())
        self.assertFalse(LearningAIDraft.objects.exists())

    @override_settings(
        OPAL_LEARNING_AI_PROVIDER_ENABLED=True,
        OPAL_LEARNING_AI_BASE_URL="https://provider.invalid/v1",
        OPAL_LEARNING_AI_API_KEY="secret-key-must-never-render",
        OPAL_LEARNING_AI_MODEL="governed-model",
    )
    def test_manager_ai_center_controls_governance_without_exposing_secret(self):
        manager = User.objects.create_user(
            username="ai-governance-manager",
            password="Manager-2026!secure",
            is_staff=True,
        )
        self.client.force_login(manager)

        response = self.client.get(reverse("learning_platform:manager_ai_center"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "حوكمة المساعد التعليمي")
        self.assertContains(response, "governed-model")
        self.assertNotContains(response, "secret-key-must-never-render")

        response = self.client.post(
            reverse("learning_platform:manager_ai_center"),
            {
                "assistant_enabled": "on",
                "teacher_tools_enabled": "on",
                "external_provider_enabled": "on",
                "local_reference_enabled": "on",
                "learner_daily_limit": 7,
                "teacher_daily_limit": 9,
                "max_context_chars": 9000,
                "max_output_chars": 2500,
                "policy_text": "استخدم المحتوى المنشور فقط ولا تنشر أي مسودة تلقائيًا.",
            },
        )
        self.assertRedirects(response, reverse("learning_platform:manager_ai_center"))
        governance = LearningAISettings.load()
        self.assertEqual(governance.learner_daily_limit, 7)
        self.assertEqual(governance.teacher_daily_limit, 9)
        self.assertTrue(governance.external_provider_enabled)
        self.assertTrue(
            LearningAuditEvent.objects.filter(
                action=LearningAuditEvent.Action.AI_SETTINGS_UPDATED,
            ).exists()
        )

    def test_ai_daily_limit_prevents_unbounded_requests(self):
        teacher = self.create_account(
            email="limit-teacher@example.com",
            role=LearningAccount.Role.TEACHER,
        )
        learner = self.create_account(email="limit-learner@example.com")
        subject = LearningSubject.objects.create(name="الأحياء", slug="biology-ai")
        course = LearningCourse.objects.create(
            subject=subject,
            teacher=teacher,
            title="أساسيات الخلية",
            slug="cell-basics",
            status=LearningCourse.Status.PUBLISHED,
        )
        LearningLesson.objects.create(
            course=course,
            title="الخلية",
            slug="cell",
            content="الخلية هي الوحدة الأساسية في بناء الكائن الحي وتحتوي مكونات تؤدي وظائف محددة.",
            order=1,
            is_published=True,
        )
        card = LearningSubscriptionCard.objects.create(
            code="AI-LIMIT-CARD",
            duration=LearningSubscriptionCard.Duration.MONTHLY,
            grants_all_subjects=True,
        )
        card.activate(learner)
        LearningEnrollment.objects.create(learner=learner, course=course)
        governance = LearningAISettings.load()
        governance.learner_daily_limit = 1
        governance.save(update_fields=["learner_daily_limit", "updated_at"])
        self.learning_login(learner)

        first = self.client.post(
            reverse("learning_platform:learner_ai_assistant"),
            {"course": course.pk, "question": "ما الخلية؟"},
        )
        self.assertEqual(first.status_code, 302)
        second = self.client.post(
            reverse("learning_platform:learner_ai_assistant"),
            {"course": course.pk, "question": "ما مكونات الخلية؟"},
        )
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, "وصلت إلى الحد اليومي")
        self.assertEqual(LearningAIInteraction.objects.filter(account=learner).count(), 1)

class LearningProductionReleaseTests(TestCase):
    password = "Opal-Production-2026!secure"

    def create_account(self, *, email="production-learner@example.com", role=LearningAccount.Role.LEARNER, verified=True):
        account = LearningAccount(
            email=email,
            full_name="مستخدم تشغيل",
            role=role,
            terms_accepted_at=timezone.now(),
            privacy_accepted_at=timezone.now(),
            email_verified_at=timezone.now() if verified else None,
        )
        account.set_password(self.password)
        account.save()
        return account

    def create_plan(self):
        return LearningSubscriptionPlan.objects.create(
            name="الخطة التشغيلية",
            slug="production-plan",
            duration=LearningSubscriptionCard.Duration.MONTHLY,
            price=Decimal("10.000"),
            currency="JOD",
            grants_all_subjects=True,
        )

    def test_registration_records_legal_acceptance_and_verification_request(self):
        response = self.client.post(
            reverse("learning_platform:register"),
            {
                "full_name": "متعلم جديد",
                "email": "new-production@example.com",
                "phone": "0790000011",
                "password1": self.password,
                "password2": self.password,
                "accept_terms": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        account = LearningAccount.objects.get(email="new-production@example.com")
        self.assertIsNotNone(account.terms_accepted_at)
        self.assertIsNotNone(account.privacy_accepted_at)
        self.assertIsNone(account.email_verified_at)
        self.assertTrue(LearningEmailVerificationRequest.objects.filter(account=account).exists())

    def test_api_login_me_and_logout_use_hashed_device_token(self):
        account = self.create_account()
        response = self.client.post(
            reverse("learning_platform:api_login"),
            data=json.dumps({"email": account.email, "password": self.password, "device_name": "Android Test"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        raw_token = response.json()["data"]["token"]
        stored = LearningAPIToken.objects.get(account=account)
        self.assertNotEqual(stored.token_hash, raw_token)
        self.assertEqual(stored.device_name, "Android Test")
        auth = {"HTTP_AUTHORIZATION": f"Bearer {raw_token}"}
        me = self.client.get(reverse("learning_platform:api_me"), **auth)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["data"]["email"], account.email)
        logout = self.client.post(reverse("learning_platform:api_logout"), **auth)
        self.assertEqual(logout.status_code, 200)
        stored.refresh_from_db()
        self.assertIsNotNone(stored.revoked_at)

    @override_settings(
        OPAL_LEARNING_PAYMENT_ENABLED=True,
        OPAL_LEARNING_PAYMENT_PROVIDER="manual",
        OPAL_LEARNING_MANUAL_PAYMENT_ALLOWED=True,
    )
    def test_manual_payment_approval_activates_one_subscription_idempotently(self):
        learner = self.create_account(email="paid@example.com")
        plan = self.create_plan()
        order, created = create_payment_order(learner, plan, idempotency_key="manual-order-1")
        self.assertTrue(created)
        order = mark_order_paid(order, provider_reference="CASH-001", manager_label="مدير")
        self.assertEqual(order.status, LearningPaymentOrder.Status.PAID)
        self.assertTrue(order.subscription_card.is_current)
        first_card_id = order.subscription_card_id
        order = mark_order_paid(order, provider_reference="CASH-001", manager_label="مدير")
        self.assertEqual(order.subscription_card_id, first_card_id)
        self.assertEqual(LearningSubscriptionCard.objects.filter(redeemed_by=learner).count(), 1)

    @override_settings(OPAL_LEARNING_PAYMENT_WEBHOOK_SECRET="webhook-secret")
    def test_signed_payment_webhook_is_idempotent(self):
        learner = self.create_account(email="webhook@example.com")
        plan = self.create_plan()
        order, _ = create_payment_order(learner, plan, idempotency_key="webhook-order-1")
        payload = {
            "event_id": "evt-001",
            "event_type": "payment.paid",
            "merchant_order_id": order.public_id,
            "reference": "provider-001",
            "amount": "10.000",
            "currency": "JOD",
        }
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(b"webhook-secret", raw, hashlib.sha256).hexdigest()
        paid, event, created = process_payment_webhook(raw, signature)
        self.assertTrue(created)
        self.assertEqual(paid.status, LearningPaymentOrder.Status.PAID)
        again, same_event, created_again = process_payment_webhook(raw, signature)
        self.assertFalse(created_again)
        self.assertEqual(event.pk, same_event.pk)
        self.assertEqual(again.subscription_card_id, paid.subscription_card_id)
        self.assertEqual(LearningPaymentEvent.objects.count(), 1)

    def test_pwa_manifest_and_health_endpoint_are_public(self):
        manifest = self.client.get(reverse("learning_platform:mobile_manifest"))
        self.assertEqual(manifest.status_code, 200)
        self.assertEqual(manifest["Content-Type"], "application/manifest+json")
        self.assertContains(manifest, '"scope": "/learning/"')
        health = self.client.get(reverse("learning_platform:health"))
        self.assertIn(health.status_code, {200, 503})
        self.assertEqual(health.json()["service"], "opal-learning-platform")

    def test_manager_readiness_and_payment_surfaces_require_erp_manager(self):
        response = self.client.get(reverse("learning_platform:manager_readiness_center"))
        self.assertEqual(response.status_code, 302)
        manager = User.objects.create_user(
            username="production-manager",
            password="Manager-2026!secure",
            is_staff=True,
        )
        self.client.force_login(manager)
        readiness = self.client.get(reverse("learning_platform:manager_readiness_center"))
        payments = self.client.get(reverse("learning_platform:manager_payment_list"))
        self.assertEqual(readiness.status_code, 200)
        self.assertEqual(payments.status_code, 200)
        self.assertContains(readiness, "جاهزية التشغيل الفعلي")
    @override_settings(OPAL_LEARNING_PUBLIC_LAUNCH=True)
    def test_legacy_account_must_accept_legal_terms_itself(self):
        account = LearningAccount(email="legacy-legal@example.com", full_name="حساب سابق", role=LearningAccount.Role.LEARNER)
        account.set_password(self.password)
        account.save()
        session = self.client.session
        session[LEARNING_SESSION_KEY] = account.pk
        session[LEARNING_AUTH_VERSION_KEY] = account.auth_version
        session.save()
        dashboard = self.client.get(reverse("learning_platform:dashboard"))
        self.assertRedirects(dashboard, reverse("learning_platform:legal_acceptance"))
        accepted = self.client.post(
            reverse("learning_platform:legal_acceptance"),
            {"accept_terms": "on", "accept_privacy": "on"},
        )
        self.assertRedirects(accepted, reverse("learning_platform:dashboard"))
        account.refresh_from_db()
        self.assertIsNotNone(account.terms_accepted_at)
        self.assertIsNotNone(account.privacy_accepted_at)

    @override_settings(OPAL_LEARNING_PAYMENT_WEBHOOK_SECRET="webhook-secret")
    def test_paid_webhook_rejects_amount_or_currency_mismatch(self):
        learner = self.create_account(email="webhook-mismatch@example.com")
        plan = self.create_plan()
        order, _ = create_payment_order(learner, plan, idempotency_key="webhook-mismatch-1")
        payload = {
            "event_id": "evt-mismatch",
            "event_type": "payment.paid",
            "merchant_order_id": order.public_id,
            "reference": "provider-mismatch",
            "amount": "9.000",
            "currency": "JOD",
        }
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(b"webhook-secret", raw, hashlib.sha256).hexdigest()
        with self.assertRaisesMessage(ValidationError, "لا يطابقان"):
            process_payment_webhook(raw, signature)
        order.refresh_from_db()
        self.assertEqual(order.status, LearningPaymentOrder.Status.PENDING)

    def test_mobile_assessment_detail_never_exposes_correct_answer(self):
        learner = self.create_account(email="mobile-quiz@example.com")
        teacher = self.create_account(email="mobile-teacher@example.com", role=LearningAccount.Role.TEACHER)
        subject = LearningSubject.objects.create(name="رياضيات تطبيقية", slug="mobile-math")
        course = LearningCourse.objects.create(
            subject=subject,
            teacher=teacher,
            title="اختبار الموبايل",
            slug="mobile-quiz-course",
            status=LearningCourse.Status.PUBLISHED,
        )
        assessment = LearningAssessment.objects.create(
            course=course,
            title="اختبار قصير",
            slug="mobile-quiz",
            assessment_type=LearningAssessment.Type.QUIZ,
            is_published=True,
        )
        LearningQuestion.objects.create(
            assessment=assessment,
            text="كم يساوي 1 + 1؟",
            choice_a="1",
            choice_b="2",
            choice_c="3",
            choice_d="4",
            correct_choice=LearningQuestion.Choice.B,
            order=1,
        )
        card = LearningSubscriptionCard.objects.create(
            code="MOBILE-QUIZ-CARD",
            duration=LearningSubscriptionCard.Duration.MONTHLY,
            grants_all_subjects=True,
        )
        card.activate(learner)
        LearningEnrollment.objects.create(learner=learner, course=course)
        _token, raw_token = issue_api_token(learner, device_name="Test Device")
        response = self.client.get(
            reverse(
                "learning_platform:api_assessment_detail",
                kwargs={"course_slug": course.slug, "assessment_slug": assessment.slug},
            ),
            HTTP_AUTHORIZATION=f"Bearer {raw_token}",
        )
        self.assertEqual(response.status_code, 200)
        encoded = json.dumps(response.json(), ensure_ascii=False)
        self.assertNotIn("correct_choice", encoded)
        self.assertIn("choices", encoded)

