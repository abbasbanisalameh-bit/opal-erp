from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = (
        "ينفذ بروفة آمنة للنسخ الاحتياطي والاستعادة خارج قاعدة البيانات الحية، "
        "ويصدر تقريرًا دون حذف أو تعديل بيانات OPAL ERP."
    )

    def add_arguments(self, parser):
        parser.add_argument("--output", help="مسار اختياري لحفظ تقرير JSON")
        parser.add_argument("--backup-dir", help="مجلد خاص لحفظ نسخة الاختبار")
        parser.add_argument(
            "--strict",
            action="store_true",
            help="اعتبار التحذيرات مانعة لاعتماد الجاهزية.",
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR)
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        passed: list[dict[str, str]] = []
        artifacts: list[dict[str, object]] = []

        def add(target, code: str, message: str) -> None:
            target.append({"code": code, "message": message})

        configured_dir = options.get("backup_dir") or os.environ.get("OPAL_PRIVATE_BACKUP_DIR")
        backup_dir = (
            Path(configured_dir).expanduser()
            if configured_dir
            else root.parent / "opal_private_backups" / "recovery_rehearsal"
        )
        if not backup_dir.is_absolute():
            backup_dir = root / backup_dir
        backup_dir.mkdir(parents=True, exist_ok=True)

        if os.access(backup_dir, os.W_OK):
            add(passed, "BACKUP_DIR", f"مجلد النسخ الخاص موجود وقابل للكتابة: {backup_dir}")
        else:
            add(errors, "BACKUP_DIR", f"مجلد النسخ غير قابل للكتابة: {backup_dir}")

        engine = str(connection.settings_dict.get("ENGINE") or "")
        db_name = str(connection.settings_dict.get("NAME") or "")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        if "sqlite" in engine and db_name:
            source = Path(db_name)
            if not source.is_absolute():
                source = root / source
            if not source.is_file():
                add(errors, "DB_SOURCE", f"ملف قاعدة SQLite غير موجود: {source}")
            else:
                target = backup_dir / f"opal_db_rehearsal_{timestamp}.sqlite3"
                try:
                    with sqlite3.connect(str(source)) as src, sqlite3.connect(str(target)) as dst:
                        src.backup(dst)
                    add(passed, "DB_BACKUP", f"تم إنشاء نسخة SQLite آمنة خارج الملف الحي: {target.name}")

                    with sqlite3.connect(str(target)) as check_conn:
                        integrity = check_conn.execute("PRAGMA integrity_check").fetchone()[0]
                        table_count = check_conn.execute(
                            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                        ).fetchone()[0]
                    if integrity != "ok":
                        add(errors, "DB_INTEGRITY", f"فشل فحص سلامة النسخة: {integrity}")
                    else:
                        add(passed, "DB_INTEGRITY", "نجح PRAGMA integrity_check على النسخة الاحتياطية.")

                    with tempfile.TemporaryDirectory(prefix="opal_recovery_rehearsal_") as temp_dir:
                        restored = Path(temp_dir) / "restored.sqlite3"
                        shutil.copy2(target, restored)
                        with sqlite3.connect(str(restored)) as restored_conn:
                            restored_integrity = restored_conn.execute("PRAGMA integrity_check").fetchone()[0]
                            restored_tables = restored_conn.execute(
                                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                            ).fetchone()[0]
                        if restored_integrity == "ok" and restored_tables == table_count:
                            add(
                                passed,
                                "RESTORE_REHEARSAL",
                                f"نجحت بروفة الاستعادة في مجلد مؤقت وتحقق {restored_tables} جدولًا.",
                            )
                        else:
                            add(errors, "RESTORE_REHEARSAL", "فشلت مطابقة النسخة المستعادة المؤقتة.")

                    artifacts.append(
                        {
                            "type": "sqlite_backup",
                            "path": str(target),
                            "size_bytes": target.stat().st_size,
                            "sha256": self._sha256(target),
                            "tables": table_count,
                        }
                    )
                except Exception as exc:  # pragma: no cover - operational safeguard
                    add(errors, "DB_BACKUP_EXCEPTION", f"تعذر تنفيذ بروفة النسخ والاستعادة: {exc}")
        else:
            add(
                warnings,
                "DB_EXTERNAL_TOOL",
                "قاعدة البيانات ليست SQLite؛ يجب تنفيذ نسخة بأداة مزود القاعدة والتحقق من الاستعادة في قاعدة منفصلة.",
            )

        # تحقق من نسخة الكود دون تعديل المستودع.
        git_dir = root / ".git"
        if git_dir.exists():
            try:
                status = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                remote = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                if status.returncode == 0 and not status.stdout.strip():
                    add(passed, "CODE_GIT_STATUS", "نسخة الكود في Git نظيفة.")
                else:
                    add(warnings, "CODE_GIT_STATUS", "توجد تغييرات كود غير محفوظة في Git.")
                if remote.returncode == 0 and remote.stdout.strip():
                    add(passed, "CODE_GIT_REMOTE", "مستودع origin مضبوط لحفظ الكود خارجيًا.")
                else:
                    add(warnings, "CODE_GIT_REMOTE", "تعذر إثبات وجود مستودع origin.")
            except (OSError, subprocess.SubprocessError) as exc:
                add(warnings, "CODE_GIT_CHECK", f"تعذر فحص Git: {exc}")
        else:
            add(
                warnings,
                "CODE_GIT_CHECK",
                "مجلد .git غير موجود في نسخة التشغيل؛ تحقق يدويًا أن الكود محفوظ ومرفوع إلى GitHub.",
            )

        required = [
            root / "manage.py",
            root / "templates/includes/sidebar.html",
            root / "templates/includes/topbar.html",
            root / "static/css/opal_erp.css",
        ]
        missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
        if missing:
            add(errors, "CODE_REQUIRED_FILES", "ملفات أساسية مفقودة: " + ", ".join(missing))
        else:
            add(passed, "CODE_REQUIRED_FILES", "ملفات النواة الواجهية والتشغيلية الأساسية موجودة.")

        strict = bool(options.get("strict"))
        ready = not errors and (not strict or not warnings)
        report = {
            "audit": "OPAL ERP backup and recovery rehearsal",
            "version": (root / "OPAL_VERSION.txt").read_text(encoding="utf-8").strip(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ready": ready,
            "status": "ready" if ready else "needs_action",
            "summary": {
                "passed": len(passed),
                "warnings": len(warnings),
                "errors": len(errors),
                "artifacts": len(artifacts),
            },
            "passed": passed,
            "warnings": warnings,
            "errors": errors,
            "artifacts": artifacts,
            "safety": {
                "live_database_modified": False,
                "data_deleted": False,
                "restore_target": "temporary_isolated_copy",
                "student_model": "students.Student",
            },
        }

        output_path = options.get("output")
        if output_path:
            output = Path(output_path)
            if not output.is_absolute():
                output = root / output
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(f"تم حفظ تقرير النسخ والاستعادة: {output}")

        self.stdout.write(self.style.MIGRATE_HEADING("OPAL ERP — بروفة النسخ والاستعادة"))
        for item in passed:
            self.stdout.write(self.style.SUCCESS(f"نجاح [{item['code']}]: {item['message']}"))
        for item in warnings:
            self.stdout.write(self.style.WARNING(f"تحذير [{item['code']}]: {item['message']}"))
        for item in errors:
            self.stdout.write(self.style.ERROR(f"خطأ [{item['code']}]: {item['message']}"))
        self.stdout.write(
            f"النتيجة: {'جاهز' if ready else 'يحتاج معالجة'} | "
            f"نجاح {len(passed)} | تحذيرات {len(warnings)} | أخطاء {len(errors)}"
        )

        if not ready:
            raise CommandError("لم تعتمد بروفة النسخ والاستعادة؛ راجع التقرير.")
