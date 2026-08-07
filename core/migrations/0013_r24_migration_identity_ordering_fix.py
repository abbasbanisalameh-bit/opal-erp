from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.db import migrations


MANIFEST = {'schema': 2, 'product': 'OPAL ERP', 'version': '131.7', 'version_name': 'OPAL Update 131.7 R24 - Migration Identity Ordering Fix', 'package_revision': 27, 'source_type': 'verified_update_package', 'created_at': '2026-08-06T01:15:00+03:00', 'baseline': 'OPAL Update 131.7 R23 - Release Identity Deployment Synchronization', 'notes': 'إصلاح ترتيب هجرات هوية الإصدار أثناء إنشاء قاعدة الاختبار أو تثبيت بيئة جديدة. يمنع ترحيل R21 القديم من تخفيض OPAL_UPDATE_MANIFEST.json عند وجود إصدار أحدث، ويضيف مُثبت هوية R24 بعد هجرة R21 صراحة. لا تغييرات على بيانات المنصة أو الحسابات أو الدورات أو الاشتراكات أو الصلاحيات.', 'code_only': True, 'excluded': ['database', 'media', 'virtual_environment', '.env', '.git', 'collected_static']}


def finalize_release_identity(apps, schema_editor):
    root = Path(settings.BASE_DIR).resolve()
    manifest_path = root / "OPAL_UPDATE_MANIFEST.json"
    try:
        current_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        existing_revision = int(current_manifest.get("package_revision") or 0)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        existing_revision = 0
    if existing_revision > MANIFEST["package_revision"]:
        return
    (root / "OPAL_VERSION.txt").write_text(MANIFEST["version"] + "\n", encoding="utf-8")
    (root / "OPAL_RELEASE_NAME.txt").write_text(MANIFEST["version_name"] + "\n", encoding="utf-8")
    (root / "OPAL_UPDATE_MANIFEST.json").write_text(
        json.dumps(MANIFEST, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_r23_release_identity_sync"),
        ("learning_platform", "0007_r21_runtime_validation_fixes"),
    ]

    operations = [
        migrations.RunPython(finalize_release_identity, migrations.RunPython.noop),
    ]
