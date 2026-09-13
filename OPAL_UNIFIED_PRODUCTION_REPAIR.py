#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

FORBIDDEN_PREFIXES = ("media/", "uploads/", "staticfiles/", "collected_static/", "venv/", ".venv/", "env/")
FORBIDDEN_EXACT = ("db.sqlite3", "db.sqlite")

class RepairError(RuntimeError):
    pass

class Repair:
    def __init__(self, root: Path, apply: bool):
        self.root = root.resolve()
        self.apply = apply
        self.changed = []
        self.skipped = []
        self.notes = []
        self.backup_root = self.root / ".opal_repair_backups" / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.manifest = self._manifest()

    def _manifest(self):
        p = self.root / "OPAL_UPDATE_MANIFEST.json"
        if not p.is_file():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RepairError(f"OPAL_UPDATE_MANIFEST.json غير صالح: {exc}")

    def write(self, rel, content):
        p = self.root / rel
        old = p.read_text(encoding="utf-8") if p.exists() else None
        if old == content:
            self.skipped.append(str(rel))
            return False
        if self.apply:
            if p.exists():
                dst = self.backup_root / Path(rel)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dst)
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        self.changed.append(str(rel))
        return True

    def patch_release_helper(self):
        rel = "core/release_contract_assertions.py"
        p = self.root / rel
        if not p.is_file():
            return
        t = p.read_text(encoding="utf-8")
        if "import re" not in t:
            t = t.replace("import json\n", "import json\nimport re\n", 1)
        t = t.replace(
            '    test_case.assertEqual(version, "131.7")\n    test_case.assertRegex(release_name, r"OPAL Update 131\\.7 R\\d+ - .+")\n',
            '    test_case.assertTrue(version, "OPAL_VERSION.txt لا يحتوي رقم إصدار.")\n    test_case.assertRegex(release_name, rf"OPAL Update {re.escape(version)} R\\d+ - .+")\n',
        )
        self.write(rel, t)

    def patch_checks(self):
        rel = "core/checks.py"
        p = self.root / rel
        if not p.is_file():
            return
        t = p.read_text(encoding="utf-8")
        t = t.replace('css_path = root / "static/css/opal_erp.css"', 'css_path = root / "static/css/opal_theme_system.css"')
        t = t.replace('"path": "static/css/opal_erp.css",', '"path": "static/css/opal_theme_system.css",')
        old = """    version_file = root / "OPAL_VERSION.txt"
    version = version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else ""
    if version != "131.7":
        issues.append({
            "code": "TIMETABLE_RELEASE_IDENTITY_MISMATCH",
            "message": f"هوية الكود الفعلية يجب أن تكون 131.7 وليست {version or 'غير محددة'}.",
            "path": "OPAL_VERSION.txt",
        })
"""
        new = """    version_file = root / "OPAL_VERSION.txt"
    manifest_file = root / "OPAL_UPDATE_MANIFEST.json"
    version = version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else ""
    manifest_version = ""
    if manifest_file.is_file():
        try:
            import json
            manifest_version = str(json.loads(manifest_file.read_text(encoding="utf-8")).get("version") or "").strip()
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            manifest_version = ""
    if not version or not manifest_version or version != manifest_version:
        issues.append({
            "code": "TIMETABLE_RELEASE_IDENTITY_MISMATCH",
            "message": (
                "هوية الإصدار غير متسقة بين OPAL_VERSION.txt وOPAL_UPDATE_MANIFEST.json: "
                f"version={version or 'غير محددة'} manifest={manifest_version or 'غير محددة'}."
            ),
            "path": "OPAL_VERSION.txt",
        })
"""
        if old in t:
            t = t.replace(old, new, 1)
        self.write(rel, t)

    def patch_css_contract_paths(self):
        for rel in (
            "core/live_events_matrix_contracts.py",
            "core/final_reengineering_audit.py",
        ):
            p = self.root / rel
            if not p.is_file():
                continue
            t = p.read_text(encoding="utf-8")
            t = t.replace("static/css/opal_erp.css", "static/css/opal_theme_system.css")
            self.write(rel, t)

        rel = "core/subject_ui_contracts.py"
        p = self.root / rel
        if p.is_file():
            t = p.read_text(encoding="utf-8")
            start = t.find("    required = {")
            end = t.find("\n\n    for relative, markers in required.items():", start)
            if start >= 0 and end >= 0:
                block = """    required = {
        "core/templatetags/opal_subjects.py": (
            "strict hexadecimal whitelist", "subject_style", "subject_colour",
        ),
        # One active shared CSS authority after R87/R89 consolidation.
        "static/css/opal_theme_system.css": (
            ".opal-subject-chip", ".opal-subject-card",
            ".opal-compact-module-grid", ".opal-compact-action-row",
            "grid-template-columns:repeat(3,minmax(0,1fr))!important",
            ".opal-fixed-manager-dashboard", ".opal-manager-quick-row",
            ".opal-fixed-manager-dashboard .opal-dashboard-subject-chip",
        ),
        "templates/base/base.html": ("css/opal_theme_system.css",),
        "timetable/live_services.py": (
            'subject_color = entry.subject.color or "#64748B"', '"subject_color": subject_color',
        ),
        "dashboard/templates/dashboard/home.html": (
            "opal-actions-fixed-row", "subject_style item.subject_color",
            "subject_style row.entry.subject", "opal-fixed-manager-dashboard",
            "opal-dashboard-subject-chip",
        ),
        "templates/teachers/portal_dashboard.html": (
            "opal-compact-module-grid", "opal-compact-subject-grid", "subject_style a.subject",
        ),
        "templates/parent_portal/dashboard.html": (
            "opal-parent-metric-grid", "opal-compact-module-grid",
        ),
        "templates/students/student_360.html": (
            "opal-compact-action-row", "opal-compact-metric-grid",
            "opal-compact-tabs", "subject_style row.exam.subject",
        ),
        "templates/exams/gradebook.html": (
            "opal-subject-card", "exam__subject__color", "subject_style mark.exam.subject",
        ),
    }"""
                t = t[:start] + block + t[end:]
                self.write(rel, t)

    def patch_database_safety(self):
        rel = "core/update_engine_runtime.py"
        p = self.root / rel
        if not p.is_file():
            return
        t = p.read_text(encoding="utf-8")
        marker = 'database_safety = database_safety_path.name if database_safety_path else ""'
        if marker in t:
            self.write(rel, t.replace("database_safety.name", "database_safety"))

    def patch_pytest(self):
        self.write("pytest.ini", "[pytest]\nDJANGO_SETTINGS_MODULE = config.settings\npython_files = test_*.py *_tests.py tests.py\naddopts = -ra\n")
        rel = "requirements.txt"
        p = self.root / rel
        if p.is_file():
            lines = p.read_text(encoding="utf-8").splitlines()
            names = {re.split(r"[<>=!~]", x.strip(), maxsplit=1)[0].lower() for x in lines if x.strip() and not x.lstrip().startswith("#")}
            add = []
            if "pytest" not in names:
                add.append("pytest>=8,<10")
            if "pytest-django" not in names:
                add.append("pytest-django>=4.8,<5")
            if add:
                self.write(rel, "\n".join(lines + [""] + add) + "\n")

    def patch_base_cache(self):
        rel = "templates/base/base.html"
        p = self.root / rel
        if not p.is_file():
            return
        version = str(self.manifest.get("version") or "").strip()
        revision = str(self.manifest.get("package_revision") or "").strip()
        if not version or not revision:
            return
        token = f"opal-{version}-r{revision}-css-authority"
        t = p.read_text(encoding="utf-8")
        t2 = re.sub(r"(opal_theme_system\.css'\s*%\}\?v=)[^\"'\s]+", r"\1" + token, t, count=1)
        self.write(rel, t2)

    def patch_historical_tests(self):
        mapping = {
            r"opal_erp\.css": r"opal_theme_system\.css",
            r"opal_dashboard_polish\.css": r"opal_theme_system\.css",
            r"opal_dashboard_executive\.css": r"opal_theme_system\.css",
            r"opal_entity_360_consolidation\.css": r"opal_theme_system\.css",
        }
        for p in list(self.root.rglob("test*.py")) + list(self.root.rglob("tests.py")):
            if any(x in p.parts for x in (".git", "venv", ".venv", "env", "__pycache__")):
                continue
            t = p.read_text(encoding="utf-8")
            if "base" not in t:
                continue
            old = t
            for a, b in mapping.items():
                t = t.replace(a, b)
            if t != old:
                self.write(str(p.relative_to(self.root)), t)

        rel = "core/test_update131_7_r10_aesthetic_finishing_contract.py"
        p = self.root / rel
        if p.is_file():
            t = p.read_text(encoding="utf-8")
            old = """        self.assertEqual(manifest["version"], "131.7")
        self.assertGreaterEqual(manifest["package_revision"], 13)
        self.assertTrue(manifest["code_only"])
        self.assertRegex(manifest["version_name"], r"OPAL Update 131\\.7 R\\d+ - .+")
"""
            new = """        version = str(manifest["version"]).strip()
        self.assertTrue(version)
        self.assertGreaterEqual(manifest["package_revision"], 13)
        self.assertTrue(manifest["code_only"])
        self.assertRegex(manifest["version_name"], rf"OPAL Update {re.escape(version)} R\\d+ - .+")
"""
            if old in t:
                t = t.replace("import json\n", "import json\nimport re\n", 1).replace(old, new, 1)
                self.write(rel, t)

        rel = "core/test_update131_7_r22_forward_compatible_release_contract.py"
        p = self.root / rel
        if p.is_file():
            t = p.read_text(encoding="utf-8")
            t2 = t.replace("self.assertIn(r'r\"OPAL Update 131\\.7 R\\d+ - .+\"', helper)", 'self.assertIn("re.escape(version)", helper)')
            self.write(rel, t2)

    def patch_remaining_forward_contracts(self):
        patches = {
            "core/test_update129_horizontal_timetable_contract.py": [
                ("self.assertIn('version != \"131.7\"', checks)", 'self.assertIn("manifest_version", checks)'),
            ],
            "core/test_update130_production_stability_contract.py": [
                ('self.assertEqual(version, "131.7")', 'self.assertEqual(manifest["version"], version)'),
            ],
            "core/test_update131_6_subject_ui_contract.py": [
                ('self.assertIn("css/opal_dashboard_executive.css", base)', 'self.assertIn("css/opal_theme_system.css", base)'),
            ],
        }
        for rel, replacements in patches.items():
            p = self.root / rel
            if not p.is_file():
                continue
            t = p.read_text(encoding="utf-8")
            original = t
            for old, new in replacements:
                t = t.replace(old, new)
            if t != original:
                self.write(rel, t)

    def patch_gitignore(self):
        rel = ".gitignore"
        p = self.root / rel
        base = p.read_text(encoding="utf-8") if p.is_file() else ""
        req = [".opal_repair_backups/", "staticfiles/", "media/", "db.sqlite3", "*.sqlite3", ".env", ".env.*", "venv/", ".venv/", "env/", "*.sqlite3-journal", "*.sqlite3-wal", "*.sqlite3-shm"]
        lines = base.splitlines()
        seen = {x.strip() for x in lines}
        missing = [x for x in req if x not in seen]
        if missing:
            if lines and lines[-1].strip():
                lines.append("")
            lines += ["# OPAL verified runtime/sensitive exclusions"] + missing
            self.write(rel, "\n".join(lines) + "\n")

    def untrack_runtime_files(self):
        if not (self.root / ".git").exists():
            self.notes.append("لا يوجد Git محلي؛ لم يتم تعديل index.")
            return
        r = subprocess.run(["git", "ls-files", "-z"], cwd=self.root, capture_output=True, check=True)
        files = [x.decode("utf-8", "replace") for x in r.stdout.split(b"\0") if x]
        remove = []
        for x in files:
            n = x.replace("\\", "/")
            if n in FORBIDDEN_EXACT or any(n.startswith(p) for p in FORBIDDEN_PREFIXES) or n.lower().endswith((".sqlite3", ".sqlite", ".db")):
                remove.append(x)
        if not remove:
            self.skipped.append("Git index runtime cleanup")
            return
        self.notes.append("إزالة من Git index فقط دون حذف من القرص: " + ", ".join(remove[:20]))
        if self.apply:
            subprocess.run(["git", "rm", "-r", "--cached", "--ignore-unmatch", "--", *remove], cwd=self.root, check=True)
        self.changed.append("Git index runtime cleanup")

    def verify(self, django_check):
        for rel in self.changed:
            if rel.endswith(".py"):
                ast.parse((self.root / rel).read_text(encoding="utf-8"), filename=rel)
        if django_check:
            try:
                import django  # noqa
            except Exception:
                self.notes.append("Django غير مثبت؛ تم تجاوز manage.py check.")
                return
            for cmd in ([sys.executable, "manage.py", "check"], [sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"]):
                r = subprocess.run(cmd, cwd=self.root, text=True, capture_output=True)
                if r.returncode:
                    raise RepairError("فشل " + " ".join(cmd) + "\n" + (r.stdout + "\n" + r.stderr)[-8000:])

    def run(self, verify=False):
        if not (self.root / "manage.py").is_file():
            raise RepairError(f"المسار ليس جذر مشروع OPAL: {self.root}")
        self.patch_release_helper()
        self.patch_checks()
        self.patch_css_contract_paths()
        self.patch_database_safety()
        self.patch_pytest()
        self.patch_base_cache()
        self.patch_historical_tests()
        self.patch_remaining_forward_contracts()
        self.patch_gitignore()
        self.untrack_runtime_files()
        if self.apply:
            self.verify(verify)
        return {
            "ok": True, "root": str(self.root), "apply": self.apply,
            "manifest_version": self.manifest.get("version"),
            "manifest_revision": self.manifest.get("package_revision"),
            "changed": self.changed, "skipped": self.skipped,
            "notes": self.notes,
            "backup": str(self.backup_root) if self.apply else "",
        }

def main():
    ap = argparse.ArgumentParser(description="OPAL ERP Unified Production Repair")
    ap.add_argument("--root", default=".")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    try:
        result = Repair(Path(a.root), a.apply).run(a.verify)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
