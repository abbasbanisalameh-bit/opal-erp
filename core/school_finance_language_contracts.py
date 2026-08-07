"""Contracts for OPAL's plain school-fee terminology and dashboard navigation.

The school ERP deliberately avoids general-accounting language in user-facing
screens.  Internal field names remain stable for data compatibility, while the
UI uses: total fees, discounts, paid, and remaining.
"""

from __future__ import annotations

from pathlib import Path

from .final_reengineering_audit import AuditIssue, project_root


_FORBIDDEN_VISIBLE_TERMS = ("مدين", "دائن", "الذمم", "ذمة")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def audit_plain_school_finance_language(root: Path | None = None) -> list[AuditIssue]:
    root = (root or project_root()).resolve()
    issues: list[AuditIssue] = []

    visible_files = [
        *sorted((root / "templates").rglob("*.html")),
        root / "dashboard" / "templates" / "dashboard" / "home.html",
        root / "parent_portal" / "forms.py",
        root / "parent_portal" / "models.py",
        root / "parent_portal" / "financial_services.py",
    ]
    seen: set[Path] = set()
    for path in visible_files:
        if path in seen or not path.is_file() or "migrations" in path.parts:
            continue
        seen.add(path)
        source = _read(path)
        for term in _FORBIDDEN_VISIBLE_TERMS:
            if term in source:
                issues.append(
                    AuditIssue(
                        "general_accounting_term_visible",
                        f"المصطلح المحاسبي العام «{term}» ما يزال ظاهرًا للمستخدم.",
                        path.relative_to(root).as_posix(),
                    )
                )

    fees_template = _read(root / "templates" / "parent_portal" / "fees.html")
    for label in ("إجمالي الرسوم", "الخصومات", "المدفوع", "المتبقي"):
        if label not in fees_template:
            issues.append(
                AuditIssue(
                    "parent_fee_summary_label_missing",
                    f"كشف ولي الأمر يفتقد المصطلح المدرسي المعتمد: {label}.",
                    "templates/parent_portal/fees.html",
                )
            )
    for forbidden_binding in ("tx.debit", "tx.credit"):
        if forbidden_binding in fees_template:
            issues.append(
                AuditIssue(
                    "parent_fee_dual_column_returned",
                    "كشف ولي الأمر أعاد عمودي المدين والدائن بدل عمود المبلغ الواحد.",
                    "templates/parent_portal/fees.html",
                )
            )
    if "tx.amount" not in fees_template or "نوع الحركة" not in fees_template:
        issues.append(
            AuditIssue(
                "parent_fee_plain_movement_missing",
                "كشف ولي الأمر يجب أن يعرض نوع الحركة ومبلغًا واحدًا واضحًا.",
                "templates/parent_portal/fees.html",
            )
        )

    dashboard = _read(root / "templates" / "accounting" / "dashboard.html")
    if "إجمالي المتبقي" not in dashboard:
        issues.append(
            AuditIssue(
                "finance_remaining_label_missing",
                "بوابة الرسوم لا تستخدم مصطلح «إجمالي المتبقي» المعتمد.",
                "templates/accounting/dashboard.html",
            )
        )
    return issues


def run_school_finance_language_audit(root: Path | None = None) -> dict:
    issues = audit_plain_school_finance_language(root=root)
    return {
        "ok": not issues,
        "checks": {"plain_school_finance_language": not issues},
        "issue_count": len(issues),
        "issues": [issue.as_dict() for issue in issues],
    }
