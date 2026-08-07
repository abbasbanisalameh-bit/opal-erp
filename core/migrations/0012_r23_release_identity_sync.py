from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.db import migrations


MANIFEST = {'schema': 2, 'product': 'OPAL ERP', 'version': '131.7', 'version_name': 'OPAL Update 131.7 R23 - Release Identity Deployment Synchronization', 'package_revision': 26, 'source_type': 'verified_update_package', 'created_at': '2026-08-05T16:08:36+03:00', 'baseline': 'OPAL Update 131.7 R22 - Forward-Compatible Release Contract Fix', 'notes': 'إصلاح تزامن هوية الإصدار عند التركيب من مركز التحديثات. يقوم التحديث بإعادة مزامنة OPAL_VERSION.txt وOPAL_RELEASE_NAME.txt وOPAL_UPDATE_MANIFEST.json، ويجعل محرك التحديث يتحقق صراحة من نسخ ملفات الهوية واتساقها بعد كل استبدال للكود. لا تغييرات على بيانات المنصة أو الحسابات أو الدورات أو الاشتراكات أو الصلاحيات.', 'code_only': True, 'excluded': ['database', 'media', 'virtual_environment', '.env', '.git', 'collected_static']}


def synchronize_release_identity(apps, schema_editor):
    root = Path(settings.BASE_DIR).resolve()
    (root / "OPAL_VERSION.txt").write_text(MANIFEST["version"] + "\n", encoding="utf-8")
    (root / "OPAL_RELEASE_NAME.txt").write_text(MANIFEST["version_name"] + "\n", encoding="utf-8")
    (root / "OPAL_UPDATE_MANIFEST.json").write_text(
        json.dumps(MANIFEST, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class Migration(migrations.Migration):
    dependencies = [("core", "0011_bootstrap_update_engine_v3")]

    operations = [
        migrations.RunPython(synchronize_release_identity, migrations.RunPython.noop),
    ]
