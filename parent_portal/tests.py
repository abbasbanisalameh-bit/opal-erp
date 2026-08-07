from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import School
from students.models import Student

from .models import Family, FamilyStudent
from .services import create_or_update_parent_family_for_student, update_family_identity


class ParentPortalPermissionsTests(TestCase):
    def setUp(self):
        self.parent = User.objects.create_user(username="parent_test", password="pass12345")
        self.staff = User.objects.create_user(username="staff_test", password="pass12345", is_staff=True)
        self.school = School.objects.create(name="Test School")
        self.family = Family.objects.create(user=self.parent, school=self.school, guardian_name="Parent")

    def test_parent_root_redirects_to_portal(self):
        self.client.force_login(self.parent)
        response = self.client.get("/")
        self.assertRedirects(response, reverse("parent_portal:dashboard"), fetch_redirect_response=False)

    def test_parent_cannot_open_admin_or_management_routes(self):
        self.client.force_login(self.parent)
        for path in ("/admin/", "/accounting/", "/students/"):
            response = self.client.get(path)
            self.assertRedirects(response, reverse("parent_portal:dashboard"), fetch_redirect_response=False)
        # The private development center is denied by the superuser gate before
        # the ordinary parent-portal redirect middleware can handle the route.
        self.assertEqual(self.client.get("/development/").status_code, 403)

    def test_unlinked_user_cannot_open_parent_portal(self):
        other = User.objects.create_user(username="other", password="pass12345")
        self.client.force_login(other)
        response = self.client.get(reverse("parent_portal:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_staff_is_not_confined_to_parent_portal(self):
        self.client.force_login(self.staff)
        response = self.client.get("/admin/")
        self.assertNotEqual(response.status_code, 302)


class ParentFamilyConsolidationTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة أولياء الأمور", is_active=True)

    def test_existing_family_without_user_is_repaired_and_children_share_it(self):
        family = Family.objects.create(
            school=self.school,
            guardian_name="ولي الاختبار",
            phone="0791112233",
        )
        first = Student.objects.create(
            student_number="PF-1",
            full_name="الطالب الأول",
            grade="الأول",
            guardian_name="ولي الاختبار",
            phone="0791112233",
        )
        second = Student.objects.create(
            student_number="PF-2",
            full_name="الطالب الثاني",
            grade="الثاني",
            guardian_name="ولي الاختبار",
            phone="0791112233",
        )

        first_family = create_or_update_parent_family_for_student(
            first,
            guardian_name="ولي الاختبار",
            phone="0791112233",
            school=self.school,
        )
        second_family = create_or_update_parent_family_for_student(
            second,
            guardian_name="ولي الاختبار",
            phone="0791112233",
            school=self.school,
        )

        family.refresh_from_db()
        self.assertEqual(first_family.pk, family.pk)
        self.assertEqual(second_family.pk, family.pk)
        self.assertIsNotNone(family.user_id)
        self.assertEqual(
            set(FamilyStudent.objects.filter(family=family).values_list("student_id", flat=True)),
            {first.pk, second.pk},
        )

    def test_same_name_without_identifier_does_not_merge_unrelated_families(self):
        first = Student.objects.create(student_number="NAME-1", full_name="الأول", grade="الأول")
        second = Student.objects.create(student_number="NAME-2", full_name="الثاني", grade="الأول")
        first_family = create_or_update_parent_family_for_student(
            first, guardian_name="محمد أحمد", phone="0791111111", school=self.school
        )
        second_family = create_or_update_parent_family_for_student(
            second, guardian_name="محمد أحمد", phone="0792222222", school=self.school
        )
        self.assertNotEqual(first_family.pk, second_family.pk)

    def test_family_is_single_parent_identity_source_for_student_copies(self):
        student = Student.objects.create(
            student_number="SYNC-1",
            full_name="طالب المزامنة",
            grade="الأول",
            guardian_name="قديم",
            phone="0790000000",
        )
        family = create_or_update_parent_family_for_student(
            student, guardian_name="قديم", phone="0790000000", school=self.school
        )
        update_family_identity(
            family,
            guardian_name="الاسم الرسمي",
            phone="0799999999",
            national_id="PARENT-1",
        )
        student.refresh_from_db()
        family.refresh_from_db()
        self.assertEqual(student.guardian_name, "الاسم الرسمي")
        self.assertEqual(student.phone, "0799999999")
        self.assertEqual(family.identity_number, "PARENT1")
