from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "أنشئ نسخة احتياطية قابلة للتدقيق لبيانات منصة أوبال التعليمية."

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", default="")

    def handle(self, *args, **options):
        target_dir = Path(
            options["output_dir"]
            or getattr(settings, "OPAL_LEARNING_BACKUP_DIR", "")
            or Path(settings.BASE_DIR) / "backups" / "learning_platform"
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = target_dir / f"opal_learning_backup_{stamp}.zip"
        with tempfile.TemporaryDirectory(prefix="opal_learning_backup_") as temp:
            work = Path(temp)
            data_path = work / "learning_platform.json"
            with data_path.open("w", encoding="utf-8") as stream:
                call_command(
                    "dumpdata",
                    "learning_platform",
                    indent=2,
                    stdout=stream,
                )
            included = [data_path]
            db_path = None
            if connection.vendor == "sqlite":
                db_path = work / "db.sqlite3"
                connection.ensure_connection()
                destination = sqlite3.connect(str(db_path))
                try:
                    connection.connection.backup(destination)
                finally:
                    destination.close()
                included.append(db_path)
            manifest = {
                "product": "OPAL Learning Platform",
                "created_at": datetime.now().astimezone().isoformat(),
                "database_vendor": connection.vendor,
                "files": {},
                "contains_password_hashes": True,
                "contains_plaintext_passwords": False,
            }
            for path in included:
                manifest["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest_path = work / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            included.append(manifest_path)
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in included:
                    archive.write(path, arcname=path.name)
        try:
            os.chmod(archive_path, 0o600)
        except OSError:
            pass
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        self.stdout.write(self.style.SUCCESS(f"backup={archive_path}"))
        self.stdout.write(f"sha256={digest}")
