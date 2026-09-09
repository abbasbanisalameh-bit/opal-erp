import json
from pathlib import Path

from django.test import SimpleTestCase


class Update1317R42ContractTests(SimpleTestCase):
    def test_release_identity_is_r42_revision_50(self):
        root = Path(__file__).resolve().parent.parent
        manifest = json.loads((root / "OPAL_UPDATE_MANIFEST.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(manifest["package_revision"], 50)
        self.assertEqual((root / "OPAL_VERSION.txt").read_text(encoding="utf-8").strip(), "131.7")
        self.assertRegex((root / "OPAL_RELEASE_NAME.txt").read_text(encoding="utf-8"), r"R(?:42|43)")

    def test_transport_impersonation_uses_single_gateway(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "transport" / "views.py").read_text(encoding="utf-8")
        self.assertNotIn('redirect("transport:driver-transport-dashboard")', source)
        self.assertIn('redirect("transport:transport-dashboard")', source)

    def test_console_routes_and_template_exist(self):
        root = Path(__file__).resolve().parent.parent
        urls = (root / "core" / "urls.py").read_text(encoding="utf-8")
        template = (root / "templates" / "core" / "system_updates.html").read_text(encoding="utf-8")
        console = (root / "templates" / "core" / "system_console.html").read_text(encoding="utf-8")
        self.assertIn('name="system_console"', urls)
        self.assertIn('name="open_system_console"', urls)
        self.assertIn('name="run_system_console"', urls)
        self.assertIn("فتح كونسول", template)
        self.assertIn("console_id", console)
        self.assertIn("user-select:text", console)

    def test_console_does_not_create_second_system_updates_entry(self):
        root = Path(__file__).resolve().parent.parent
        template = (root / "templates" / "core" / "system_console.html").read_text(encoding="utf-8")
        self.assertNotIn("core:system_updates", template)
        self.assertIn("consoleBackButton", template)
