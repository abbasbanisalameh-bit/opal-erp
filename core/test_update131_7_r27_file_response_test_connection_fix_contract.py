from pathlib import Path

from django.test import SimpleTestCase

from core.release_contract_assertions import assert_forward_compatible_release_identity


ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class FileResponseTestConnectionIsolationContractTests(SimpleTestCase):
    def test_backup_download_test_does_not_close_the_http_response(self):
        tests = source("core/tests_system_updates.py")
        self.assertNotIn("download_response.close()", tests)
        self.assertIn('getattr(download_response, "file_to_stream", None)', tests)
        self.assertIn("file_to_stream.close()", tests)
        self.assertIn("following POST request", tests)

    def test_current_release_identity_meets_r27_floor(self):
        assert_forward_compatible_release_identity(self, source, min_revision=30)
