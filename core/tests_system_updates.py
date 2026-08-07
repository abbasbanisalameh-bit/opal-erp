from __future__ import annotations

import errno
import io
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .system_update_service import (
    GitStatus,
    _create_database_safety_snapshot,
    _path_forbidden,
    _restore_database_safety_snapshot,
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


    @patch("core.system_update_views.get_github_versions", return_value=[])
    @patch("core.system_update_views.get_git_status")
    @patch("core.system_update_views.list_local_versions")
    @patch("core.system_update_views.private_storage_root", return_value=Path("/tmp/opal"))
    def test_page_renders_download_and_delete_actions(self, _private, versions, git_status, _github):
        from .system_update_service import LocalVersionRecord

        git_status.return_value = GitStatus(available=True, branch="main", commit="abc123")
        versions.return_value = [
            LocalVersionRecord(
                filename="OPAL_TEST.zip",
                version_name="OPAL TEST",
                source_type="current_snapshot",
                source_display="نسخة من النظام الحالي",
                size_bytes=1024,
                sha256="a" * 64,
                saved_at="2026-07-15T10:00:00",
                saved_by="admin",
            )
        ]
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("core:system_updates"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("core:updates_download_backup"))
        self.assertContains(response, reverse("core:updates_delete_backup"))
        self.assertContains(response, "تنزيل")
        self.assertContains(response, "حذف")

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

    def _make_update_upload(self) -> SimpleUploadedFile:
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, "w") as archive:
            archive.writestr("opal/manage.py", "print('opal')")
            archive.writestr("opal/core/apps.py", "")
            archive.writestr("opal/templates/base.html", "")
        return SimpleUploadedFile(
            "opal_update.zip",
            memory_file.getvalue(),
            content_type="application/zip",
        )

    def test_current_snapshot_excludes_private_data(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
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
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            upload = self._make_update_upload()
            with patch.dict(os.environ, {"OPAL_SYSTEM_STORAGE_DIR": temp}):
                record = save_uploaded_update(upload, username="tester")
                self.assertTrue(record.compatible)
                self.assertEqual(len(list_local_versions()), 1)
                inspection = inspect_package(Path(temp) / "versions" / record.filename)
                self.assertTrue(inspection.compatible)

    def test_uploaded_update_remains_successful_when_metadata_write_fails(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            upload = self._make_update_upload()
            metadata_error = OSError(errno.EDQUOT, "quota exceeded")
            with patch.dict(
                os.environ,
                {"OPAL_SYSTEM_STORAGE_DIR": temp},
            ), patch(
                "core.update_engine_runtime._write_metadata",
                side_effect=metadata_error,
            ):
                record = save_uploaded_update(upload, username="tester")
            archive_path = Path(temp) / "versions" / record.filename
            self.assertTrue(archive_path.is_file())
            self.assertTrue(inspect_package(archive_path).compatible)

    def test_upload_quota_failure_has_actionable_storage_code(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            upload = self._make_update_upload()
            quota_error = OSError(errno.EDQUOT, "quota exceeded")
            with patch.dict(
                os.environ,
                {"OPAL_SYSTEM_STORAGE_DIR": temp},
            ), patch(
                "core.update_engine_runtime.tempfile.mkstemp",
                side_effect=quota_error,
            ):
                with self.assertRaises(ValidationError) as captured:
                    save_uploaded_update(upload, username="tester")
            message = " ".join(captured.exception.messages)
            self.assertIn("حصة التخزين", message)
            self.assertIn("EDQUOT", message)

    def test_git_guard_rejects_generated_and_secret_files_but_allows_template(self):
        for path in (
            "db.sqlite3",
            "backups/production.sqlite3",
            "logs/system.log",
            "deliverables/OPAL_UPDATE_108.zip",
            ".env.production",
        ):
            self.assertTrue(_path_forbidden(path), path)
        self.assertFalse(_path_forbidden(".env.example"))
        self.assertFalse(_path_forbidden("core/system_update_service.py"))


class DatabaseSafetySnapshotTests(TestCase):
    def test_sqlite_safety_snapshot_restores_the_pre_update_state(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            root = Path(temp)
            database_path = root / "opal.sqlite3"
            with sqlite3.connect(database_path) as connection:
                connection.execute("CREATE TABLE sample (value TEXT)")
                connection.execute("INSERT INTO sample (value) VALUES ('before')")

            storage = root / "private"
            with patch(
                "core.update_engine_runtime._sqlite_database_path",
                return_value=database_path,
            ), patch(
                "core.update_engine_runtime.private_storage_root",
                return_value=storage,
            ), patch(
                "core.update_engine_runtime.connections.close_all",
            ):
                snapshot = _create_database_safety_snapshot()
                with sqlite3.connect(database_path) as connection:
                    connection.execute("DELETE FROM sample")
                    connection.execute("INSERT INTO sample (value) VALUES ('after')")
                _restore_database_safety_snapshot(snapshot)
                with sqlite3.connect(database_path) as connection:
                    rows = connection.execute("SELECT value FROM sample").fetchall()

            self.assertEqual(rows, [("before",)])
            self.assertTrue(snapshot.is_file())

    def test_database_safety_retention_keeps_only_five_latest_snapshots(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            root = Path(temp)
            database_path = root / "opal.sqlite3"
            with sqlite3.connect(database_path) as connection:
                connection.execute("CREATE TABLE sample (value TEXT)")
                connection.execute("INSERT INTO sample (value) VALUES ('stable')")

            storage = root / "private"
            snapshots = []
            with patch(
                "core.update_engine_runtime._sqlite_database_path",
                return_value=database_path,
            ), patch(
                "core.update_engine_runtime.private_storage_root",
                return_value=storage,
            ), patch(
                "core.update_engine_runtime.connections.close_all",
            ), patch.dict(
                os.environ,
                {"OPAL_DB_SAFETY_KEEP": "5"},
            ):
                for _index in range(7):
                    snapshots.append(_create_database_safety_snapshot())

            retained = sorted((storage / "database_safety").glob("DB_SAFETY_BEFORE_*.sqlite3"))
            self.assertEqual(len(retained), 5)
            self.assertFalse(snapshots[0].exists())
            self.assertFalse(snapshots[1].exists())
            self.assertTrue(snapshots[-1].exists())

    def test_snapshot_creation_remains_successful_if_retention_cleanup_fails(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            root = Path(temp)
            database_path = root / "opal.sqlite3"
            with sqlite3.connect(database_path) as connection:
                connection.execute("CREATE TABLE sample (value TEXT)")

            storage = root / "private"
            with patch(
                "core.update_engine_runtime._sqlite_database_path",
                return_value=database_path,
            ), patch(
                "core.update_engine_runtime.private_storage_root",
                return_value=storage,
            ), patch(
                "core.update_engine_runtime.connections.close_all",
            ), patch(
                "core.update_engine_runtime._prune_database_safety_snapshots",
                side_effect=OSError(errno.EACCES, "permission denied"),
            ):
                snapshot = _create_database_safety_snapshot()

            self.assertTrue(snapshot.is_file())


class BackupFileActionsTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            username="backup-admin",
            email="backup@example.com",
            password="test-pass-123",
        )
        self.client.force_login(self.superuser)

    def test_download_and_delete_version_file(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            root = Path(temp)
            versions = root / "versions"
            versions.mkdir()
            archive = versions / "OPAL_TEST.zip"
            older_archive = versions / "OPAL_OLDER.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("manage.py", "print('opal')")
            with zipfile.ZipFile(older_archive, "w") as handle:
                handle.writestr("manage.py", "print('opal older')")
            archive.with_suffix(".json").write_text("{}", encoding="utf-8")
            older_archive.with_suffix(".json").write_text("{}", encoding="utf-8")

            with override_settings(OPAL_PRIVATE_BACKUPS_DIR=str(root)):
                api_response = self.client.get(reverse("core:updates_backup_files_api"))
                self.assertEqual(api_response.status_code, 200)
                self.assertIn("versions/OPAL_TEST.zip", {item["name"] for item in api_response.json()["files"]})

                download_response = self.client.get(
                    reverse("core:updates_download_backup"),
                    {"name": "versions/OPAL_TEST.zip"},
                )
                try:
                    self.assertEqual(download_response.status_code, 200)
                    self.assertEqual(download_response["Content-Type"], "application/zip")
                finally:
                    # Close only the archive stream. Calling response.close()
                    # emits request_finished and can close Django's shared test
                    # database connection before the following POST request.
                    file_to_stream = getattr(download_response, "file_to_stream", None)
                    if file_to_stream is not None and not file_to_stream.closed:
                        file_to_stream.close()

                delete_response = self.client.post(
                    reverse("core:updates_delete_backup"),
                    {"name": "versions/OPAL_TEST.zip"},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )
                self.assertEqual(delete_response.status_code, 200)
                self.assertTrue(delete_response.json()["ok"])
                self.assertFalse(archive.exists())
                self.assertFalse(archive.with_suffix(".json").exists())


class UpdateUiAssetsTests(TestCase):
    def test_sticky_table_assets_are_present(self):
        base_dir = Path(__file__).resolve().parent.parent
        css = (base_dir / "static" / "css" / "opal_erp.css").read_text(encoding="utf-8")
        js = (base_dir / "static" / "js" / "opal_erp.js").read_text(encoding="utf-8")
        template = (base_dir / "templates" / "core" / "system_updates.html").read_text(encoding="utf-8")
        self.assertIn("OPAL Scrollable Tables V4", css)
        self.assertIn("position: sticky !important", css)
        self.assertIn("OPAL_TABLE_SCROLL_INIT_V4", js)
        self.assertIn("updates_download_backup", template)
        self.assertIn("updates_delete_backup", template)
