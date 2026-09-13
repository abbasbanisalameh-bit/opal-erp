from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = ROOT / "templates" / "base" / "base.html"
GLOBAL_JS = ROOT / "static" / "js" / "opal_erp.js"
GLOBAL_CSS = ROOT / "static" / "css" / "opal_erp.css"


class Update121MobileExperienceContractTests(SimpleTestCase):
    def test_base_cache_identity_uses_the_current_release(self):
        source = BASE_TEMPLATE.read_text(encoding="utf-8")
        self.assertRegex(source, r"opal_theme_system\.css' %\}\?v=[^\"\s]+")
        self.assertRegex(source, r"opal_erp\.js' %\}\?v=[^\"\s]+")

    def test_simple_tables_are_decorated_with_real_header_labels(self):
        source = GLOBAL_JS.read_text(encoding="utf-8")
        self.assertIn("OPAL Update 121: Mobile-first operational experience", source)
        self.assertIn("decorateTable", source)
        self.assertIn("cell.dataset.opalLabel = label", source)
        self.assertIn("opal-mobile-card-table", source)
        self.assertIn("opal-mobile-actions-cell", source)

    def test_complex_tables_keep_horizontal_scroll_fallback(self):
        source = GLOBAL_JS.read_text(encoding="utf-8")
        self.assertIn("markScrollableTable", source)
        self.assertIn("opal-mobile-scroll-hint", source)
        self.assertIn("اسحب أفقيًا لعرض بقية الجدول", source)
        self.assertIn("rowspan", source)
        self.assertIn("colspan", source)

    def test_visual_viewport_and_keyboard_are_handled_safely(self):
        source = GLOBAL_JS.read_text(encoding="utf-8")
        styles = GLOBAL_CSS.read_text(encoding="utf-8")
        self.assertIn("window.visualViewport", source)
        self.assertIn("--opal-visual-viewport-height", source)
        self.assertIn("opal-keyboard-open", source)
        self.assertIn("body.opal-keyboard-open .opal-mobile-action-dock", styles)

    def test_phone_layout_has_touch_targets_and_card_tables(self):
        styles = GLOBAL_CSS.read_text(encoding="utf-8")
        self.assertIn("OPAL Update 121: mobile-first operational experience", styles)
        self.assertIn("@media (max-width: 575px)", styles)
        self.assertIn("min-height: 44px", styles)
        self.assertIn("table.opal-mobile-card-table tbody td::before", styles)
        self.assertIn("content: attr(data-opal-label)", styles)
        self.assertIn(".opal-mobile-action-dock", styles)

    def test_mobile_layer_does_not_add_a_parallel_backend(self):
        source = GLOBAL_JS.read_text(encoding="utf-8")
        self.assertNotIn("fetch(", source[source.index("OPAL Update 121:"):])
        self.assertNotIn("XMLHttpRequest", source[source.index("OPAL Update 121:"):])
