from types import SimpleNamespace

from django.test import SimpleTestCase

from students.student360 import _build_student_alerts_and_risk


class StudentAlertsRiskProfileContractTests(SimpleTestCase):
    def test_builds_expected_high_risk_alerts(self):
        student = SimpleNamespace(source="openemis", national_id="")
        profile = _build_student_alerts_and_risk(
            student,
            current_enrollment=None,
            family=None,
            finance={"total": 1000, "remaining": 600},
            attendance={"total": 10, "rate": 70},
            marks_profile={"marks": [object()], "percentage_average": 55},
        )
        self.assertEqual(profile["risk"], {"label": "مرتفع", "class": "danger", "score": 8})
        self.assertEqual(len(profile["alerts"]), 6)

    def test_builds_stable_low_risk_result(self):
        student = SimpleNamespace(source="manual", national_id="123")
        profile = _build_student_alerts_and_risk(
            student,
            current_enrollment=object(),
            family=object(),
            finance={"total": 1000, "remaining": 0},
            attendance={"total": 10, "rate": 95},
            marks_profile={"marks": [object()], "percentage_average": 90},
        )
        self.assertEqual(profile["alerts"], [])
        self.assertEqual(profile["risk"], {"label": "منخفض", "class": "success", "score": 0})
