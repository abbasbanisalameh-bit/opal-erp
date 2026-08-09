from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class R351FlutterRadioGroupHotfixContractTests(SimpleTestCase):
    def setUp(self):
        self.source = (
            Path(settings.BASE_DIR) / "mobile" / "opal_learning_app" / "lib" / "main.dart"
        ).read_text(encoding="utf-8")

    def test_quiz_uses_modern_radio_group(self):
        self.assertIn("RadioGroup<String>(", self.source)
        self.assertIn("groupValue: answers[questionId]", self.source)
        self.assertIn("onChanged: (value)", self.source)

    def test_radio_list_tile_no_longer_owns_deprecated_group_state(self):
        self.assertIn("RadioListTile<String>(", self.source)
        self.assertNotIn("groupValue: answers[q['id'].toString()]", self.source)
        self.assertNotIn("onChanged: (value) => setState(() => answers[q['id'].toString()]", self.source)
