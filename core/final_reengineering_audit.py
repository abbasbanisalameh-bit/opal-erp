"""Read-only final audit helpers for OPAL ERP reengineering.

This module deliberately does not mutate database records or project files.
It consolidates structural checks used to certify the reengineered project while
preserving OPAL's existing behavior and visual identity.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

from django.apps import apps
from django.conf import settings
from django.template import engines
from django.urls import URLPattern, URLResolver, get_resolver


@dataclass(frozen=True)
class AuditIssue:
    code: str
    message: str
    path: str = ""

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def project_root() -> Path:
    return Path(settings.BASE_DIR).resolve()


def _iter_python_files(root: Path) -> Iterable[Path]:
    excluded = {".git", ".venv", "venv", "env", "__pycache__", "staticfiles", "media"}
    for path in root.rglob("*.py"):
        if excluded.intersection(path.parts):
            continue
        yield path


def audit_python_syntax(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    issues: list[AuditIssue] = []
    for path in _iter_python_files(root):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            issues.append(AuditIssue("python_syntax", str(exc), str(path.relative_to(root))))
    return issues


def audit_official_student_model() -> list[AuditIssue]:
    """Ensure OPAL's sole official student model remains students.Student."""
    issues: list[AuditIssue] = []
    try:
        official = apps.get_model("students", "Student")
    except LookupError:
        return [AuditIssue("student_model_missing", "النموذج الرسمي students.Student غير موجود.")]

    candidates = []
    for model in apps.get_models():
        if model.__name__.lower() == "student":
            candidates.append(f"{model._meta.app_label}.{model.__name__}")
    expected = f"{official._meta.app_label}.{official.__name__}"
    extras = sorted(candidate for candidate in candidates if candidate != expected)
    if extras:
        issues.append(
            AuditIssue(
                "duplicate_student_model",
                "تم العثور على نموذج Student موازٍ للنموذج الرسمي: " + ", ".join(extras),
            )
        )
    return issues


def _walk_urlpatterns(patterns, prefix=""):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            yield from _walk_urlpatterns(pattern.url_patterns, prefix + str(pattern.pattern))
        elif isinstance(pattern, URLPattern):
            yield prefix + str(pattern.pattern), pattern


def audit_named_urls() -> list[AuditIssue]:
    """Detect duplicate fully-qualified URL names without changing routing."""
    issues: list[AuditIssue] = []
    seen: dict[str, str] = {}
    resolver = get_resolver()

    def walk(patterns, namespaces=()):
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                next_namespaces = namespaces + ((pattern.namespace,) if pattern.namespace else ())
                walk(pattern.url_patterns, next_namespaces)
            elif isinstance(pattern, URLPattern) and pattern.name:
                full_name = ":".join((*namespaces, pattern.name))
                route = str(pattern.pattern)
                if full_name in seen and seen[full_name] != route:
                    issues.append(
                        AuditIssue(
                            "duplicate_url_name",
                            f"اسم الرابط {full_name} مرتبط بأكثر من مسار: {seen[full_name]} و {route}",
                        )
                    )
                else:
                    seen[full_name] = route

    walk(resolver.url_patterns)
    return issues


def audit_required_identity_files(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    required = (
        "templates/includes/sidebar.html",
        "templates/includes/topbar.html",
        "static/css/opal_erp.css",
    )
    return [
        AuditIssue("opal_identity_file_missing", "ملف أساسي من هوية OPAL غير موجود.", relative)
        for relative in required
        if not (root / relative).is_file()
    ]


def audit_templates() -> list[AuditIssue]:
    """Compile all project templates through Django's configured engine."""
    issues: list[AuditIssue] = []
    root = project_root()
    template_root = root / "templates"
    if not template_root.exists():
        return [AuditIssue("templates_root_missing", "مجلد templates غير موجود.")]

    engine = engines["django"]
    for path in template_root.rglob("*.html"):
        relative = path.relative_to(template_root).as_posix()
        try:
            engine.get_template(relative)
        except Exception as exc:  # Django template exceptions vary by backend.
            issues.append(AuditIssue("template_compile", str(exc), relative))
    return issues


def run_final_reengineering_audit(*, include_templates: bool = True) -> dict:
    checks = {
        "python_syntax": audit_python_syntax(),
        "official_student_model": audit_official_student_model(),
        "named_urls": audit_named_urls(),
        "opal_identity": audit_required_identity_files(),
    }
    if include_templates:
        checks["templates"] = audit_templates()

    issues = [issue for group in checks.values() for issue in group]
    return {
        "ok": not issues,
        "checks": {name: len(group) == 0 for name, group in checks.items()},
        "issue_count": len(issues),
        "issues": [issue.as_dict() for issue in issues],
    }
