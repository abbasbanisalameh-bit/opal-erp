from django.contrib.auth import get_user_model
from django.test import SimpleTestCase

from .workflow import build_executive_export_rows, is_management_user


class DashboardWorkflowContractTests(SimpleTestCase):
    def test_management_access_contract_is_preserved(self):
        user = get_user_model()(is_staff=True)
        self.assertTrue(is_management_user(user))
        normal = get_user_model()(is_staff=False, is_superuser=False)
        self.assertFalse(is_management_user(normal))

    def test_export_contract_keeps_expected_indicators(self):
        snapshot = {
            "today": "2026-07-21",
            "students_count": 10,
            "active_students": 9,
            "teachers_count": 4,
            "sections_count": 3,
            "attendance_percent": 95,
            "period_absences": 2,
            "period_late": 1,
            "total_invoices": 100,
            "paid_amount": 70,
            "outstanding": 30,
            "collection_rate": 70,
            "overdue_invoices": 1,
            "academic_average": 80,
            "pass_rate": 90,
            "issued_documents": 5,
        }
        rows = build_executive_export_rows(snapshot)
        labels = [label for label, _value in rows]
        self.assertEqual(len(rows), 16)
        self.assertIn("إجمالي الطلاب", labels)
        self.assertIn("إجمالي التحصيل", labels)
        self.assertIn("نسبة النجاح", labels)
