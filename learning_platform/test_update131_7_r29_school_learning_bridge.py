from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from academics.models import Enrollment, Grade, Section, Subject
from core.models import AcademicYear, Branch, School
from parent_portal.models import Family, FamilyStudent
from students.models import Student
from teachers.models import Teacher, TeacherAssignment

from .forms import LearningTeacherSchoolCourseForm
from .models import (
    LearningAccessSettings,
    LearningCourse,
    LearningGradeAccessOverride,
    LearningStudentAccessOverride,
    LearningStudentProfile,
    LearningSubscriptionCard,
    LearningTeacherProfile,
)
from .school_bridge import (
    eligible_courses_for_student,
    ensure_learning_subject_for_academic_subject,
    ensure_student_learning_account,
    ensure_teacher_learning_account,
    student_learning_access,
)
from .services import learner_can_access_course
from .session_auth import LEARNING_SESSION_KEY


class R29SchoolLearningBridgeTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_superuser("r29-manager", "manager@example.test", "x")
        self.parent_user = User.objects.create_user("r29-parent", password="x")
        self.teacher_user = User.objects.create_user("r29-teacher", password="x")
        self.school = School.objects.create(name="مدرسة R29", is_active=True)
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            midyear_break_start=date(2027, 1, 16),
            midyear_break_end=date(2027, 1, 31),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        self.grade1 = Grade.objects.create(school=self.school, name="الصف الأول", order=1)
        self.grade2 = Grade.objects.create(school=self.school, name="الصف الثاني", order=2)
        self.section1 = Section.objects.create(
            academic_year=self.year, branch=self.branch, grade=self.grade1, name="شعبة أ", capacity=30
        )
        self.section2 = Section.objects.create(
            academic_year=self.year, branch=self.branch, grade=self.grade2, name="شعبة أ", capacity=30
        )
        self.student = Student.objects.create(
            student_number="R29-S-1", full_name="آدم عباس محمود بني سلامة", grade=self.grade1.name, is_active=True
        )
        self.other_student = Student.objects.create(
            student_number="R29-S-2", full_name="ليان صالح علي الرفاعي", grade=self.grade2.name, is_active=True
        )
        Enrollment.objects.create(
            student=self.student, academic_year=self.year, grade=self.grade1, section=self.section1, status="active"
        )
        Enrollment.objects.create(
            student=self.other_student, academic_year=self.year, grade=self.grade2, section=self.section2, status="active"
        )
        self.family = Family.objects.create(
            school=self.school,
            user=self.parent_user,
            guardian_name="عباس محمود يوسف بني سلامة",
            relation="والد",
            identity_number="R29-G-1",
            family_code="R29-F-1",
            is_active=True,
        )
        FamilyStudent.objects.create(family=self.family, student=self.student, relation="والد", is_active=True)
        self.access = LearningAccessSettings.objects.create(
            school=self.school, parent_default_enabled=False, teacher_sso_enabled=True
        )

        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_number="R29-T-1",
            full_name="محمد أحمد محمود الخطيب",
            school=self.school,
            branch=self.branch,
            is_active=True,
        )
        self.subject1 = Subject.objects.create(
            academic_year=self.year, grade=self.grade1, name="الرياضيات", code="R29-M1", weekly_periods=5
        )
        self.subject2 = Subject.objects.create(
            academic_year=self.year, grade=self.grade2, name="العلوم", code="R29-SCI2", weekly_periods=5
        )
        self.assignment = TeacherAssignment.objects.create(
            teacher=self.teacher,
            academic_year=self.year,
            section=self.section1,
            subject=self.subject1,
            is_primary=True,
            is_active=True,
        )

    def test_student_access_precedence_is_student_then_grade_then_global(self):
        self.assertFalse(student_learning_access(self.student)["enabled"])
        LearningGradeAccessOverride.objects.create(settings=self.access, grade=self.grade1, is_enabled=True)
        self.assertTrue(student_learning_access(self.student)["enabled"])
        LearningStudentAccessOverride.objects.create(settings=self.access, student=self.student, is_enabled=False)
        resolved = student_learning_access(self.student)
        self.assertFalse(resolved["enabled"])
        self.assertEqual(resolved["source"], "student")

    def test_manager_all_off_and_all_on_clear_narrower_exceptions(self):
        LearningGradeAccessOverride.objects.create(settings=self.access, grade=self.grade1, is_enabled=True)
        LearningStudentAccessOverride.objects.create(settings=self.access, student=self.student, is_enabled=True)
        self.client.force_login(self.manager)
        response = self.client.post(reverse("learning_platform:manager_school_access"), {"action": "all_off"})
        self.assertRedirects(response, reverse("learning_platform:manager_school_access"))
        self.access.refresh_from_db()
        self.assertFalse(self.access.parent_default_enabled)
        self.assertFalse(LearningGradeAccessOverride.objects.exists())
        self.assertFalse(LearningStudentAccessOverride.objects.exists())

        response = self.client.post(reverse("learning_platform:manager_school_access"), {"action": "all_on"})
        self.assertRedirects(response, reverse("learning_platform:manager_school_access"))
        self.access.refresh_from_db()
        self.assertTrue(self.access.parent_default_enabled)

    def test_parent_enters_each_child_through_same_erp_login_but_child_has_distinct_learning_identity(self):
        self.access.parent_default_enabled = True
        self.access.save(update_fields=["parent_default_enabled", "updated_at"])
        self.client.force_login(self.parent_user)
        response = self.client.get(reverse("learning_platform:erp_parent_student_entry", args=[self.student.pk]))
        self.assertRedirects(response, reverse("learning_platform:dashboard"))
        profile = LearningStudentProfile.objects.get(student=self.student)
        self.assertTrue(profile.account.is_school_managed)
        self.assertEqual(profile.account.role, profile.account.Role.LEARNER)
        self.assertEqual(self.client.session[LEARNING_SESSION_KEY], profile.account_id)

        response = self.client.get(reverse("learning_platform:erp_parent_student_entry", args=[self.other_student.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(LearningStudentProfile.objects.filter(student=self.other_student).count(), 0)

    def test_school_managed_learner_sees_only_grade_section_courses_and_card_unlocks_content(self):
        self.access.parent_default_enabled = True
        self.access.save(update_fields=["parent_default_enabled", "updated_at"])
        teacher_account = ensure_teacher_learning_account(self.teacher)
        learner = ensure_student_learning_account(self.student)
        learning_math = ensure_learning_subject_for_academic_subject(self.subject1)
        learning_science = ensure_learning_subject_for_academic_subject(self.subject2)
        allowed = LearningCourse.objects.create(
            subject=learning_math,
            teacher=teacher_account,
            title="رياضيات الصف الأول أ",
            slug="r29-math-g1-a",
            grade_label=self.grade1.name,
            academic_subject=self.subject1,
            academic_section=self.section1,
            status=LearningCourse.Status.PUBLISHED,
        )
        denied = LearningCourse.objects.create(
            subject=learning_science,
            teacher=teacher_account,
            title="علوم الصف الثاني أ",
            slug="r29-science-g2-a",
            grade_label=self.grade2.name,
            academic_subject=self.subject2,
            academic_section=self.section2,
            status=LearningCourse.Status.PUBLISHED,
        )
        self.assertEqual(list(eligible_courses_for_student(self.student)), [allowed])
        self.assertFalse(learner_can_access_course(learner, allowed))
        card = LearningSubscriptionCard.objects.create(
            code="R29-CARD-1", duration=LearningSubscriptionCard.Duration.YEARLY, grants_all_subjects=True
        )
        card.activate(learner)
        self.assertTrue(learner_can_access_course(learner, allowed))
        self.assertFalse(learner_can_access_course(learner, denied))

    def test_teacher_sso_and_content_form_are_limited_to_official_assignments(self):
        account = ensure_teacher_learning_account(self.teacher)
        self.assertTrue(LearningTeacherProfile.objects.filter(teacher=self.teacher, account=account).exists())
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse("learning_platform:erp_teacher_entry"))
        self.assertRedirects(response, reverse("learning_platform:dashboard"))
        self.assertEqual(self.client.session[LEARNING_SESSION_KEY], account.pk)

        form = LearningTeacherSchoolCourseForm(teacher=self.teacher)
        self.assertEqual(list(form.fields["assignment"].queryset), [self.assignment])
