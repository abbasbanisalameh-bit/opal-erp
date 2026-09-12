"""Read-only stability contracts for OPAL's global runtime shell.

The checks in this module protect the canonical navigation, template shell,
context-processor order, and asset loading without touching school data.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.urls import NoReverseMatch, reverse

from config.runtime_registry import build_context_processors
from .final_reengineering_audit import AuditIssue, project_root
from .information_architecture import GATEWAYS
from .workflow_catalog import OPERATIONS, SIDEBAR_SECTIONS


_STATIC_REF = re.compile(r"{%\s*static\s+['\"]([^'\"]+)['\"]\s*%}")


def _optional_enabled(code: str | None) -> bool:
    if code == "openemis":
        return bool(getattr(settings, "OPAL_ENABLE_OPENEMIS", False))
    if code == "development":
        return bool(getattr(settings, "OPAL_ENABLE_DEVELOPMENT_CENTER", False))
    return True


def audit_runtime_context_registry() -> list[AuditIssue]:
    """Validate the one canonical global context-processor registry."""
    issues: list[AuditIssue] = []
    processors = build_context_processors()
    if len(processors) != len(set(processors)):
        issues.append(AuditIssue("duplicate_context_processor", "يوجد Context Processor مكرر في سجل التشغيل المركزي."))

    required = (
        "core.context_processors.opal_identity",
        "core.context_processors.opal_operations",
        "enterprise_ops.context_processors.enterprise_notifications",
        "timetable.context_processors.live_schedule",
    )
    for processor in required:
        if processor not in processors:
            issues.append(AuditIssue("missing_context_processor", f"معالج السياق الأساسي غير موجود: {processor}"))

    if all(item in processors for item in (required[0], required[3])):
        if processors.index(required[0]) > processors.index(required[3]):
            issues.append(
                AuditIssue(
                    "runtime_context_order",
                    "يجب تحميل هوية OPAL قبل حالة الجدول الحي حتى يُعاد استخدام سياق المدرسة نفسه.",
                )
            )
    return issues


def audit_base_template_contract(root: Path | None = None) -> list[AuditIssue]:
    """Protect the global shell and prevent duplicate static payloads."""
    root = (root or project_root()).resolve()
    relative = Path("templates/base/base.html")
    path = root / relative
    if not path.is_file():
        return [AuditIssue("base_template_missing", "القالب الأساسي للنظام غير موجود.", str(relative))]

    text = path.read_text(encoding="utf-8")
    issues: list[AuditIssue] = []
    for include in ('{% include "includes/sidebar.html" %}', '{% include "includes/topbar.html" %}'):
        count = text.count(include)
        if count != 1:
            issues.append(
                AuditIssue(
                    "global_shell_include",
                    f"يجب تضمين {include} مرة واحدة فقط؛ الموجود {count}.",
                    str(relative),
                )
            )

    assets = _STATIC_REF.findall(text)
    duplicates = sorted({asset for asset in assets if assets.count(asset) > 1})
    for asset in duplicates:
        issues.append(AuditIssue("duplicate_static_asset", f"الملف الثابت محمّل أكثر من مرة: {asset}", str(relative)))

    required_assets = ("css/opal_theme_system.css", "js/opal_erp.js")
    for asset in required_assets:
        if assets.count(asset) != 1:
            issues.append(
                AuditIssue(
                    "required_static_asset",
                    f"يجب تحميل الملف {asset} مرة واحدة في القالب الأساسي.",
                    str(relative),
                )
            )

    css_assets = [asset for asset in assets if asset.endswith(".css")]
    legacy_shared = {
        "css/opal_erp.css", "css/opal_dashboard_polish.css", "css/opal_ui_consolidation.css",
        "css/opal_tables_consolidation.css", "css/opal_cards_consolidation.css", "css/opal_dashboard_executive.css",
        "css/opal_entity_360_consolidation.css", "css/opal_settings_consolidation.css",
        "css/opal_feedback_consolidation.css", "css/opal_responsive_audit.css", "css/opal_identity_cards.css",
    }
    leaked = sorted(set(css_assets) & legacy_shared)
    if leaked:
        issues.append(AuditIssue("legacy_shared_css_loaded", "يجب ألا يحمّل base.html طبقات CSS المشتركة القديمة بعد توحيد السلطة: " + ", ".join(leaked), str(relative)))
    if css_assets and css_assets[-1] != "css/opal_theme_system.css":
        issues.append(
            AuditIssue(
                "theme_asset_order",
                "يجب أن يكون نظام الثيم المركزي آخر ملف CSS حتى لا تستبدله ملفات قديمة.",
                str(relative),
            )
        )
    return issues


def audit_canonical_navigation_routes() -> list[AuditIssue]:
    """Ensure all enabled canonical operations and information gateways resolve."""
    issues: list[AuditIssue] = []
    operation_keys = {item["key"] for item in OPERATIONS}
    if len(operation_keys) != len(OPERATIONS):
        issues.append(AuditIssue("duplicate_operation_key", "توجد مفاتيح مكررة في دليل العمليات الموحد."))

    for operation in OPERATIONS:
        if not _optional_enabled(operation.get("optional")):
            continue
        try:
            reverse(operation["route"])
        except NoReverseMatch:
            issues.append(
                AuditIssue(
                    "unresolved_operation_route",
                    f"مسار العملية {operation['key']} غير قابل للحل: {operation['route']}",
                    "core/workflow_catalog.py",
                )
            )

    seen_sidebar_keys: set[tuple[str, str]] = set()
    for role, sections in SIDEBAR_SECTIONS.items():
        for section in sections:
            for key in section["items"]:
                if key not in operation_keys:
                    issues.append(
                        AuditIssue(
                            "unknown_sidebar_operation",
                            f"القائمة الجانبية للدور {role} تشير إلى عملية غير موجودة: {key}",
                            "core/workflow_catalog.py",
                        )
                    )
                signature = (role, key)
                if signature in seen_sidebar_keys:
                    issues.append(
                        AuditIssue(
                            "duplicate_sidebar_operation",
                            f"العملية {key} مكررة في القائمة الجانبية للدور {role}.",
                            "core/workflow_catalog.py",
                        )
                    )
                seen_sidebar_keys.add(signature)

    for gateway in GATEWAYS:
        try:
            reverse(gateway.route)
        except NoReverseMatch:
            issues.append(
                AuditIssue(
                    "unresolved_information_gateway",
                    f"بوابة المعلومات {gateway.key} غير قابلة للحل: {gateway.route}",
                    "core/information_architecture.py",
                )
            )
    return issues


def run_runtime_stability_audit(root: Path | None = None) -> dict:
    checks = {
        "runtime_context_registry": audit_runtime_context_registry(),
        "base_template_contract": audit_base_template_contract(root=root),
        "canonical_navigation_routes": audit_canonical_navigation_routes(),
    }
    issues = [issue for group in checks.values() for issue in group]
    return {
        "ok": not issues,
        "checks": {name: not group for name, group in checks.items()},
        "issue_count": len(issues),
        "issues": [issue.as_dict() for issue in issues],
    }
