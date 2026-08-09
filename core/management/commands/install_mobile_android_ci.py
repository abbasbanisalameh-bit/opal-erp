from __future__ import annotations

import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Install/update the OPAL Android GitHub Actions workflow from the tracked mobile template."

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR)
        source = root / "mobile" / "opal_learning_app" / "ci" / "opal-android-build.yml"
        if not source.exists():
            raise CommandError(f"Mobile CI template is missing: {source}")
        target = root / ".github" / "workflows" / "opal-android-build.yml"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        self.stdout.write(self.style.SUCCESS(f"تم تثبيت مسار بناء Android: {target}"))
