from pathlib import Path

from django.test import SimpleTestCase

from .single_entry_contracts import run_single_entry_contract_audit


ROOT = Path(__file__).resolve().parents[1]


class Update125SingleEntryContractTests(SimpleTestCase):
    def test_static_single_entry_contract_is_clean(self):
        report = run_single_entry_contract_audit(root=ROOT)
        self.assertTrue(report["ok"], report["issues"])

    def test_no_template_or_route_is_removed_by_the_contract(self):
        self.assertTrue((ROOT / "templates" / "core" / "operations_center.html").is_file())
        self.assertTrue((ROOT / "templates" / "teachers" / "portal_workspace.html").is_file())
        self.assertTrue((ROOT / "templates" / "parent_portal" / "dashboard.html").is_file())
        self.assertTrue((ROOT / "dashboard" / "templates" / "dashboard" / "home.html").is_file())
