from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from config.runtime_registry import build_context_processors
from core.runtime_contracts import (
    audit_base_template_contract,
    audit_canonical_navigation_routes,
    audit_runtime_context_registry,
    run_runtime_stability_audit,
)


class Update122FinalStabilityContractTests(SimpleTestCase):
    def test_runtime_processors_are_unique_and_identity_precedes_live_schedule(self):
        processors = build_context_processors()
        self.assertEqual(len(processors), len(set(processors)))
        self.assertLess(
            processors.index("core.context_processors.opal_identity"),
            processors.index("timetable.context_processors.live_schedule"),
        )
        self.assertEqual(audit_runtime_context_registry(), [])

    def test_global_shell_assets_and_includes_are_canonical(self):
        self.assertEqual(audit_base_template_contract(), [])

    def test_enabled_operations_and_gateways_resolve(self):
        self.assertEqual(audit_canonical_navigation_routes(), [])

    def test_runtime_audit_is_read_only_and_stable(self):
        report = run_runtime_stability_audit()
        self.assertEqual(set(report), {"ok", "checks", "issue_count", "issues"})
        self.assertTrue(report["ok"])

    def test_live_schedule_reuses_request_scoped_school(self):
        source = (Path(settings.BASE_DIR) / "timetable/context_processors.py").read_text(encoding="utf-8")
        self.assertIn("request_school(request)", source)
        self.assertNotIn("School.objects.filter", source)
