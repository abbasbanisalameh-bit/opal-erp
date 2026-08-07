from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Update1314LiveEventsMatrixContractTests(unittest.TestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_dashboard_uses_three_row_horizontal_matrix(self):
        template = self.source("dashboard/templates/dashboard/home.html")
        self.assertIn("opal_live_schedule.grade_columns", template)
        self.assertIn('colspan="{{ column.section_count }}"', template)
        self.assertIn("opal-live-grade-row", template)
        self.assertIn("opal-live-section-row", template)
        self.assertIn("opal-live-event-row", template)
        self.assertIn(">الصف<", template)
        self.assertIn(">الشعبة<", template)
        self.assertIn(">الحدث الجاري<", template)
        self.assertIn("item.short_name", template)
        self.assertIn("item.label", template)

    def test_each_section_keeps_its_own_live_state(self):
        service = self.source("timetable/live_services.py")
        self.assertIn('"grade_columns": grade_columns', service)
        self.assertIn('"sections": values', service)
        self.assertIn('"section_count": len(values)', service)
        self.assertIn('"short_name": short_name or section.name', service)
        self.assertIn('"state_code": state_code', service)
        self.assertNotIn("أحداث مختلفة بين الشعب", service)

    def test_operating_states_are_explicit(self):
        service = self.source("timetable/live_services.py")
        self.assertIn('"state": "no_schedule"', service)
        self.assertIn('"لم يبدأ الدوام"', service)
        self.assertIn('"بين حدثين"', service)
        self.assertIn('"خارج وقت الدوام"', service)
        self.assertIn('teacher_state_active = base.get("state") in {"active", "between"}', service)
        self.assertIn("time-slot definitions must not invent a school day", service)
        self.assertNotIn("entry_slots = list(TimeSlot.objects.filter(is_active=True", service)

    def test_official_clock_and_boundary_refresh_are_deployed(self):
        template = self.source("dashboard/templates/dashboard/home.html")
        js = self.source("static/js/opal_erp.js")
        self.assertIn('data-opal-official-clock="time"', template)
        self.assertIn("opal_time_zone_label", template)
        self.assertIn("data-live-seconds", template)
        self.assertIn("function installLiveBoundaryRefresh()", js)
        self.assertIn("officialNow()", js)
        self.assertIn("nearestBoundary + 1", js)

    def test_mobile_matrix_has_fixed_axis_and_horizontal_scroll(self):
        css = self.source("static/css/opal_erp.css")
        self.assertIn("OPAL Update 131.4: live grade/section event matrix", css)
        self.assertIn(".opal-live-events-matrix-wrap", css)
        self.assertIn("overflow-x:auto", css)
        self.assertIn(".opal-live-events-matrix .opal-live-axis-cell", css)
        self.assertIn("position:sticky", css)
        self.assertIn("inset-inline-start:0", css)

    def test_runtime_gate_is_registered(self):
        checks = self.source("core/checks.py")
        contracts = self.source("core/live_events_matrix_contracts.py")
        self.assertIn("run_live_events_matrix_audit", checks)
        self.assertIn('id="opal.E134"', checks)
        self.assertIn("def run_live_events_matrix_audit", contracts)

    def test_no_parallel_page_model_or_route(self):
        models = self.source("timetable/models.py") + self.source("dashboard/models.py")
        self.assertNotIn("class LiveGradeEvent", models)
        self.assertFalse((ROOT / "dashboard" / "templates" / "dashboard" / "live_events.html").exists())
        urls = self.source("dashboard/urls.py")
        self.assertNotIn("live-events", urls)


if __name__ == "__main__":
    unittest.main()
