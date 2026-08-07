from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class Update1311PostConsolidationStabilityContractTests(unittest.TestCase):
    def test_global_context_processors_do_not_run_operational_writes(self):
        notifications = source("enterprise_ops/context_processors.py")
        self.assertNotIn("sync_attendance_registers", notifications)
        for token in (
            ".save(", ".create(", ".update(", ".delete(",
            "get_or_create(", "update_or_create(", "bulk_create(",
        ):
            self.assertNotIn(token, notifications)

    def test_management_topbar_uses_compact_school_status(self):
        context = source("timetable/context_processors.py")
        self.assertIn("school_live_status", context)
        self.assertNotIn("management_live_status", context)
        self.assertIn("teacher_live_status", context)

    def test_teacher_management_pages_are_school_scoped(self):
        views = source("teachers/views.py")
        self.assertIn("school = request_school(request)", views)
        self.assertIn("Teacher.objects.filter(school=school)", views)
        self.assertIn("teacher__school=school", views)
        self.assertIn("assignments__academic_year__is_current=True", views)

    def test_tpi_is_read_only_on_get_and_explicit_on_post(self):
        views = source("teachers/views.py")
        dashboard = views[views.index("def dashboard"):views.index("def teacher_list")]
        self.assertIn("management_tpi_snapshot_context", dashboard)
        self.assertIn('request.method == "POST"', dashboard)
        self.assertIn('request.POST.get("action") == "refresh_tpi"', dashboard)
        self.assertIn("management_tpi_context(school=school)", dashboard)

        portal = views[views.index("def portal_dashboard"):views.index("def portal_workspace")]
        self.assertIn("teacher_tpi_snapshot_context", portal)
        self.assertNotIn("teacher_tpi_context(", portal)

    def test_tpi_snapshot_readers_do_not_call_refresh_writer(self):
        tpi = source("teachers/tpi.py")
        management = tpi[
            tpi.index("def management_tpi_snapshot_context"):
            tpi.index("def teacher_tpi_snapshot_context")
        ]
        teacher = tpi[
            tpi.index("def teacher_tpi_snapshot_context"):
            tpi.index("def teacher_tpi_context")
        ]
        for block in (management, teacher):
            self.assertNotIn("refresh_school_open_tpi", block)
            self.assertNotIn("calculate_open_snapshot", block)
            self.assertNotRegex(block, re.compile(r"\.save\(|get_or_create\(|update_or_create\("))

    def test_stability_system_check_is_registered(self):
        checks = source("core/checks.py")
        self.assertIn("run_post_consolidation_stability_audit", checks)
        self.assertIn('id="opal.E131"', checks)


if __name__ == "__main__":
    unittest.main()
