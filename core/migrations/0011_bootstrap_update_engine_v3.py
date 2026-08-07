"""Bootstrap the self-updating center without changing OPAL business data."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from django.conf import settings
from django.db import migrations


ENTRY_POINT = '''"""Stable public entry point for the self-updating OPAL update center."""

from . import update_engine_runtime as _runtime

globals().update(
    {
        name: value
        for name, value in vars(_runtime).items()
        if not name.startswith("__")
    }
)
'''


def _private_storage(root: Path) -> Path:
    configured = (
        os.environ.get("OPAL_SYSTEM_STORAGE_DIR", "").strip()
        or os.environ.get("OPAL_PRIVATE_BACKUP_DIR", "").strip()
        or str(getattr(settings, "OPAL_SYSTEM_STORAGE_DIR", "") or "").strip()
        or str(getattr(settings, "OPAL_PRIVATE_BACKUPS_DIR", "") or "").strip()
        or str(getattr(settings, "OPAL_PRIVATE_BACKUP_DIR", "") or "").strip()
    )
    return Path(configured).expanduser().resolve() if configured else root.parent / "opal_private_backups"


def bootstrap_update_engine(apps, schema_editor):
    """Install the tiny permanent entry point after the package is in place.

    The actual runtime remains in normal project code, so subsequent packages
    can improve the update center rather than being replaced by an old overlay.
    """
    root = Path(settings.BASE_DIR).resolve()
    runtime = root / "core" / "update_engine_runtime.py"
    if not runtime.is_file():
        raise RuntimeError("ملف محرك التحديث الجديد مفقود؛ أوقف الترحيل لحماية مركز التحديث.")

    entry_point = root / "core" / "system_update_service.py"
    entry_point.write_text(ENTRY_POINT, encoding="utf-8")

    payload_root = _private_storage(root) / "engine_v2" / "payload" / "core"
    payload_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(entry_point, payload_root / "system_update_service.py")
    try:
        payload_root.chmod(0o700)
        (payload_root / "system_update_service.py").chmod(0o600)
    except OSError:
        pass


class Migration(migrations.Migration):
    dependencies = [("core", "0010_semester_structure_snapshot")]

    operations = [migrations.RunPython(bootstrap_update_engine, migrations.RunPython.noop)]
