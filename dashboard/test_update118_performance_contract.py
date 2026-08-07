from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "dashboard" / "workflow.py"
PERFORMANCE_COMMAND = ROOT / "core" / "management" / "commands" / "audit_runtime_performance.py"
PERFORMANCE_HELPERS = ROOT / "core" / "performance_audit.py"


class Update118PerformanceContractTests(SimpleTestCase):
    def test_compact_dashboard_skips_non_rendered_heavy_blocks(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        dashboard_block = source[source.index("def build_dashboard_context"):source.index("def build_executive_export_rows")]
        self.assertIn("include_secondary_metrics=False", dashboard_block)
        self.assertIn("include_financial_watch=False", dashboard_block)
        self.assertIn("include_attendance_watch=False", dashboard_block)

    def test_full_snapshot_contract_remains_the_default(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("include_secondary_metrics=True", source)
        self.assertIn("include_financial_watch=True", source)
        self.assertIn("include_attendance_watch=True", source)
        self.assertIn('IssuedDocument.objects.filter(', source)
        self.assertIn('if include_secondary_metrics and academic_year is not None else 0', source)

    def test_audit_uses_get_requests_and_signed_cookie_authentication(self):
        source = PERFORMANCE_COMMAND.read_text(encoding="utf-8")
        self.assertIn("client.get(url, follow=False)", source)
        self.assertNotIn("client.post(", source)
        self.assertIn('SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies"', source)
        self.assertIn("_authenticate_client_without_database_write", source)

    def test_sql_values_are_normalized_before_reports(self):
        source = PERFORMANCE_HELPERS.read_text(encoding="utf-8")
        self.assertIn("normalize_sql", source)
        self.assertIn("_STRING_LITERAL_RE.sub", source)
        self.assertIn("n_plus_one_suspected", source)
