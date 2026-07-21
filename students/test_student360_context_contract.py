from django.test import SimpleTestCase

from students.student360 import _assemble_student_360_context


class Student360ContextContractTests(SimpleTestCase):
    def test_context_keys_and_values_remain_stable(self):
        student = object()
        context = _assemble_student_360_context(
            student,
            academic_profile={"enrollments": ["enrollment"], "current_enrollment": "current"},
            family_profile={
                "family": "family",
                "family_link": "family-link",
                "siblings": ["sibling"],
                "guardian_links": ["guardian-link"],
            },
            invoices=["invoice"],
            payments=["payment"],
            allocations=["allocation"],
            finance={"total": 100},
            attendance={
                "recent": ["attendance"],
                "counts": {"present": 1},
                "total": 1,
                "rate": 100.0,
                "absent_count": 0,
                "late_count": 0,
            },
            marks_profile={"marks": ["mark"], "summary": {"count": 1}, "percentage_average": 90.0},
            documents_profile={"documents": ["document"]},
            timetable=["entry"],
            alert_profile={"alerts": ["alert"], "risk": {"label": "منخفض"}},
            data_completeness=88,
            activity_timeline=["event"],
        )
        self.assertIs(context["student"], student)
        self.assertEqual(context["current_enrollment"], "current")
        self.assertEqual(context["attendance_rate"], 100.0)
        self.assertEqual(context["percentage_average"], 90.0)
        self.assertEqual(context["data_completeness"], 88)
        self.assertEqual(len(context), 26)

    def test_context_public_key_set_is_preserved(self):
        expected = {
            "student", "enrollments", "current_enrollment", "family", "family_link",
            "siblings", "guardian_links", "invoices", "payments", "allocations", "finance",
            "attendance_recent", "attendance_counts", "attendance_total", "attendance_rate",
            "absent_count", "late_count", "marks", "mark_summary", "percentage_average",
            "documents", "timetable", "alerts", "risk", "data_completeness", "activity_timeline",
        }
        context = _assemble_student_360_context(
            object(),
            academic_profile={"enrollments": [], "current_enrollment": None},
            family_profile={"family": None, "family_link": None, "siblings": [], "guardian_links": []},
            invoices=[], payments=[], allocations=[], finance={},
            attendance={"recent": [], "counts": {}, "total": 0, "rate": 0, "absent_count": 0, "late_count": 0},
            marks_profile={"marks": [], "summary": {}, "percentage_average": 0},
            documents_profile={"documents": []}, timetable=[],
            alert_profile={"alerts": [], "risk": {}}, data_completeness=0, activity_timeline=[],
        )
        self.assertEqual(set(context), expected)
