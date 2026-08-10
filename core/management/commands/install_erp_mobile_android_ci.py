from pathlib import Path
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "يثبت GitHub Actions لبناء تطبيق نظام OPAL ERP ويعيد مسار بناء منصة أوبال إن كان متاحًا."

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR)
        target_dir = root / ".github" / "workflows"
        target_dir.mkdir(parents=True, exist_ok=True)

        sources = [
            (
                root / "mobile" / "opal_erp_app" / "ci" / "opal-erp-android-build.yml",
                target_dir / "opal-erp-android-build.yml",
                True,
            ),
            (
                root / "mobile" / "opal_learning_app" / "ci" / "opal-android-build.yml",
                target_dir / "opal-android-build.yml",
                False,
            ),
        ]

        installed = []
        for source, target, required in sources:
            if not source.exists():
                if required:
                    raise CommandError(f"ملف Workflow غير موجود: {source}")
                continue
            shutil.copy2(source, target)
            installed.append(target)

        if not installed:
            raise CommandError("لم يتم العثور على أي Workflow قابل للتثبيت.")

        for target in installed:
            self.stdout.write(self.style.SUCCESS(f"تم تثبيت مسار بناء Android: {target}"))
