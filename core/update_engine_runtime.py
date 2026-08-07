from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Iterable

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connections
from django.utils import timezone
from django.utils.text import get_valid_filename


DEFAULT_MAX_PACKAGE_MB = 50
MAX_COMMAND_OUTPUT = 16000
MANIFEST_NAME = "OPAL_UPDATE_MANIFEST.json"
RELEASE_IDENTITY_FILES = ("OPAL_VERSION.txt", "OPAL_RELEASE_NAME.txt", MANIFEST_NAME)
DEPLOYED_MARKER = "OPAL_DEPLOYED_VERSION.json"
DATABASE_SAFETY_DIRECTORY = "database_safety"
DEFAULT_DATABASE_SAFETY_KEEP = 5
CONFIRMATION_WORD = "استعادة"

PROTECTED_TOP_LEVEL = {
    ".git",
    ".env",
    "db.sqlite3",
    "media",
    "uploads",
    "venv",
    ".venv",
    "env",
    "staticfiles",
    "collected_static",
}

EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".github",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    "media",
    "uploads",
    "staticfiles",
    "collected_static",
    "backups",
    "backup",
    "logs",
    "log",
    "tmp",
    "temp",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
}

EXCLUDED_FILE_NAMES = {
    "db.sqlite3",
    ".env",
    ".coverage",
    "coverage.xml",
}

EXCLUDED_EXTENSIONS = {
    ".sqlite",
    ".sqlite3",
    ".db",
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".bak",
    ".backup",
    ".log",
    ".pyc",
    ".pyo",
    ".pyd",
}

FORBIDDEN_GIT_PATHS = (
    "db.sqlite3",
    "db.sqlite",
    "media/",
    "uploads/",
    "staticfiles/",
    "collected_static/",
    "venv/",
    ".venv/",
    "env/",
    ".env",
)

FORBIDDEN_GIT_SUFFIXES = (
    ".sqlite",
    ".sqlite3",
    ".db",
    ".bak",
    ".backup",
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".log",
    ".pyc",
    ".pyo",
    ".pyd",
)


class SystemUpdateError(RuntimeError):
    """خطأ آمن يمكن عرضه لمدير النظام."""


@dataclass(frozen=True)
class CurrentVersion:
    name: str
    source: str
    branch: str
    commit: str
    deployed_at: str
    has_changes: bool


@dataclass(frozen=True)
class LocalVersionRecord:
    filename: str
    version_name: str
    source_type: str
    source_display: str
    size_bytes: int
    sha256: str
    saved_at: str
    saved_by: str
    branch: str = ""
    commit: str = ""
    compatible: bool = True
    notes: str = ""

    @property
    def size_display(self) -> str:
        return _size_display(self.size_bytes)


@dataclass(frozen=True)
class GitStatus:
    available: bool
    branch: str = ""
    commit: str = ""
    remote: str = ""
    has_changes: bool = False
    error: str = ""


@dataclass(frozen=True)
class GitVersionRecord:
    ref: str
    short_name: str
    kind: str
    kind_display: str
    commit: str
    short_commit: str
    committed_at: str
    author: str
    subject: str
    is_current: bool = False


@dataclass(frozen=True)
class GitPushResult:
    branch: str
    commit: str
    created_commit: bool
    message: str


@dataclass(frozen=True)
class RestoreResult:
    version_name: str
    source: str
    safety_snapshot: str
    message: str
    database_safety_snapshot: str = ""


@dataclass(frozen=True)
class PackageInspection:
    compatible: bool
    project_prefix: str
    version_name: str
    notes: str


def project_root() -> Path:
    root = Path(settings.BASE_DIR).resolve()
    if not (root / "manage.py").is_file():
        raise SystemUpdateError("تعذر تحديد مجلد المشروع: ملف manage.py غير موجود.")
    return root


def python_executable() -> str:
    """Return the real virtualenv Python, never the uWSGI host executable."""
    root = project_root()
    candidates = [
        root / "venv" / "bin" / "python",
        root / ".venv" / "bin" / "python",
    ]
    virtual_env = os.environ.get("VIRTUAL_ENV", "").strip()
    if virtual_env:
        candidates.append(Path(virtual_env).expanduser() / "bin" / "python")
    for candidate in candidates:
        try:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate.resolve())
        except OSError:
            continue
    executable_name = Path(sys.executable or "").name.lower()
    if executable_name.startswith("python") and Path(sys.executable).is_file():
        return sys.executable
    raise SystemUpdateError("تعذر تحديد Python الخاص بالبيئة الافتراضية.")


def private_storage_root() -> Path:
    configured = (
        os.environ.get("OPAL_SYSTEM_STORAGE_DIR", "").strip()
        or os.environ.get("OPAL_PRIVATE_BACKUP_DIR", "").strip()
        or str(getattr(settings, "OPAL_SYSTEM_STORAGE_DIR", "") or "").strip()
        or str(getattr(settings, "OPAL_PRIVATE_BACKUPS_DIR", "") or "").strip()
        or str(getattr(settings, "OPAL_PRIVATE_BACKUP_DIR", "") or "").strip()
    )
    path = Path(configured).expanduser().resolve() if configured else project_root().parent / "opal_private_backups"
    try:
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o700)
    except OSError as exc:
        if exc.errno == errno.ENOSPC:
            raise SystemUpdateError("المساحة المتاحة لا تكفي لإنشاء مجلد إدارة النسخ.") from exc
        raise SystemUpdateError("تعذر إنشاء مجلد إدارة النسخ الخاص.") from exc
    return path


def versions_dir() -> Path:
    path = private_storage_root() / "versions"
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def database_safety_dir() -> Path:
    """Return the private directory used for automatic SQLite rollback points."""
    path = private_storage_root() / DATABASE_SAFETY_DIRECTORY
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def _sqlite_database_path() -> Path:
    """Return the live SQLite file or stop before a non-reversible update.

    OPAL currently uses SQLite.  Refusing an automatic update for another
    engine is safer than claiming that its data can be rolled back when it
    cannot.
    """
    database = settings.DATABASES.get("default", {})
    engine = str(database.get("ENGINE") or "")
    if engine != "django.db.backends.sqlite3":
        raise SystemUpdateError(
            "يتطلب مركز التحديث نسخة احتياطية قابلة للاستعادة لقاعدة البيانات. "
            "الاسترجاع التلقائي مدعوم لقاعدة SQLite فقط؛ أنشئ نسخة من قاعدة البيانات "
            "لدى مزودها ثم نفّذ التحديث يدويًا."
        )
    database_name = str(database.get("NAME") or "").strip()
    if not database_name or database_name == ":memory:" or database_name.startswith("file:"):
        raise SystemUpdateError("ملف قاعدة SQLite الفعلي غير متاح لإنشاء نقطة أمان قبل التحديث.")
    path = Path(database_name).expanduser()
    if not path.is_absolute():
        path = project_root() / path
    path = path.resolve()
    if not path.is_file():
        raise SystemUpdateError("ملف قاعدة SQLite غير موجود؛ أوقف التحديث لحماية البيانات.")
    return path


def database_safety_retention_limit() -> int:
    """Keep a bounded number of verified SQLite rollback points."""
    raw = os.environ.get("OPAL_DB_SAFETY_KEEP", str(DEFAULT_DATABASE_SAFETY_KEEP))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = DEFAULT_DATABASE_SAFETY_KEEP
    return max(2, min(value, 20))


def _prune_database_safety_snapshots(*, preserve: Path | None = None) -> list[str]:
    """Remove only old completed snapshots after a new one is verified."""
    directory = database_safety_dir()
    snapshots = sorted(
        (
            path
            for path in directory.glob("DB_SAFETY_BEFORE_*.sqlite3")
            if path.is_file()
        ),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    protected_names = {
        path.name
        for path in snapshots[:database_safety_retention_limit()]
    }
    if preserve is not None:
        protected_names.add(preserve.name)

    removed = []
    for path in snapshots:
        if path.name in protected_names:
            continue
        try:
            path.unlink()
            removed.append(path.name)
        except OSError as exc:
            error_name = errno.errorcode.get(exc.errno or 0, "UNKNOWN")
            _append_audit(
                "database_safety_prune_failed",
                "system",
                f"file={path.name} storage_code={error_name}",
            )
    return removed


def _create_database_safety_snapshot() -> Path:
    """Create a verified SQLite rollback point before applying an update."""
    database_path = _sqlite_database_path()
    directory = database_safety_dir()
    timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S_%f")
    final_path = directory / f"DB_SAFETY_BEFORE_{timestamp}.sqlite3"
    temporary_path = directory / f".{final_path.name}.partial"

    def verify_snapshot(path: Path) -> None:
        if not path.is_file() or path.stat().st_size <= 0:
            raise sqlite3.DatabaseError("empty SQLite safety snapshot")
        check = None
        try:
            check = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=30)
            result = check.execute("PRAGMA quick_check").fetchone()
            if not result or str(result[0]).lower() != "ok":
                raise sqlite3.DatabaseError(f"SQLite quick_check failed: {result!r}")
        finally:
            if check is not None:
                check.close()

    def in_process_backup() -> None:
        source = destination = None
        try:
            temporary_path.unlink(missing_ok=True)
            connections.close_all()
            source = sqlite3.connect(str(database_path), timeout=90)
            source.execute("PRAGMA busy_timeout = 90000")
            destination = sqlite3.connect(str(temporary_path), timeout=90)
            destination.execute("PRAGMA busy_timeout = 90000")
            source.backup(destination, pages=256, sleep=0.15)
            destination.commit()
        finally:
            if destination is not None:
                destination.close()
            if source is not None:
                source.close()

    def subprocess_backup() -> None:
        helper = "\n".join(
            [
                "import os, sqlite3, sys",
                "src, dst = sys.argv[1], sys.argv[2]",
                "try:",
                "    os.unlink(dst)",
                "except FileNotFoundError:",
                "    pass",
                "source = destination = None",
                "try:",
                "    source = sqlite3.connect(src, timeout=120)",
                "    source.execute('PRAGMA busy_timeout = 120000')",
                "    destination = sqlite3.connect(dst, timeout=120)",
                "    destination.execute('PRAGMA busy_timeout = 120000')",
                "    source.backup(destination, pages=128, sleep=0.25)",
                "    destination.commit()",
                "finally:",
                "    if destination is not None: destination.close()",
                "    if source is not None: source.close()",
            ]
        )
        completed = subprocess.run(
            [python_executable(), "-c", helper, str(database_path), str(temporary_path)],
            cwd=str(project_root()),
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "subprocess backup failed").strip()
            raise sqlite3.OperationalError(detail[-2000:])

    errors: list[BaseException] = []
    try:
        for attempt in range(3):
            try:
                in_process_backup()
                verify_snapshot(temporary_path)
                break
            except (OSError, sqlite3.Error) as exc:
                errors.append(exc)
                temporary_path.unlink(missing_ok=True)
                if attempt < 2:
                    time.sleep(0.75 * (attempt + 1))
        else:
            subprocess_backup()
            verify_snapshot(temporary_path)

        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, final_path)
        _append_audit("database_safety_created", "system", f"file={final_path.name}")
        try:
            removed = _prune_database_safety_snapshots(preserve=final_path)
        except OSError as prune_error:
            error_name = errno.errorcode.get(prune_error.errno or 0, "UNKNOWN")
            _append_audit(
                "database_safety_prune_failed",
                "system",
                f"storage_code={error_name}",
            )
            removed = []
        if removed:
            _append_audit(
                "database_safety_pruned",
                "system",
                f"removed={len(removed)} retained={database_safety_retention_limit()}",
            )
        return final_path
    except (OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
        errors.append(exc)
        detail = type(errors[-1]).__name__
        _append_audit(
            "database_safety_failed",
            "system",
            f"type={detail} attempts={len(errors)} database={database_path.name}",
        )
        raise SystemUpdateError(
            "تعذر إنشاء نقطة أمان لقاعدة البيانات قبل التحديث؛ لم يتم تطبيق التحديث. "
            f"رمز التشخيص: {detail}."
        ) from exc
    finally:
        temporary_path.unlink(missing_ok=True)


def _restore_database_safety_snapshot(snapshot_path: Path) -> None:
    """Restore a SQLite safety point logically, without replacing files in place."""
    if not snapshot_path.is_file():
        raise SystemUpdateError("ملف نقطة أمان قاعدة البيانات غير موجود.")
    database_path = _sqlite_database_path()
    source = destination = None
    try:
        connections.close_all()
        source = sqlite3.connect(f"{snapshot_path.resolve().as_uri()}?mode=ro", uri=True, timeout=30)
        destination = sqlite3.connect(str(database_path), timeout=30)
        source.backup(destination)
        destination.close()
        destination = None
        source.close()
        source = None
        _append_audit("database_safety_restored", "system", f"file={snapshot_path.name}")
    except (OSError, sqlite3.Error) as exc:
        raise SystemUpdateError("تعذر استعادة قاعدة البيانات إلى نقطة الأمان التلقائية.") from exc
    finally:
        if destination is not None:
            destination.close()
        if source is not None:
            source.close()


def engine_dir() -> Path:
    return private_storage_root() / "engine_v2"


def max_package_bytes() -> int:
    raw = os.environ.get("OPAL_UPDATE_MAX_MB", str(DEFAULT_MAX_PACKAGE_MB))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = DEFAULT_MAX_PACKAGE_MB
    return max(1, min(value, 250)) * 1024 * 1024


def _upload_storage_validation_error(exc: OSError) -> ValidationError:
    """Translate filesystem failures without hiding the actionable cause."""
    error_name = errno.errorcode.get(exc.errno or 0, "UNKNOWN")
    quota_errors = {errno.ENOSPC}
    if hasattr(errno, "EDQUOT"):
        quota_errors.add(errno.EDQUOT)
    if exc.errno in quota_errors:
        return ValidationError(
            "المساحة أو حصة التخزين على الخادم لا تكفي لحفظ ملف التحديث. "
            f"رمز التخزين: {error_name}."
        )
    if exc.errno in {errno.EACCES, errno.EPERM, errno.EROFS}:
        return ValidationError(
            "مجلد حفظ التحديثات غير قابل للكتابة من خدمة الموقع. "
            f"رمز التخزين: {error_name}."
        )
    return ValidationError(
        "تعذر حفظ ملف التحديث على الخادم. "
        f"رمز التخزين: {error_name}."
    )


def _size_display(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("بايت", "ك.ب", "م.ب", "ج.ب"):
        if size < 1024 or unit == "ج.ب":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} بايت"


def _safe_slug(value: str, fallback: str = "opal_version") -> str:
    cleaned = get_valid_filename((value or "").strip())
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned).strip("._-")
    return cleaned[:100] or fallback


def _is_excluded(relative: Path) -> bool:
    if any(part in EXCLUDED_DIRECTORY_NAMES for part in relative.parts):
        return True
    if relative.name in EXCLUDED_FILE_NAMES:
        return True
    if relative.name.startswith(".env") and relative.name != ".env.example":
        return True
    if relative.suffix.lower() in EXCLUDED_EXTENSIONS:
        return True
    return False


def _iter_code_files(root: Path) -> Iterable[tuple[Path, Path]]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if _is_excluded(relative):
            continue
        yield path, relative


def _safe_zip_members(archive: zipfile.ZipFile) -> None:
    total_uncompressed = 0
    for member in archive.infolist():
        name = member.filename.replace("\\", "/")
        path = PurePosixPath(name)
        if not name or path.is_absolute() or ".." in path.parts:
            raise ValidationError("ملف ZIP يحتوي على مسار غير آمن.")
        unix_mode = (member.external_attr >> 16) & 0o170000
        if unix_mode == 0o120000:
            raise ValidationError("لا يسمح بوجود روابط رمزية داخل ملف التحديث.")
        if member.file_size > 250 * 1024 * 1024:
            raise ValidationError("يوجد ملف ضخم وغير مسموح داخل الحزمة.")
        total_uncompressed += member.file_size
        if total_uncompressed > 500 * 1024 * 1024:
            raise ValidationError("الحجم غير المضغوط للحزمة أكبر من الحد الآمن.")


def inspect_package(path: Path) -> PackageInspection:
    if not zipfile.is_zipfile(path):
        return PackageInspection(False, "", path.stem, "الملف ليس ZIP صالحًا.")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            _safe_zip_members(archive)
            bad_member = archive.testzip()
            if bad_member:
                return PackageInspection(False, "", path.stem, f"ملف تالف داخل الحزمة: {bad_member}")
            names = [name.replace("\\", "/").rstrip("/") for name in archive.namelist()]
            manage_names = [name for name in names if name == "manage.py" or name.endswith("/manage.py")]
            if not manage_names:
                return PackageInspection(False, "", path.stem, "لا تحتوي الحزمة على manage.py.")
            manage_names.sort(key=lambda item: (len(PurePosixPath(item).parts), item))
            selected = PurePosixPath(manage_names[0])
            selected_depth = len(selected.parts)
            if sum(1 for item in manage_names if len(PurePosixPath(item).parts) == selected_depth) > 1:
                return PackageInspection(False, "", path.stem, "تحتوي الحزمة على أكثر من مشروع في المستوى نفسه.")
            prefix = "" if str(selected.parent) == "." else str(selected.parent).rstrip("/") + "/"
            required = {f"{prefix}manage.py", f"{prefix}core", f"{prefix}templates"}
            normalized_set = set(names)
            has_core = any(name == f"{prefix}core" or name.startswith(f"{prefix}core/") for name in normalized_set)
            has_templates = any(name == f"{prefix}templates" or name.startswith(f"{prefix}templates/") for name in normalized_set)
            if not has_core or not has_templates:
                return PackageInspection(False, prefix, path.stem, "الحزمة لا تحتوي على core وtemplates بالشكل المتوقع.")

            version_name = path.stem
            notes = ""
            manifest_candidates = [MANIFEST_NAME, f"{prefix}{MANIFEST_NAME}"]
            for manifest_name in manifest_candidates:
                if manifest_name in archive.namelist():
                    try:
                        data = json.loads(archive.read(manifest_name).decode("utf-8"))
                        version_name = str(data.get("version_name") or data.get("name") or version_name)
                        notes = str(data.get("notes") or "")
                    except (UnicodeDecodeError, json.JSONDecodeError, KeyError):
                        notes = "تعذر قراءة بيانات manifest؛ تم الاعتماد على بنية المشروع."
                    break
            return PackageInspection(True, prefix, version_name, notes)
    except (zipfile.BadZipFile, OSError, ValidationError) as exc:
        return PackageInspection(False, "", path.stem, str(exc))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata_path(path: Path) -> Path:
    return path.with_suffix(".json")


def _write_metadata(path: Path, data: dict[str, object]) -> None:
    metadata = _metadata_path(path)
    metadata.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        metadata.chmod(0o600)
    except OSError:
        pass


def _read_metadata(path: Path) -> dict[str, object]:
    metadata = _metadata_path(path)
    if not metadata.is_file():
        return {}
    try:
        return json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _append_audit(action: str, username: str, details: str) -> None:
    try:
        log_path = private_storage_root() / "system_operations.log"
        safe_details = details.replace("\n", " ")[:4000]
        line = f"{timezone.localtime().isoformat()}\t{username or 'system'}\t{action}\t{safe_details}\n"
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(line)
        try:
            log_path.chmod(0o600)
        except OSError:
            pass
    except OSError:
        pass


def _run(
    command: list[str],
    *,
    timeout: int = 180,
    check: bool = True,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("LC_ALL", "C.UTF-8")
    try:
        result = subprocess.run(
            command,
            cwd=cwd or project_root(),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SystemUpdateError("انتهت مهلة العملية قبل اكتمالها.") from exc
    except OSError as exc:
        raise SystemUpdateError(f"تعذر تشغيل الأمر: {command[0]}") from exc
    if check and result.returncode != 0:
        output = (result.stdout or "").strip()[-MAX_COMMAND_OUTPUT:]
        raise SystemUpdateError(output or f"فشل الأمر برمز {result.returncode}.")
    return result


def _sanitize_remote(remote: str) -> str:
    value = (remote or "").strip()
    value = re.sub(r"(https?://)[^/@]+@", r"\1", value)
    value = re.sub(r"(https?://)[^/:]+:[^/@]+@", r"\1", value)
    return value


def get_git_status() -> GitStatus:
    root = project_root()
    if not (root / ".git").exists() or shutil.which("git") is None:
        return GitStatus(available=False, error="المشروع غير مربوط بمستودع Git.")
    try:
        branch = _run(["git", "branch", "--show-current"], timeout=20).stdout.strip()
        commit = _run(["git", "rev-parse", "--short=12", "HEAD"], timeout=20).stdout.strip()
        remote_result = _run(["git", "remote", "get-url", "origin"], timeout=20, check=False)
        remote = _sanitize_remote(remote_result.stdout) if remote_result.returncode == 0 else ""
        status = _run(["git", "status", "--porcelain"], timeout=30).stdout
        return GitStatus(
            available=True,
            branch=branch or "detached HEAD",
            commit=commit,
            remote=remote,
            has_changes=bool(status.strip()),
        )
    except SystemUpdateError as exc:
        return GitStatus(available=False, error=str(exc))


def _code_release_identity(root: Path) -> tuple[str, str]:
    """Return the release carried by the deployed source tree.

    The private deployment marker records *how* a package was restored, but it may
    legitimately survive a manual rsync deployment.  Therefore it must not mask a
    newer release identity shipped by the code itself.
    """
    version_path = root / "OPAL_VERSION.txt"
    release_name_path = root / "OPAL_RELEASE_NAME.txt"
    try:
        version = version_path.read_text(encoding="utf-8").strip() if version_path.is_file() else ""
    except OSError:
        version = ""
    try:
        release_name = (
            release_name_path.read_text(encoding="utf-8").strip()
            if release_name_path.is_file()
            else ""
        )
    except OSError:
        release_name = ""
    if release_name:
        return release_name[:160], "OPAL release metadata"
    if version:
        return f"OPAL Update {version}", "OPAL_VERSION.txt"
    return "", ""


def get_current_version() -> CurrentVersion:
    root = project_root()
    status = get_git_status()
    marker_path = private_storage_root() / DEPLOYED_MARKER
    marker: dict[str, object] = {}
    if marker_path.is_file():
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            marker = {}

    code_name, code_source = _code_release_identity(root)
    # The code release is authoritative.  A previous private marker is retained
    # only for deployment time/source metadata and cannot rename newer code.
    name = code_name or str(marker.get("version_name") or "")
    source = code_source or str(marker.get("source") or "")
    deployed_at = str(marker.get("deployed_at") or "")
    if not name and status.available:
        exact_tag = _run(["git", "describe", "--tags", "--exact-match", "HEAD"], timeout=20, check=False)
        if exact_tag.returncode == 0 and exact_tag.stdout.strip():
            name = exact_tag.stdout.strip()
            source = "Git tag"
        else:
            name = f"{status.branch} — {status.commit}"
            source = "Git"
    if not name:
        name = "نسخة غير مسماة"
        source = "النظام الحالي"
    return CurrentVersion(
        name=name,
        source=source,
        branch=status.branch if status.available else "",
        commit=status.commit if status.available else "",
        deployed_at=deployed_at,
        has_changes=status.has_changes if status.available else False,
    )


def _create_snapshot_impl(
    *,
    username: str,
    requested_name: str,
    source_type: str,
    notes: str = "",
) -> LocalVersionRecord:
    root = project_root()
    status = get_git_status()
    timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    default_name = f"OPAL_CURRENT_{timestamp}"
    version_name = (requested_name or "").strip()[:120] or default_name
    filename = f"{_safe_slug(version_name, default_name)}_{timestamp}.zip"
    final_path = versions_dir() / filename

    files = list(_iter_code_files(root))
    estimated = sum(path.stat().st_size for path, _relative in files)
    free_space = shutil.disk_usage(versions_dir()).free
    minimum_required = max(5 * 1024 * 1024, int(estimated * 1.25))
    if free_space < minimum_required:
        raise SystemUpdateError("المساحة المتاحة لا تكفي لإنشاء نسخة الكود الحالية.")

    manifest = {
        "schema": 2,
        "product": "OPAL ERP",
        "version_name": version_name,
        "source_type": source_type,
        "created_at": timezone.localtime().isoformat(),
        "created_by": username or "system",
        "branch": status.branch if status.available else "",
        "commit": status.commit if status.available else "",
        "notes": notes,
        "code_only": True,
        "excluded": ["database", "media", "virtual_environment", ".env", ".git", "collected_static"],
    }

    temporary_path = final_path.with_name(f".{final_path.name}.partial")
    try:
        with zipfile.ZipFile(
            temporary_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
            root_name = root.name
            for path, relative in files:
                archive.write(path, Path(root_name) / relative)
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, final_path)
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        if exc.errno == errno.ENOSPC:
            raise SystemUpdateError("امتلأت المساحة أثناء إنشاء النسخة الحالية.") from exc
        raise SystemUpdateError("تعذر إنشاء نسخة النظام الحالية.") from exc

    record = LocalVersionRecord(
        filename=final_path.name,
        version_name=version_name,
        source_type=source_type,
        source_display={
            "current_snapshot": "نسخة من النظام الحالي",
            "safety_snapshot": "نسخة أمان تلقائية",
            "uploaded_update": "تحديث مرفوع",
        }.get(source_type, source_type),
        size_bytes=final_path.stat().st_size,
        sha256=_sha256(final_path),
        saved_at=timezone.localtime().isoformat(),
        saved_by=username or "system",
        branch=status.branch if status.available else "",
        commit=status.commit if status.available else "",
        compatible=True,
        notes=notes,
    )
    _write_metadata(final_path, asdict(record))
    _append_audit("snapshot_created", username, f"{record.filename} source={source_type} sha256={record.sha256}")
    return record


def create_current_snapshot(*, username: str, version_name: str = "") -> LocalVersionRecord:
    lock_path = private_storage_root() / ".system_version.lock"
    with lock_path.open("w", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SystemUpdateError("توجد عملية نسخ أو تحديث أخرى قيد التنفيذ.") from exc
        return _create_snapshot_impl(
            username=username,
            requested_name=version_name,
            source_type="current_snapshot",
            notes="نسخة كود فقط دون قاعدة البيانات أو media أو البيئة الافتراضية.",
        )


def save_uploaded_update(uploaded_file, *, username: str) -> LocalVersionRecord:
    if uploaded_file is None:
        raise ValidationError("اختر ملف النسخة أو التحديث أولًا.")
    original_name = Path(uploaded_file.name or "opal_update.zip").name
    if Path(original_name).suffix.lower() != ".zip":
        raise ValidationError("يسمح برفع ملفات ZIP فقط.")
    if uploaded_file.size and uploaded_file.size > max_package_bytes():
        limit_mb = max_package_bytes() // (1024 * 1024)
        raise ValidationError(f"حجم الملف أكبر من الحد المسموح ({limit_mb} م.ب).")

    temporary_path: Path | None = None
    bytes_written = 0
    try:
        directory = versions_dir()
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        final_name = f"UPLOAD_{_safe_slug(Path(original_name).stem)}_{timestamp}.zip"
        final_path = directory / final_name
        fd, temporary_name = tempfile.mkstemp(prefix=".upload_", suffix=".zip", dir=directory)
        os.close(fd)
        temporary_path = Path(temporary_name)
        with temporary_path.open("wb") as destination:
            for chunk in uploaded_file.chunks():
                bytes_written += len(chunk)
                if bytes_written > max_package_bytes():
                    limit_mb = max_package_bytes() // (1024 * 1024)
                    raise ValidationError(f"تجاوز الملف الحد المسموح ({limit_mb} م.ب).")
                destination.write(chunk)
        inspection = inspect_package(temporary_path)
        if not inspection.compatible:
            raise ValidationError(f"الحزمة غير متوافقة: {inspection.notes}")
        digest = _sha256(temporary_path)
        status = get_git_status()
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, final_path)
        temporary_path = None
        record = LocalVersionRecord(
            filename=final_name,
            version_name=inspection.version_name or Path(original_name).stem,
            source_type="uploaded_update",
            source_display="تحديث مرفوع",
            size_bytes=bytes_written,
            sha256=digest,
            saved_at=timezone.localtime().isoformat(),
            saved_by=username or "system",
            branch=status.branch if status.available else "",
            commit=status.commit if status.available else "",
            compatible=True,
            notes=inspection.notes,
        )
        try:
            _write_metadata(final_path, asdict(record) | {"original_name": original_name})
        except OSError as metadata_error:
            error_name = errno.errorcode.get(metadata_error.errno or 0, "UNKNOWN")
            _append_audit(
                "update_metadata_failed",
                username,
                f"{final_name} storage_code={error_name}",
            )
        _append_audit("update_uploaded", username, f"{final_name} sha256={record.sha256}")
        return record
    except OSError as exc:
        raise _upload_storage_validation_error(exc) from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _record_from_path(path: Path) -> LocalVersionRecord:
    data = _read_metadata(path)
    stat = path.stat()
    inspection = inspect_package(path) if "compatible" not in data else None
    source_type = str(data.get("source_type") or "legacy_uploaded")
    source_display = str(data.get("source_display") or {
        "current_snapshot": "نسخة من النظام الحالي",
        "safety_snapshot": "نسخة أمان تلقائية",
        "uploaded_update": "تحديث مرفوع",
        "legacy_uploaded": "نسخة محفوظة سابقًا",
    }.get(source_type, source_type))
    compatible = bool(data.get("compatible", inspection.compatible if inspection else True))
    notes = str(data.get("notes") or (inspection.notes if inspection else ""))
    return LocalVersionRecord(
        filename=path.name,
        version_name=str(data.get("version_name") or (inspection.version_name if inspection else path.stem)),
        source_type=source_type,
        source_display=source_display,
        size_bytes=int(data.get("size_bytes") or stat.st_size),
        sha256=str(data.get("sha256") or _sha256(path)),
        saved_at=str(data.get("saved_at") or datetime.fromtimestamp(stat.st_mtime).isoformat()),
        saved_by=str(data.get("saved_by") or "غير معروف"),
        branch=str(data.get("branch") or ""),
        commit=str(data.get("commit") or ""),
        compatible=compatible,
        notes=notes,
    )


def list_local_versions(limit: int = 60) -> list[LocalVersionRecord]:
    paths: list[Path] = []
    paths.extend(versions_dir().glob("*.zip"))
    # توافق مع نسخ V1 التي كانت محفوظة مباشرة في المجلد الخاص.
    paths.extend(private_storage_root().glob("*.zip"))
    unique = {path.resolve(): path for path in paths}
    ordered = sorted(unique.values(), key=lambda item: item.stat().st_mtime, reverse=True)
    return [_record_from_path(path) for path in ordered[:limit]]


def _find_local_version_path(filename: str) -> Path:
    safe_name = Path(filename or "").name
    if not safe_name or safe_name != filename:
        raise SystemUpdateError("اسم النسخة غير صالح.")
    candidates = [versions_dir() / safe_name, private_storage_root() / safe_name]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise SystemUpdateError("لم يتم العثور على النسخة المختارة.")


def _extract_project_root(archive_path: Path, destination: Path) -> tuple[Path, PackageInspection]:
    inspection = inspect_package(archive_path)
    if not inspection.compatible:
        raise SystemUpdateError(f"الحزمة غير متوافقة: {inspection.notes}")
    with zipfile.ZipFile(archive_path, "r") as archive:
        _safe_zip_members(archive)
        archive.extractall(destination)
    root = destination / inspection.project_prefix.rstrip("/") if inspection.project_prefix else destination
    root = root.resolve()
    if not (root / "manage.py").is_file():
        raise SystemUpdateError("لم يتم العثور على manage.py بعد فك الحزمة.")
    return root, inspection


def _copy_tree_contents(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            shutil.copytree(child, target, dirs_exist_ok=True)
        else:
            shutil.copy2(child, target)


def _patch_urls(path: Path) -> None:
    if not path.is_file():
        raise SystemUpdateError("تعذر إبقاء مركز التحديثات: core/urls.py غير موجود.")
    content = path.read_text(encoding="utf-8")
    import_lines = (
        "from . import system_update_views",
        "from . import backup_file_actions",
    )
    lines = content.splitlines()
    insert_at = 0
    for index, line in enumerate(lines):
        if line.startswith("from ") or line.startswith("import "):
            insert_at = index + 1
    for import_line in import_lines:
        if import_line not in lines:
            lines.insert(insert_at, import_line)
            insert_at += 1
    content = "\n".join(lines).rstrip() + "\n"

    routes = [
        ('name="system_updates"', '    path("updates/", system_update_views.system_updates, name="system_updates"),'),
        ('name="updates_backup_files_api"', '    path("updates/files/api/", backup_file_actions.backup_files_api, name="updates_backup_files_api"),'),
        ('name="updates_download_backup"', '    path("updates/files/download/", backup_file_actions.download_backup_file, name="updates_download_backup"),'),
        ('name="updates_delete_backup"', '    path("updates/files/delete/", backup_file_actions.delete_backup_file, name="updates_delete_backup"),'),
    ]
    missing = [route for marker, route in routes if marker not in content]
    if missing:
        close_index = content.rfind("]")
        if close_index == -1:
            raise SystemUpdateError("تعذر تحديد urlpatterns داخل core/urls.py.")
        content = content[:close_index] + "\n".join(missing) + "\n" + content[close_index:]
    path.write_text(content, encoding="utf-8")


def _patch_system_settings_template(path: Path) -> None:
    if not path.is_file():
        return
    content = path.read_text(encoding="utf-8")
    # إزالة بطاقة V1 أو نسخة V2 قديمة قبل إعادة الإدراج.
    content = re.sub(
        r"\n?\{# OPAL_SYSTEM_UPDATES_PAGE_V[12] #\}.*?\{% endif %\}\n?",
        "\n",
        content,
        flags=re.DOTALL,
    )
    card = '''\n{# OPAL_SYSTEM_UPDATES_PAGE_V2 #}\n{% if request.user.is_superuser %}\n<div class="opal-card mb-4">\n    <h3 class="fw-bold mb-3"><i class="bi bi-arrow-repeat"></i> مركز تحديثات النظام</h3>\n    <p class="text-secondary">حفظ نسخة الكود الحالية، رفع تحديث، استعادة نسخة محفوظة، وإدارة نسخ GitHub.</p>\n    <a href="{% url 'core:system_updates' %}" class="btn btn-dark">\n        <i class="bi bi-gear-wide-connected"></i> فتح مركز تحديثات النظام\n    </a>\n</div>\n{% endif %}\n'''
    token = "{% block content %}"
    if token not in content:
        raise SystemUpdateError("تعذر إضافة رابط مركز التحديثات إلى صفحة الإعدادات.")
    content = content.replace(token, token + card, 1)
    path.write_text(content, encoding="utf-8")


def _reapply_update_tool_overlay() -> None:
    """Reapply only the stable entry point kept outside normal code swaps.

    The implementation is intentionally stored in ``update_engine_runtime``
    (which is updated with the package).  Keeping only this tiny entry point
    in the permanent overlay prevents an old update center from overwriting a
    newer safety implementation after a successful restore.
    """
    source = engine_dir() / "payload"
    if not source.is_dir():
        raise SystemUpdateError("ملفات محرك التحديثات الدائم غير موجودة.")
    root = project_root()
    for relative in (Path("core/system_update_service.py"),):
        source_file = source / relative
        if not source_file.is_file():
            raise SystemUpdateError(f"ملف محرك التحديثات مفقود: {relative}")
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, destination)
    _patch_urls(root / "core" / "urls.py")
    _patch_system_settings_template(root / "templates" / "core" / "system_settings.html")


def _synchronize_release_identity_from_source(source_root: Path, deployed_root: Path) -> None:
    """Copy release identity explicitly and reject an incoherent deployment."""
    for filename in RELEASE_IDENTITY_FILES:
        source_file = source_root / filename
        if not source_file.is_file():
            raise SystemUpdateError(f"ملف هوية الإصدار مفقود داخل الحزمة: {filename}")
        shutil.copy2(source_file, deployed_root / filename)

    try:
        version = (deployed_root / "OPAL_VERSION.txt").read_text(encoding="utf-8").strip()
        release_name = (deployed_root / "OPAL_RELEASE_NAME.txt").read_text(encoding="utf-8").strip()
        manifest = json.loads((deployed_root / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemUpdateError("تعذر قراءة هوية الإصدار بعد نسخ التحديث.") from exc

    if manifest.get("version") != version or manifest.get("version_name") != release_name:
        raise SystemUpdateError(
            "هوية الإصدار غير متسقة بعد التحديث؛ أُوقفت العملية لحماية نقطة النشر."
        )


def _replace_project_code(source_root: Path) -> None:
    root = project_root()
    for child in list(root.iterdir()):
        if child.name in PROTECTED_TOP_LEVEL:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    for child in source_root.iterdir():
        if child.name in PROTECTED_TOP_LEVEL:
            continue
        target = root / child.name
        if child.is_dir():
            shutil.copytree(child, target, dirs_exist_ok=True)
        else:
            shutil.copy2(child, target)
    _synchronize_release_identity_from_source(source_root, root)
    _reapply_update_tool_overlay()


def _run_post_restore_checks(*, run_migrations: bool) -> None:
    python_bin = python_executable()
    _run([python_bin, "manage.py", "check"], timeout=180)
    _run([python_bin, "manage.py", "makemigrations", "--check", "--dry-run"], timeout=180)
    if run_migrations:
        _run([python_bin, "manage.py", "migrate", "--noinput"], timeout=300)
    _run([python_bin, "manage.py", "collectstatic", "--noinput"], timeout=300)
    _run([python_bin, "manage.py", "check"], timeout=180)


def _write_deployed_marker(
    *,
    version_name: str,
    source: str,
    username: str,
    safety_snapshot: str,
    database_safety_snapshot: str,
) -> None:
    status = get_git_status()
    data = {
        "version_name": version_name,
        "source": source,
        "deployed_at": timezone.localtime().isoformat(),
        "deployed_by": username or "system",
        "branch": status.branch if status.available else "",
        "commit": status.commit if status.available else "",
        "safety_snapshot": safety_snapshot,
        "database_safety_snapshot": database_safety_snapshot,
    }
    marker = private_storage_root() / DEPLOYED_MARKER
    marker.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        marker.chmod(0o600)
    except OSError:
        pass


def _apply_archive(
    archive_path: Path,
    *,
    username: str,
    source_label: str,
    requested_version_name: str = "",
) -> RestoreResult:
    inspection = inspect_package(archive_path)
    if not inspection.compatible:
        raise SystemUpdateError(f"الحزمة غير متوافقة: {inspection.notes}")
    safety = _create_snapshot_impl(
        username=username,
        requested_name=f"SAFETY_BEFORE_{timezone.localtime().strftime('%Y%m%d_%H%M%S')}",
        source_type="safety_snapshot",
        notes=f"نسخة أمان تلقائية قبل استعادة {requested_version_name or inspection.version_name}.",
    )
    database_safety = _create_database_safety_snapshot()
    with tempfile.TemporaryDirectory(prefix="opal_restore_", dir=private_storage_root()) as temporary_directory:
        extracted_root, inspection = _extract_project_root(archive_path, Path(temporary_directory))
        try:
            _replace_project_code(extracted_root)
            _run_post_restore_checks(run_migrations=True)
        except Exception as original_exc:
            # Restore both the previous code and the exact SQLite state from
            # before migrations.  No --fake migration is used here.
            try:
                with tempfile.TemporaryDirectory(prefix="opal_rollback_", dir=private_storage_root()) as rollback_temp:
                    rollback_root, _rollback_inspection = _extract_project_root(
                        _find_local_version_path(safety.filename), Path(rollback_temp)
                    )
                    _replace_project_code(rollback_root)
                    _restore_database_safety_snapshot(database_safety)
                    _run_post_restore_checks(run_migrations=False)
            except Exception as rollback_exc:
                raise SystemUpdateError(
                    f"فشلت الاستعادة وفشل الرجوع التلقائي أيضًا. الخطأ الأصلي: {original_exc}. "
                    f"خطأ الرجوع: {rollback_exc}"
                ) from rollback_exc
            raise SystemUpdateError(
                "فشلت الاستعادة وتمت إعادة الكود وقاعدة البيانات إلى ما قبل التحديث تلقائيًا. "
                f"السبب: {original_exc}"
            ) from original_exc

    final_name = requested_version_name or inspection.version_name or archive_path.stem
    _write_deployed_marker(
        version_name=final_name,
        source=source_label,
        username=username,
        safety_snapshot=safety.filename,
        database_safety_snapshot=database_safety.name,
    )
    _append_audit(
        "version_restored",
        username,
        f"version={final_name} source={source_label} safety={safety.filename} database={database_safety.name}",
    )
    return RestoreResult(
        version_name=final_name,
        source=source_label,
        safety_snapshot=safety.filename,
        message="تمت استعادة الكود وتشغيل الفحص والترحيلات وتجميع الملفات الثابتة.",
        database_safety_snapshot=database_safety.name,
    )


def restore_local_version(*, filename: str, username: str, confirmation: str) -> RestoreResult:
    if (confirmation or "").strip() != CONFIRMATION_WORD:
        raise ValidationError(f"اكتب كلمة {CONFIRMATION_WORD} لتأكيد الاستعادة.")
    lock_path = private_storage_root() / ".system_version.lock"
    with lock_path.open("w", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SystemUpdateError("توجد عملية نسخ أو تحديث أخرى قيد التنفيذ.") from exc
        path = _find_local_version_path(filename)
        record = _record_from_path(path)
        if not record.compatible:
            raise SystemUpdateError("النسخة المختارة غير متوافقة مع نظام الاستعادة.")
        return _apply_archive(
            path,
            username=username,
            source_label="نسخة محفوظة على النظام",
            requested_version_name=record.version_name,
        )


def _path_forbidden(path: str) -> bool:
    normalized = path.replace("\\", "/")
    # Remove only a relative ``./`` prefix.  ``lstrip('./')`` would also
    # remove the leading dot from names such as .env.production.
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    for forbidden in FORBIDDEN_GIT_PATHS:
        if forbidden.endswith("/") and normalized.startswith(forbidden):
            return True
        if normalized == forbidden:
            return True
    filename = PurePosixPath(normalized).name.lower()
    if filename.startswith(".env") and filename != ".env.example":
        return True
    if filename.endswith(FORBIDDEN_GIT_SUFFIXES):
        return True
    return False


def _ensure_no_forbidden_tracked_files() -> None:
    result = _run(["git", "ls-files", "-z"], timeout=30)
    paths = [item for item in result.stdout.split("\0") if item]
    forbidden = [path for path in paths if _path_forbidden(path)]
    if forbidden:
        sample = "، ".join(forbidden[:8])
        raise SystemUpdateError(f"أوقف الرفع: توجد ملفات حساسة متتبعة داخل Git: {sample}")


def push_current_system_to_github(*, username: str) -> GitPushResult:
    status = get_git_status()
    if not status.available:
        raise SystemUpdateError(status.error or "Git غير متاح.")
    if not status.remote:
        raise SystemUpdateError("لا يوجد مستودع origin مرتبط بالمشروع.")
    if status.branch == "detached HEAD":
        raise SystemUpdateError("لا يمكن الرفع أثناء وجود Git في وضع detached HEAD.")

    lock_path = private_storage_root() / ".git_push.lock"
    with lock_path.open("w", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SystemUpdateError("توجد عملية رفع أخرى قيد التنفيذ.") from exc
        _run([python_executable(), "manage.py", "check"], timeout=180)
        _run([python_executable(), "manage.py", "makemigrations", "--check", "--dry-run"], timeout=180)
        _ensure_no_forbidden_tracked_files()
        _run(["git", "add", "-A"], timeout=60)
        _ensure_no_forbidden_tracked_files()
        staged = _run(["git", "diff", "--cached", "--quiet"], timeout=30, check=False)
        if staged.returncode not in (0, 1):
            raise SystemUpdateError((staged.stdout or "تعذر فحص تغييرات Git.").strip())
        created_commit = staged.returncode == 1
        if created_commit:
            timestamp = timezone.localtime().strftime("%Y-%m-%d %H:%M")
            actor = (username or "مدير النظام")[:80]
            message = f"OPAL ERP: حفظ النظام من مركز التحديثات - {timestamp} - {actor}"
            _run(["git", "commit", "-m", message], timeout=180)
        _run(["git", "push", "origin", status.branch], timeout=240)
        commit = _run(["git", "rev-parse", "--short=12", "HEAD"], timeout=20).stdout.strip()
        message = (
            "تم إنشاء Commit ورفع النظام إلى GitHub."
            if created_commit
            else "لا توجد تغييرات جديدة؛ تم التأكد من مزامنة الفرع مع GitHub."
        )
        _append_audit("github_push", username, f"branch={status.branch} commit={commit}")
        return GitPushResult(status.branch, commit, created_commit, message)


def get_github_versions(*, fetch: bool = False, limit: int = 120) -> list[GitVersionRecord]:
    status = get_git_status()
    if not status.available:
        return []
    if fetch:
        _run(["git", "fetch", "origin", "--prune", "--tags"], timeout=240)
    head_commit = _run(["git", "rev-parse", "HEAD"], timeout=20).stdout.strip()
    separator = "\x1f"
    format_string = separator.join(
        [
            "%(refname)",
            "%(refname:short)",
            "%(objectname)",
            "%(objectname:short)",
            "%(creatordate:iso8601-strict)",
            "%(creator)",
            "%(subject)",
        ]
    )
    result = _run(
        [
            "git",
            "for-each-ref",
            "--sort=-creatordate",
            f"--format={format_string}",
            "refs/remotes/origin",
            "refs/tags",
        ],
        timeout=60,
    )
    records: list[GitVersionRecord] = []
    seen_refs: set[tuple[str, str]] = set()
    seen_commits: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split(separator)
        if len(parts) != 7:
            continue
        ref, short_name, commit, short_commit, committed_at, author, subject = parts
        if ref == "refs/remotes/origin/HEAD" or short_name.endswith("/HEAD"):
            continue
        kind = "tag" if ref.startswith("refs/tags/") else "branch"
        key = (kind, short_name)
        if key in seen_refs:
            continue
        seen_refs.add(key)
        # Resolve annotated tags to their underlying commit for accurate comparison and display.
        resolved = _run(["git", "rev-list", "-n", "1", ref], timeout=20, check=False)
        resolved_commit = resolved.stdout.strip() if resolved.returncode == 0 else commit
        resolved_short = resolved_commit[:12] if resolved_commit else short_commit
        if resolved_commit:
            seen_commits.add(resolved_commit)
        records.append(
            GitVersionRecord(
                ref=ref,
                short_name=short_name,
                kind=kind,
                kind_display="وسم Tag" if kind == "tag" else "فرع",
                commit=resolved_commit or commit,
                short_commit=resolved_short,
                committed_at=committed_at,
                author=author,
                subject=subject,
                is_current=(resolved_commit or commit) == head_commit,
            )
        )

    # عرض سجل الـ Commits أيضًا، حتى يمكن استعادة نقطة سابقة لا تحمل فرعًا أو Tag مستقلًا.
    log_format = "%H%x1f%h%x1f%cI%x1f%an%x1f%s"
    log_result = _run(
        ["git", "log", "--all", f"--pretty=format:{log_format}", "--max-count=100"],
        timeout=90,
        check=False,
    )
    if log_result.returncode == 0:
        for line in log_result.stdout.splitlines():
            parts = line.split(separator)
            if len(parts) != 5:
                continue
            commit, short_commit, committed_at, author, subject = parts
            if commit in seen_commits:
                continue
            seen_commits.add(commit)
            records.append(
                GitVersionRecord(
                    ref=commit,
                    short_name=f"Commit {short_commit}",
                    kind="commit",
                    kind_display="Commit",
                    commit=commit,
                    short_commit=short_commit,
                    committed_at=committed_at,
                    author=author,
                    subject=subject,
                    is_current=commit == head_commit,
                )
            )

    records.sort(key=lambda item: item.committed_at or "", reverse=True)
    return records[:limit]


def restore_github_version(*, ref: str, username: str, confirmation: str) -> RestoreResult:
    if (confirmation or "").strip() != CONFIRMATION_WORD:
        raise ValidationError(f"اكتب كلمة {CONFIRMATION_WORD} لتأكيد الاستعادة.")
    lock_path = private_storage_root() / ".system_version.lock"
    with lock_path.open("w", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SystemUpdateError("توجد عملية نسخ أو تحديث أخرى قيد التنفيذ.") from exc
        versions = get_github_versions(fetch=True)
        selected = next((item for item in versions if item.ref == ref), None)
        if selected is None:
            raise SystemUpdateError("نسخة GitHub المختارة غير موجودة أو لم تعد متاحة.")
        fd, temp_name = tempfile.mkstemp(prefix="opal_git_", suffix=".zip", dir=private_storage_root())
        os.close(fd)
        archive_path = Path(temp_name)
        try:
            _run(
                ["git", "archive", "--format=zip", f"--output={archive_path}", selected.ref],
                timeout=180,
            )
            return _apply_archive(
                archive_path,
                username=username,
                source_label=f"GitHub — {selected.kind_display}",
                requested_version_name=selected.short_name,
            )
        finally:
            archive_path.unlink(missing_ok=True)
