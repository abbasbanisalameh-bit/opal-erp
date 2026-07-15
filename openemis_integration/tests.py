from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from academics.models import Enrollment, Grade
from attendance_v2.models import Attendance
from core.models import AcademicYear, School
from exams.models import StudentMark
from parent_portal.models import Family, FamilyStudent
from students.models import Student
from teachers.models import Teacher

from .services import import_openemis_payload, upsert_student_from_openemis


class OpenEMISCanonicalImportTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="مدرسة OpenEMIS", is_active=True)
        self.year = AcademicYear.objects.create(
            school=self.school,
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )
        Grade.objects.create(school=self.school, name="الأول", order=1)

    def payload(self):
        return {
            "students": [
                {
                    "student": {
                        "student_number": "OEM-100",
                        "ministry_student_id": "وزارة-١٠٠",
                        "national_id": "ST-١٠٠",
                        "full_name": "طالب الوزارة",
                        "father_name": "الأب",
                        "mother_name": "الأم",
                        "status": "active",
                    },
                    "guardian": {
                        "name": "ولي الوزارة",
                        "identity_type": "national",
                        "identity_number": "ولي-١٠٠",
                        "phone": "0791234567",
                        "email": "parent@example.com",
                    },
                    "enrollment": {
                        "academic_year": "2026/2027",
                        "grade": "الأول",
                        "section": "أ",
                        "branch": "الرئيسي",
                        "status": "active",
                    },
                    "attendance": [
                        {"date": "2026-09-10", "status": "present", "notes": "قادمة من الوزارة"}
                    ],
                    "marks": [
                        {
                            "academic_year": "2026/2027",
                            "semester": "first",
                            "grade": "الأول",
                            "subject": "الرياضيات",
                            "exam_type": "first",
                            "max_mark": "100",
                            "mark": "80",
                        }
                    ],
                    "unknown_openemis_field": {"preserved": True},
                }
            ],
            "teachers": [
                {
                    "employee_number": "OEM-T-1",
                    "ministry_teacher_id": "TEACH-١",
                    "national_id": "T-NID-١",
                    "full_name": "معلم الوزارة",
                    "branch": "الرئيسي",
                    "is_active": True,
                    "custom_ministry_field": "kept",
                }
            ],
        }

    def test_repeated_import_updates_canonical_records_without_duplicates(self):
        first = import_openemis_payload(self.payload())
        second = import_openemis_payload(self.payload())

        self.assertEqual(first["students_created"], 1)
        self.assertEqual(second["students_updated"], 1)
        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(Teacher.objects.count(), 1)
        self.assertEqual(Family.objects.count(), 1)
        self.assertEqual(FamilyStudent.objects.filter(is_active=True).count(), 1)
        self.assertEqual(Enrollment.objects.filter(status="active").count(), 1)
        self.assertEqual(Attendance.objects.count(), 1)
        self.assertEqual(StudentMark.objects.count(), 1)

        student = Student.objects.get()
        teacher = Teacher.objects.get()
        family = Family.objects.get()
        mark = StudentMark.objects.get()
        self.assertEqual(student.ministry_student_id, "وزارة100")
        self.assertEqual(student.national_id, "ST100")
        self.assertEqual(student.source, "openemis")
        self.assertTrue(student.openemis_data["unknown_openemis_field"]["preserved"])
        self.assertEqual(family.identity_number, "ولي100")
        self.assertEqual(family.source, "openemis")
        self.assertEqual(teacher.ministry_teacher_id, "TEACH1")
        self.assertEqual(teacher.source, "openemis")
        self.assertEqual(teacher.openemis_data["custom_ministry_field"], "kept")
        # 80/100 is converted to the official first-exam maximum 20.
        self.assertEqual(mark.mark, Decimal("16.00"))
        self.assertEqual(mark.exam.max_mark, Decimal("20.00"))

    def test_conflicting_official_identifiers_are_rejected(self):
        first = Student.objects.create(
            student_number="CONFLICT-1",
            ministry_student_id="MIN1",
            full_name="الأول",
            grade="الأول",
        )
        second = Student.objects.create(
            student_number="CONFLICT-2",
            national_id="NID2",
            full_name="الثاني",
            grade="الأول",
        )
        with self.assertRaises(ValidationError):
            upsert_student_from_openemis(
                {
                    "student": {
                        "ministry_student_id": first.ministry_student_id,
                        "national_id": second.national_id,
                        "full_name": "سجل متعارض",
                    }
                }
            )
