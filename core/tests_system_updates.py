from __future__ import annotations

import io
import os
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .system_update_service import (
    GitStatus,
    create_current_snapshot,
    inspect_package,
    list_local_versions,
    save_uploaded_update,
)


class SystemUpdatesPageTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            username="opal-admin",
            email="admin@example.com",
            password="test-pass-123",
        )
        self.staff = user_model.objects.create_user(
            username="opal-staff",
            password="test-pass-123",
            is_staff=True,
        )

    @patch("core.system_update_views.get_github_versions", return_value=[])
    @patch("core.system_update_views.get_git_status")
    @patch("core.system_update_views.list_local_versions", return_value=[])
    @patch("core.system_update_views.private_storage_root", return_value=Path("/tmp/opal"))
    def test_superuser_can_open_page(self, _private, _versions, git_status, _github):
        git_status.return_value = GitStatus(available=True, branch="main", commit="abc123")
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("core:system_updates"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "حفظ النسخة الحالية")
        self.assertContains(response, "نسخ GitHub")

    def test_staff_cannot_open_page(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("core:system_updates"))
        self.assertEqual(response.status_code, 403)


class PackageTests(TestCase):
    def _make_project(self, root: Path) -> Path:
        project = root / "opal_school"
        (project / "core").mkdir(parents=True)
        (project / "templates").mkdir(parents=True)
        (project / "media").mkdir()
        (project / "venv").mkdir()
        (project / "manage.py").write_text("print('opal')\n", encoding="utf-8")
        (project / "core" / "models.py").write_text("# model\n", encoding="utf-8")
        (project / "templates" / "page.html").write_text("opal\n", encoding="utf-8")
        (project / "media" / "student.jpg").write_bytes(b"media")
        (project / "venv" / "python").write_bytes(b"venv")
        (project / "db.sqlite3").write_bytes(b"database")
        (project / ".env").write_text("SECRET=1\n", encoding="utf-8")
        return project

    def test_current_snapshot_excludes_private_data(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            project = self._make_project(temp_path)
            storage = temp_path / "private"
            with override_settings(BASE_DIR=project), patch.dict(
                os.environ,
                {"OPAL_SYSTEM_STORAGE_DIR": str(storage)},
            ), patch("core.system_update_service.get_git_status", return_value=GitStatus(False)):
                record = create_current_snapshot(username="tester", version_name="Test V1")
                archive_path = storage / "versions" / record.filename
                self.assertTrue(archive_path.is_file())
                with zipfile.ZipFile(archive_path, "r") as archive:
                    names = set(archive.namelist())
                self.assertIn("opal_school/manage.py", names)
                self.assertNotIn("opal_school/db.sqlite3", names)
                self.assertFalse(any("/media/" in name for name in names))
                self.assertFalse(any("/venv/" in name for name in names))
                self.assertNotIn("opal_school/.env", names)

    def test_uploaded_update_is_validated_and_listed(self):
        with tempfile.TemporaryDirectory() as temp:
            memory_file = io.BytesIO()
            with zipfile.ZipFile(memory_file, "w") as archive:
                archive.writestr("opal/manage.py", "print('opal')")
                archive.writestr("opal/core/apps.py", "")
                archive.writestr("opal/templates/base.html", "")
            upload = SimpleUploadedFile(
                "opal_update.zip",
                memory_file.getvalue(),
                content_type="application/zip",
            )
            with patch.dict(os.environ, {"OPAL_SYSTEM_STORAGE_DIR": temp}):
                record = save_uploaded_update(upload, username="tester")
                self.assertTrue(record.compatible)
                self.assertEqual(len(list_local_versions()), 1)
                inspection = inspect_package(Path(temp) / "versions" / record.filename)
                self.assertTrue(inspection.compatible)
