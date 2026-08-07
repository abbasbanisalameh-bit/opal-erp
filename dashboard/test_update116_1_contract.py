from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]
EXECUTIVE_CSS = ROOT / "static" / "css" / "opal_dashboard_executive.css"
BASE_TEMPLATE = ROOT / "templates" / "base" / "base.html"


class Update1161KpiThemePersistenceContractTests(SimpleTestCase):
    def test_kpi_accents_survive_theme_body_class_initialization(self):
        source = EXECUTIVE_CSS.read_text(encoding="utf-8")
        self.assertIn("OPAL Update 116.1 — persist KPI accents", source)
        self.assertIn('html[data-opal-theme] body .opal-main .opal-executive-kpis .dashboard-card[class*="opal-kpi-"]', source)
        self.assertIn("background:var(--opal-kpi-bg)!important", source)
        self.assertIn("border-color:var(--opal-kpi-border)!important", source)

    def test_each_executive_kpi_defines_one_accent_source(self):
        source = EXECUTIVE_CSS.read_text(encoding="utf-8")
        for name in (
            "opal-kpi-students",
            "opal-kpi-teachers",
            "opal-kpi-attendance",
            "opal-kpi-collection",
            "opal-kpi-outstanding",
            "opal-kpi-success",
        ):
            rule_start = source.index(f".{name}")
            rule_end = source.index("}", rule_start)
            rule = source[rule_start:rule_end]
            self.assertIn("--opal-kpi-bg:", rule)
            self.assertIn("--opal-kpi-border:", rule)

    def test_cache_key_points_to_update_116_1(self):
        source = BASE_TEMPLATE.read_text(encoding="utf-8")
        self.assertRegex(source, r"opal_dashboard_executive\.css' %\}\?v=[^\"\s]+")
