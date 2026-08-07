from pathlib import Path
import re

from django.test import SimpleTestCase

from .school_finance_language_contracts import run_school_finance_language_audit
from .single_entry_contracts import run_single_entry_contract_audit


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard" / "templates" / "dashboard" / "home.html"
PARENT_FEES = ROOT / "templates" / "parent_portal" / "fees.html"


class Update126SchoolFinanceLanguageAndDashboardLinksTests(SimpleTestCase):
    def test_plain_school_finance_language_contract_is_clean(self):
        report = run_school_finance_language_audit(root=ROOT)
        self.assertTrue(report["ok"], report["issues"])

    def test_single_entry_contract_accepts_only_gateway_kpi_links(self):
        report = run_single_entry_contract_audit(root=ROOT)
        self.assertTrue(report["ok"], report["issues"])

    def test_parent_statement_uses_one_amount_column(self):
        source = PARENT_FEES.read_text(encoding="utf-8")
        self.assertIn("نوع الحركة", source)
        self.assertIn("tx.amount", source)
        self.assertNotIn("tx.debit", source)
        self.assertNotIn("tx.credit", source)

    def test_six_management_kpis_are_real_links_to_gateway_fragments(self):
        source = DASHBOARD.read_text(encoding="utf-8")
        anchors = re.findall(r'<a\b[^>]*class="[^"]*\bopal-kpi-[^"]*"[^>]*>', source)
        self.assertEqual(len(anchors), 6)
        for fragment in (
            "#student-list",
            "#teachers-operation",
            "#attendance-operation",
            "#fee-summary",
            "#outstanding-balances",
            "#exam-analysis-operation",
        ):
            self.assertIn(fragment, source)
