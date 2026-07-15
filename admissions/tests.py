from decimal import Decimal

from django.test import SimpleTestCase

from admissions.financial_services import distribute_amount


from datetime import date
from django.contrib.auth.models import User
from django.test import TestCase

from academics.models import Enrollment, Grade, Section
from core.models import AcademicYear, Branch, School
from parent_portal.models import FamilyStudent
from students.models import Student

from .forms import DirectStudentRegistrationForm
from .models import GradeFee
from .services import create_student_registration


class CanonicalRegistrationIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("registrar", password="pass", is_staff=True)
        self.school = School.objects.create(name="مدرسة التسجيل", is_active=True)
        self.branch = Branch.objects.create(school=self.school, name="الرئيسي", is_main=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        self.grade = Grade.objects.create(school=self.school, name="الأول")
        self.section = Section.objects.create(
            academic_year=self.year, branch=self.branch, grade=self.grade, name="الشعبة العامة", is_default=True
        )
        GradeFee.objects.create(
            school=self.school, academic_year=self.year, grade=self.grade, tuition_fee="1000.00"
        )

    def test_one_registration_creates_official_student_enrollment_and_family(self):
        form = DirectStudentRegistrationForm(
            data={
                "first_name": "أحمد",
                "father_name": "محمد",
                "grandfather_name": "علي",
                "family_name": "الاختبار",
                "gender": "male",
                "guardian_name": "محمد علي",
                "guardian_identity_type": "national",
                "guardian_identity_number": "PARENT-NID-1",
                "mother_name": "الأم",
                "phone": "0791234567",
                "address": "عمان",
                "grade": self.grade.pk,
                "section": self.section.pk,
                "transport_type": "none",
                "discount_type": "none",
                "admin_discount_value": "0",
            },
            school=self.school,
            academic_year=self.year,
        )
        self.assertTrue(form.is_valid(), form.errors)
        registration = create_student_registration(form, self.user)
        self.assertEqual(Student.objects.count(), 1)
        self.assertTrue(Enrollment.objects.filter(student=registration.student, academic_year=self.year, status="active").exists())
        self.assertTrue(FamilyStudent.objects.filter(student=registration.student, is_active=True).exists())
        self.assertTrue(registration.parent_initial_username)
        self.assertTrue(registration.parent_initial_password)
        self.assertEqual(registration.student.national_id, "")
        self.assertEqual(registration.guardian_identity_number, "PARENTNID1")
        self.assertEqual(registration.first_payment, Decimal("200.00"))
        self.assertEqual(registration.remaining_amount, Decimal("800.00"))

    def test_manual_form_uses_guardian_identity_not_student_national_id(self):
        form = DirectStudentRegistrationForm(school=self.school, academic_year=self.year)
        self.assertNotIn("national_id", form.fields)
        self.assertIn("guardian_identity_number", form.fields)
        self.assertTrue(form.fields["guardian_identity_number"].required)
        self.assertEqual(list(form.fields["gender"].choices), [("", "---------"), ("male", "ذكر"), ("female", "أنثى")])

    def test_same_guardian_identity_links_siblings_to_one_family(self):
        common = {
            "father_name": "محمد",
            "grandfather_name": "علي",
            "family_name": "الاختبار",
            "gender": "male",
            "guardian_name": "محمد علي",
            "guardian_identity_type": "national",
            "guardian_identity_number": "PARENT-NID-SHARED",
            "mother_name": "الأم",
            "phone": "0791234567",
            "address": "عمان",
            "grade": self.grade.pk,
            "section": self.section.pk,
            "transport_type": "none",
            "discount_type": "none",
            "admin_discount_value": "0",
        }
        first_form = DirectStudentRegistrationForm(
            data={**common, "first_name": "أحمد"}, school=self.school, academic_year=self.year
        )
        self.assertTrue(first_form.is_valid(), first_form.errors)
        first = create_student_registration(first_form, self.user)

        second_form = DirectStudentRegistrationForm(
            data={**common, "first_name": "محمود"}, school=self.school, academic_year=self.year
        )
        self.assertTrue(second_form.is_valid(), second_form.errors)
        second = create_student_registration(second_form, self.user)

        first_family = FamilyStudent.objects.get(student=first.student, is_active=True).family
        second_family = FamilyStudent.objects.get(student=second.student, is_active=True).family
        self.assertEqual(first_family.pk, second_family.pk)


class FamilyPaymentDistributionTests(SimpleTestCase):
    def test_skips_fully_paid_students_and_splits_evenly(self):
        rows = [
            {"student": "A", "total": Decimal("100"), "paid": Decimal("100"), "remaining": Decimal("0")},
            {"student": "B", "total": Decimal("100"), "paid": Decimal("0"), "remaining": Decimal("100")},
            {"student": "C", "total": Decimal("100"), "paid": Decimal("50"), "remaining": Decimal("50")},
        ]
        data, left = distribute_amount(rows, Decimal("60"))
        self.assertEqual(left, Decimal("0.00"))
        self.assertEqual(data[0]["allocated"], Decimal("0.00"))
        self.assertEqual(data[1]["allocated"], Decimal("30.00"))
        self.assertEqual(data[2]["allocated"], Decimal("30.00"))

    def test_caps_each_student_at_remaining_balance(self):
        rows = [
            {"student": "A", "total": Decimal("10"), "paid": Decimal("0"), "remaining": Decimal("10")},
            {"student": "B", "total": Decimal("100"), "paid": Decimal("0"), "remaining": Decimal("100")},
        ]
        data, left = distribute_amount(rows, Decimal("50"))
        self.assertEqual(left, Decimal("0.00"))
        self.assertEqual(data[0]["allocated"], Decimal("10.00"))
        self.assertEqual(data[1]["allocated"], Decimal("40.00"))

    def test_returns_excess_for_validation(self):
        rows = [
            {"student": "A", "total": Decimal("10"), "paid": Decimal("0"), "remaining": Decimal("10")},
        ]
        data, left = distribute_amount(rows, Decimal("12.50"))
        self.assertEqual(data[0]["allocated"], Decimal("10.00"))
        self.assertEqual(left, Decimal("2.50"))

    def test_rounding_is_deterministic_to_one_cent(self):
        rows = [
            {"student": "A", "total": Decimal("10"), "paid": Decimal("0"), "remaining": Decimal("10")},
            {"student": "B", "total": Decimal("10"), "paid": Decimal("0"), "remaining": Decimal("10")},
            {"student": "C", "total": Decimal("10"), "paid": Decimal("0"), "remaining": Decimal("10")},
        ]
        data, left = distribute_amount(rows, Decimal("10.00"))
        self.assertEqual(left, Decimal("0.00"))
        self.assertEqual(sum((row["allocated"] for row in data), Decimal("0.00")), Decimal("10.00"))
        self.assertEqual([row["allocated"] for row in data], [Decimal("3.34"), Decimal("3.33"), Decimal("3.33")])
