from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "اكتب requirements-lock-r20.txt من بيئة Python الحالية التي نجحت فيها الاختبارات."

    def handle(self, *args, **options):
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise CommandError(f"تعذر قراءة الاعتماديات من البيئة الحالية: {exc}") from exc

        lines = sorted(
            {
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            },
            key=str.lower,
        )
        lower_lines = [line.lower() for line in lines]
        if not any(line.startswith("django==") for line in lower_lines):
            raise CommandError("البيئة الحالية لا تعرض Django بإصدار مثبت؛ لم يُكتب ملف القفل.")
        if not any(line.startswith("pillow==") for line in lower_lines):
            raise CommandError("البيئة الحالية لا تعرض Pillow بإصدار مثبت؛ لم يُكتب ملف القفل.")

        target = Path(settings.BASE_DIR) / "requirements-lock-r20.txt"
        content = (
            "# OPAL Learning tested dependency lock\n"
            "# Generated from the active Python environment by:\n"
            "#   python manage.py write_learning_dependency_lock\n"
            + "\n".join(lines)
            + "\n"
        )
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(content, encoding="utf-8")
        temp.replace(target)
        self.stdout.write(self.style.SUCCESS(f"تم إنشاء قفل الاعتماديات: {target}"))
        self.stdout.write(f"عدد الحزم المثبتة: {len(lines)}")
