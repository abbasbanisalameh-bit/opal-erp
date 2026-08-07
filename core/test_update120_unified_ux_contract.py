from pathlib import Path
import re

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = ROOT / "templates" / "base" / "base.html"
DASHBOARD_TEMPLATE = ROOT / "dashboard" / "templates" / "dashboard" / "home.html"
GLOBAL_JS = ROOT / "static" / "js" / "opal_erp.js"
GLOBAL_CSS = ROOT / "static" / "css" / "opal_erp.css"


class Update120UnifiedUxContractTests(SimpleTestCase):
    def test_base_exposes_one_global_progress_and_live_status_region(self):
        source = BASE_TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(source.count('id="opal-navigation-progress"'), 1)
        self.assertEqual(source.count('id="opal-ux-status"'), 1)
        self.assertIn('aria-live="polite"', source)

    def test_post_forms_have_global_duplicate_submission_guard(self):
        source = GLOBAL_JS.read_text(encoding="utf-8")
        self.assertIn("OPAL Update 120: Unified interaction feedback", source)
        self.assertIn('form.dataset.opalSubmitting === "1"', source)
        self.assertIn('event.preventDefault()', source)
        self.assertIn('method === "get"', source)
        self.assertIn("opal-form-submitting", source)
        self.assertIn("جارٍ التنفيذ", source)

    def test_back_navigation_and_table_search_state_are_preserved(self):
        source = GLOBAL_JS.read_text(encoding="utf-8")
        self.assertIn("opal:scroll:", source)
        self.assertIn("back_forward", source)
        self.assertIn("opal:table-search:", source)
        self.assertIn("opal-table-search-clear", source)

    def test_empty_tables_receive_a_consistent_non_destructive_state(self):
        script = GLOBAL_JS.read_text(encoding="utf-8")
        styles = GLOBAL_CSS.read_text(encoding="utf-8")
        self.assertIn("installEmptyStates", script)
        self.assertIn("opal-empty-state", script)
        self.assertIn(".opal-empty-state", styles)
        self.assertIn("ستظهر البيانات هنا تلقائيًا عند توفرها", script)

    def test_executive_kpis_link_only_to_canonical_gateways(self):
        source = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn("data-opal-card-link", source)
        anchors = re.findall(r'<a\b[^>]*class="[^"]*\bopal-kpi-[^"]*"[^>]*>', source)
        self.assertEqual(len(anchors), 6)
        for route in (
            "students:student_list",
            "academics:academic_structure",
            "accounting:dashboard",
        ):
            self.assertIn("{% url '" + route + "' %}", source)
        for direct_operation in (
            "teachers:dashboard",
            "attendance_v2:dashboard",
            "exams:exam_dashboard",
            "admissions:fee_payment_create",
        ):
            if 'class="opal-manager-quick-row"' in source:
                kpi_start = source.index('class="opal-manager-quick-row"')
                kpi_end = source.index("</nav>", kpi_start)
            else:
                kpi_start = source.index('class="dashboard-grid opal-executive-kpis"')
                kpi_end = source.index("</section>", kpi_start)
            self.assertNotIn(direct_operation, source[kpi_start:kpi_end])
        self.assertIn("{% url 'enterprise_ops:feedback_list' %}", source)
        self.assertNotIn("{% url 'enterprise_ops:workflow_list' %}", source)
        workflow_catalog = (ROOT / "core" / "workflow_catalog.py").read_text(encoding="utf-8")
        self.assertIn("enterprise_ops:workflow_list", workflow_catalog)

    def test_interaction_layer_is_keyboard_and_motion_safe(self):
        script = GLOBAL_JS.read_text(encoding="utf-8")
        styles = GLOBAL_CSS.read_text(encoding="utf-8")
        self.assertIn('event.key !== "Enter"', script)
        self.assertIn('event.key !== " "', script)
        self.assertIn("prefers-reduced-motion", styles)
        self.assertIn("focus-visible", styles)
