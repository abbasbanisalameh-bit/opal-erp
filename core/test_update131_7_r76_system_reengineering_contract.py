from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]


class R76SystemReengineeringContractTests(SimpleTestCase):
    def test_module_registry_is_canonical_and_ui_governance_is_loaded_once(self):
        registry = (ROOT / "core" / "module_registry.py").read_text(encoding="utf-8")
        base = (ROOT / "templates" / "base" / "base.html").read_text(encoding="utf-8")
        sidebar = (ROOT / "templates" / "includes" / "sidebar.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "js" / "opal_ui_r76.js").read_text(encoding="utf-8")
        theme = (ROOT / "static" / "css" / "opal_theme_system.css").read_text(encoding="utf-8")
        self.assertIn("from .workflow_catalog import MODULES", registry)
        self.assertEqual(base.count('opal_ui_r76.js'), 1)
        self.assertIn('data-opal-module', sidebar)
        self.assertIn('removeAttribute("title")', js)
        self.assertIn("OPAL Update 131.7 R76", theme)

    def test_global_shell_remains_single_path(self):
        base = (ROOT / "templates" / "base" / "base.html").read_text(encoding="utf-8")
        self.assertEqual(base.count('{% include "includes/sidebar.html" %}'), 1)
        self.assertEqual(base.count('{% include "includes/topbar.html" %}'), 1)
