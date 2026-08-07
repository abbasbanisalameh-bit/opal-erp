from __future__ import annotations

import json
from pathlib import Path

from django.db import migrations


MANIFEST = {'schema': 2, 'product': 'OPAL ERP', 'version': '131.7', 'version_name': 'OPAL Update 131.7 R21 - Learning Platform Runtime Validation Fixes', 'package_revision': 24, 'source_type': 'verified_update_package', 'created_at': '2026-08-05T13:55:00+03:00', 'baseline': 'OPAL Update 131.7 R20 - Learning Platform Production Release Candidate', 'notes': 'إصلاح اعتماد R20 على PythonAnywhere: استبدال اختبارات هشة مرتبطة بترجمة Django، تصحيح عقد ترويسة Bearer إلى HTTP_AUTHORIZATION، واستعادة OPAL_UPDATE_MANIFEST.json بعد التثبيت عبر مركز التحديثات مع تعديل محرك التحديثات للحفاظ عليه مستقبلًا. لا تغييرات على بيانات المنصة أو صلاحياتها التشغيلية.', 'code_only': True, 'excluded': ['database', 'media', 'virtual_environment', '.env', '.git', 'collected_static']}


def restore_release_manifest(apps, schema_editor):
    project_root = Path(__file__).resolve().parents[2]
    manifest_path = project_root / "OPAL_UPDATE_MANIFEST.json"

    # This historical migration may run again while Django creates a test
    # database or a fresh environment. Never let it downgrade a newer source
    # release identity already shipped with the installed code.
    try:
        current_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        current_manifest = {}

    try:
        existing_revision = int(current_manifest.get("package_revision") or 0)
    except (TypeError, ValueError):
        existing_revision = 0

    if existing_revision > MANIFEST["package_revision"]:
        return

    manifest_path.write_text(
        json.dumps(MANIFEST, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class Migration(migrations.Migration):
    dependencies = [("learning_platform", "0006_learning_production_release")]

    operations = [
        migrations.RunPython(restore_release_manifest, migrations.RunPython.noop),
    ]
