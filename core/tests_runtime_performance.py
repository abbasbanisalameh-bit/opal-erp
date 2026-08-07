import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.contrib.sessions.models import Session
from django.test import SimpleTestCase, TestCase

from core.performance_audit import compare_reports, normalize_sql, summarize_queries


class PerformanceAuditUtilityTests(SimpleTestCase):
    def test_sql_normalization_hides_live_values(self):
        sql = "SELECT * FROM students_student WHERE id = 42 AND full_name = 'طالب اختبار'"
        fingerprint = normalize_sql(sql)
        self.assertNotIn("42", fingerprint)
        self.assertNotIn("طالب اختبار", fingerprint)
        self.assertIn("id = ?", fingerprint)

    def test_duplicate_query_summary_detects_n_plus_one_pattern(self):
        queries = [
            {"sql": f"SELECT name FROM academics_grade WHERE id = {pk}", "time": "0.001"}
            for pk in range(1, 6)
        ]
        summary = summarize_queries(queries)
        self.assertEqual(summary["query_count"], 5)
        self.assertEqual(summary["duplicate_query_count"], 4)
        self.assertTrue(summary["n_plus_one_suspected"])

    def test_before_after_comparison_uses_matching_route_key(self):
        baseline = {"results": [{"key": "dashboard", "median_response_ms": 2000, "median_query_count": 40}]}
        current = {"results": [{"key": "dashboard", "label": "لوحة", "median_response_ms": 1000, "median_query_count": 20}]}
        comparison = compare_reports(current, baseline)
        self.assertEqual(comparison[0]["response_percent_change"], -50.0)
        self.assertEqual(comparison[0]["queries_delta"], -20.0)


class PerformanceAuditCommandTests(TestCase):
    def test_command_measures_read_only_dashboard_request(self):
        user_model = get_user_model()
        admin = user_model.objects.create_superuser(
            username="performance-admin",
            email="performance@example.com",
            password="StrongPass123!",
        )
        users_before = user_model.objects.count()
        sessions_before = Session.objects.count()
        last_login_before = admin.last_login
        output = StringIO()
        call_command(
            "audit_runtime_performance",
            username=admin.username,
            routes=["dashboard:home"],
            iterations=1,
            warmup=0,
            no_save=True,
            format="json",
            stdout=output,
        )
        report = json.loads(output.getvalue())
        self.assertTrue(report["read_only"])
        self.assertEqual(report["results"][0]["route"], "dashboard:home")
        self.assertEqual(user_model.objects.count(), users_before)
        self.assertEqual(Session.objects.count(), sessions_before)
        admin.refresh_from_db()
        self.assertEqual(admin.last_login, last_login_before)
