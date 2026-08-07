from pathlib import Path
import re

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_TEMPLATE = ROOT / "dashboard" / "templates" / "dashboard" / "home.html"
EXECUTIVE_CSS = ROOT / "static" / "css" / "opal_dashboard_executive.css"
POLISH_CSS = ROOT / "static" / "css" / "opal_dashboard_polish.css"
BASE_TEMPLATE = ROOT / "templates" / "base" / "base.html"


class Update116ExecutiveDashboardContractTests(SimpleTestCase):
    def test_removed_kpis_do_not_return_to_executive_row(self):
        source = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
        if 'class="opal-manager-quick-row"' in source:
            kpi_start = source.index('class="opal-manager-quick-row"')
            kpi_end = source.index("</nav>", kpi_start)
        else:
            kpi_start = source.index('class="dashboard-grid opal-executive-kpis"')
            kpi_end = source.index("</section>", kpi_start)
        kpi_source = source[kpi_start:kpi_end]
        self.assertNotIn("الوثائق المصدرة", kpi_source)
        self.assertNotIn("امتحانات النظام", kpi_source)
        anchors = re.findall(r'<a\b[^>]*class="[^"]*\bopal-kpi-[^"]*"[^>]*>', kpi_source)
        self.assertEqual(len(anchors), 6)

    def test_requested_dashboard_order_is_explicit(self):
        source = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
        positions = [
            source.index("opal-manager-quick-row"),
            source.index("opal-teacher-performance-row"),
            source.index("opal-top-students-panel"),
            source.index("opal-satisfaction-fixed"),
            source.index("مصادر التقييم وملخص المتابعة"),
            source.index("الإيرادات والمتأخرون عن السداد"),
            source.index("المعلمون المشغولون والمتفرغون"),
            source.index("opal-live-operation-title"),
            source.index("opal-actions-fixed-row"),
            source.index("غياب الطلبة والمعلمين اليوم"),
            source.index("opal-latest-students-title"),
        ]
        self.assertEqual(positions, sorted(positions))

    def test_six_kpis_stay_in_one_row_and_have_distinct_visual_classes(self):
        source = EXECUTIVE_CSS.read_text(encoding="utf-8")
        self.assertIn("grid-template-columns:repeat(6,minmax(0,1fr))!important", source)
        for name in (
            "opal-kpi-students",
            "opal-kpi-teachers",
            "opal-kpi-attendance",
            "opal-kpi-collection",
            "opal-kpi-outstanding",
            "opal-kpi-success",
        ):
            self.assertIn(f".{name}", source)

    def test_announcement_uses_gold_text_and_multicolour_icon_only(self):
        source = POLISH_CSS.read_text(encoding="utf-8")
        self.assertIn("OPAL Update 116 — announcement text only in gold", source)
        self.assertIn("color:#e7bd54!important", source)
        self.assertIn("linear-gradient(135deg,#38bdf8", source)
        self.assertNotIn(".opal-topbar-ribbon{background:linear-gradient", source)

    def test_static_cache_keys_point_to_update_116(self):
        source = BASE_TEMPLATE.read_text(encoding="utf-8")
        self.assertRegex(source, r"opal_dashboard_polish\.css' %\}\?v=[^\"\s]+")
        self.assertRegex(source, r"opal_dashboard_executive\.css' %\}\?v=[^\"\s]+")
