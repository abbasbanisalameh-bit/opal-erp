from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "core" / "update_engine_runtime.py"
GITIGNORE = ROOT / ".gitignore"
TEMPLATE = ROOT / "templates" / "core" / "system_updates.html"


class Update1317R70RuntimeGitIsolationContractTests(SimpleTestCase):
    def test_runtime_paths_are_explicitly_ignored(self):
        source = GITIGNORE.read_text(encoding="utf-8")
        for required in ("media/", "uploads/", "db.sqlite3", ".env", "venv/"):
            self.assertIn(required, source)

    def test_push_isolates_tracked_runtime_files_without_deleting_disk_files(self):
        source = RUNTIME.read_text(encoding="utf-8")
        self.assertIn("def _isolate_forbidden_git_files()", source)
        self.assertIn("git", source)
        self.assertIn("rm", source)
        self.assertIn("--cached", source)
        self.assertIn("isolated_runtime_files = _isolate_forbidden_git_files()", source)

    def test_update_center_separates_code_from_runtime_status(self):
        source = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("توجد تغييرات برمجية لم تُرفع", source)
        self.assertIn("git_status.runtime_changes", source)
        self.assertIn("ملفات تشغيل/بيانات", source)
