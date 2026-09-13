from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class Student360MobileContainmentContractTests(unittest.TestCase):
    def test_student_tab_content_has_scoped_container(self):
        template = source("templates/students/student_360.html")
        self.assertIn('class="tab-content opal-student-360-tab-content"', template)

    def test_wide_content_scrolls_inside_the_active_tab(self):
        css = source("static/css/opal_entity_360_consolidation.css")
        self.assertIn("OPAL Update 131.7 R3 — Student 360 mobile width containment", css)
        self.assertIn(".opal-student-360 .opal-student-360-tab-content", css)
        self.assertIn("min-width:0", css)
        self.assertIn("max-width:100%", css)
        self.assertIn("overflow-x:auto!important", css)
        self.assertIn("contain:inline-size", css)

    def test_entity_stylesheet_cache_token_is_bumped(self):
        base = source("templates/base/base.html")
        self.assertRegex(base, r"opal_theme_system\.css' %\}\?v=[^\"\s]+")

    def test_release_identity(self):
        release_name = source("OPAL_RELEASE_NAME.txt").strip()
        self.assertIn(f'"version_name": "{release_name}"', source("OPAL_UPDATE_MANIFEST.json"))


if __name__ == "__main__":
    unittest.main()
