from pathlib import Path
import shutil

from django.conf import settings
from django.db import migrations


def upgrade_engine(_apps, _schema_editor):
    project = Path(settings.BASE_DIR).resolve()
    source = project / "core" / "update_engine_v4_payload"
    if not source.is_dir():
        return
    storage = project.parent / "opal_private_backups"
    engine = storage / "engine_v2" / "payload"
    copies = {
        source / "system_update_service.py": project / "core" / "system_update_service.py",
        source / "system_update_views.py": project / "core" / "system_update_views.py",
        source / "tests_system_updates.py": project / "core" / "tests_system_updates.py",
        source / "backup_file_actions.py": project / "core" / "backup_file_actions.py",
        source / "templates" / "core" / "system_updates.html": project / "templates" / "core" / "system_updates.html",
    }
    for src, dst in copies.items():
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    engine_copies = {
        source / "system_update_service.py": engine / "core" / "system_update_service.py",
        source / "system_update_views.py": engine / "core" / "system_update_views.py",
        source / "tests_system_updates.py": engine / "core" / "tests_system_updates.py",
        source / "backup_file_actions.py": engine / "core" / "backup_file_actions.py",
        source / "templates" / "core" / "system_updates.html": engine / "templates" / "core" / "system_updates.html",
    }
    for src, dst in engine_copies.items():
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


class Migration(migrations.Migration):
    dependencies = [("core", "0005_unified_two_semesters")]
    operations = [migrations.RunPython(upgrade_engine, migrations.RunPython.noop)]
