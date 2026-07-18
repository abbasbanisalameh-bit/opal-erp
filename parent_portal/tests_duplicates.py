from django.contrib.auth.models import User
from django.test import TestCase

from core.models import School
from students.models import Student

from .duplicate_services import guardian_duplicate_groups, merge_guardian_group
from .models import Family, FamilyStudent


class GuardianDuplicateMergeTests(TestCase):
    def test_phone_match_is_reviewed_and_merged_without_deleting_history(self):
        school = School.objects.create(name="مدرسة الدمج")
        user = User.objects.create_user("merge-manager", password="x", is_staff=True)
        first = Family.objects.create(school=school, guardian_name="ولي واحد", phone="0791111111")
        second = Family.objects.create(school=school, guardian_name="ولي واحد مكرر", phone="0791111111")
        child1 = Student.objects.create(student_number="M-1", full_name="الابن الأول", grade="الأول")
        child2 = Student.objects.create(student_number="M-2", full_name="الابن الثاني", grade="الثاني")
        FamilyStudent.objects.create(family=first, student=child1)
        FamilyStudent.objects.create(family=second, student=child2)

        groups = guardian_duplicate_groups()
        self.assertEqual(len(groups), 1)
        canonical, count = merge_guardian_group(
            family_ids=[first.pk, second.pk], canonical_id=first.pk, user=user,
        )
        self.assertEqual(count, 1)
        second.refresh_from_db()
        self.assertFalse(second.is_active)
        self.assertEqual(second.merged_into_id, canonical.pk)
        self.assertEqual(set(canonical.children.filter(is_active=True).values_list("student_id", flat=True)), {child1.pk, child2.pk})
        self.assertTrue(Family.objects.filter(pk=second.pk).exists())

    def test_same_name_alone_is_never_a_duplicate_group(self):
        school = School.objects.create(name="مدرسة الأسماء")
        Family.objects.create(school=school, guardian_name="اسم متشابه", phone="0791000001")
        Family.objects.create(school=school, guardian_name="اسم متشابه", phone="0791000002")
        self.assertEqual(guardian_duplicate_groups(), [])
