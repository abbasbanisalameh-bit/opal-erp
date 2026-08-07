import json
from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class AestheticFinishingContractTests(SimpleTestCase):
    def test_accessible_page_landmarks_are_single_and_linked(self):
        base = source("templates/base/base.html")
        self.assertEqual(base.count('class="opal-skip-link"'), 1)
        self.assertIn('href="#opal-main-content"', base)
        self.assertEqual(base.count('id="opal-main-content"'), 1)
        self.assertEqual(base.count('id="opal-scroll-top"'), 1)
        self.assertIn('aria-label="العودة إلى أعلى الصفحة"', base)

    def test_finishing_layer_covers_theme_motion_and_contrast(self):
        styles = source("static/css/opal_theme_system.css")
        for token in (
            "OPAL Update 131.7 R10 — aesthetic finishing touches",
            ".opal-skip-link",
            ".opal-main > .page-heading",
            ".opal-scroll-top",
            "prefers-reduced-motion:reduce",
            "prefers-contrast:more",
            "body.opal-keyboard-open .opal-scroll-top",
        ):
            self.assertIn(token, styles)

    def test_scroll_helper_is_local_progressive_enhancement_only(self):
        script = source("static/js/opal_erp.js")
        block = script.split("OPAL Update 131.7 R10: aesthetic finishing touches", 1)[1]
        self.assertIn('document.getElementById("opal-scroll-top")', block)
        self.assertIn("window.requestAnimationFrame", block)
        self.assertIn("prefers-reduced-motion: reduce", block)
        self.assertIn("window.scrollTo", block)
        self.assertNotIn("fetch(", block)
        self.assertNotIn("XMLHttpRequest", block)

    def test_release_remains_code_only_and_uses_one_cache_identity(self):
        manifest = json.loads(source("OPAL_UPDATE_MANIFEST.json"))
        base = source("templates/base/base.html")
        self.assertEqual(manifest["version"], "131.7")
        self.assertGreaterEqual(manifest["package_revision"], 13)
        self.assertTrue(manifest["code_only"])
        self.assertRegex(manifest["version_name"], r"OPAL Update 131\.7 R\d+ - .+")
        self.assertGreaterEqual(base.count("update1317-r10-aesthetic-finishing"), 5)
