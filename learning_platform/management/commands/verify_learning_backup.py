from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "تحقق من سلامة نسخة منصة أوبال التعليمية دون استعادتها فوق البيانات الحالية."

    def add_arguments(self, parser):
        parser.add_argument("archive")

    def handle(self, *args, **options):
        archive_path = Path(options["archive"])
        if not archive_path.is_file():
            raise CommandError("ملف النسخة غير موجود.")
        if not zipfile.is_zipfile(archive_path):
            raise CommandError("الملف ليس ZIP صالحًا.")
        with tempfile.TemporaryDirectory(prefix="opal_learning_verify_") as temp:
            target = Path(temp)
            with zipfile.ZipFile(archive_path) as archive:
                unsafe = [
                    name
                    for name in archive.namelist()
                    if name.startswith("/") or ".." in Path(name).parts
                ]
                if unsafe:
                    raise CommandError("تحتوي النسخة مسارات غير آمنة.")
                archive.extractall(target)
            manifest_path = target / "manifest.json"
            if not manifest_path.exists():
                raise CommandError("manifest.json غير موجود.")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for name, expected in manifest.get("files", {}).items():
                path = target / name
                if not path.is_file():
                    raise CommandError(f"ملف مفقود داخل النسخة: {name}")
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                if actual != expected:
                    raise CommandError(f"فشل SHA-256 للملف: {name}")
            data_path = target / "learning_platform.json"
            try:
                raw_data = data_path.read_text(encoding="utf-8")
                payload = json.loads(raw_data)
            except (OSError, json.JSONDecodeError) as exc:
                raise CommandError("ملف بيانات المنصة غير صالح.") from exc
            if not isinstance(payload, list):
                raise CommandError("صيغة dumpdata غير متوقعة.")
            try:
                deserialized_count = sum(1 for _item in serializers.deserialize("json", raw_data))
            except Exception as exc:
                raise CommandError("تعذر تفسير النسخة بنماذج الإصدار الحالي.") from exc
            if deserialized_count != len(payload):
                raise CommandError("عدد الكائنات بعد التفسير لا يطابق ملف النسخة.")
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        marker_path = archive_path.with_suffix(archive_path.suffix + ".verified.json")
        marker_path.write_text(
            json.dumps(
                {
                    "archive": archive_path.name,
                    "sha256": digest,
                    "verified_at": timezone.now().isoformat(),
                    "objects": len(payload),
                    "structural_only": True,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS("النسخة سليمة بنيويًا وتطابق بصمات manifest ويمكن تفسير بياناتها بالنماذج الحالية."))
        self.stdout.write(f"objects={len(payload)} sha256={digest} marker={marker_path}")
