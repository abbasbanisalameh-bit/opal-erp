from pathlib import Path
from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]


class R53TransportGroupEstablishmentContractTests(SimpleTestCase):
    def test_family_student_values_rows_use_mapping_access(self):
        source = (ROOT / "transport" / "services.py").read_text(encoding="utf-8")
        self.assertIn('row["student_id"]: row["family_id"] for row in FamilyStudent.objects.filter(', source)
        self.assertNotIn('row.student_id: row.family_id for row in FamilyStudent.objects.filter(', source)
