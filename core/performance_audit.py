"""Read-only runtime performance measurement helpers for OPAL ERP.

The module deliberately avoids writing to school data.  It normalizes SQL before
reporting so values from live records are not stored in audit files.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Iterable, Mapping, Sequence


_STRING_LITERAL_RE = re.compile(r"'(?:''|[^'])*'")
_HEX_LITERAL_RE = re.compile(r"\bX'(?:[0-9A-Fa-f]{2})+'\b")
_NUMBER_LITERAL_RE = re.compile(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?(?![A-Za-z_])")
_WHITESPACE_RE = re.compile(r"\s+")


DEFAULT_PERFORMANCE_ROUTES: tuple[dict[str, object], ...] = (
    {
        "key": "executive_dashboard",
        "route": "dashboard:home",
        "label": "لوحة الإدارة التنفيذية",
        "query_budget": 35,
        "response_budget_ms": 2500,
    },
    {
        "key": "finance_dashboard",
        "route": "accounting:dashboard",
        "label": "لوحة الرسوم والدفعات",
        "query_budget": 70,
        "response_budget_ms": 3000,
    },
    {
        "key": "invoice_list",
        "route": "accounting:invoice_list",
        "label": "قائمة الرسوم والفواتير",
        "query_budget": 75,
        "response_budget_ms": 3000,
    },
    {
        "key": "attendance_dashboard",
        "route": "attendance_v2:dashboard",
        "label": "لوحة الحضور",
        "query_budget": 60,
        "response_budget_ms": 2500,
    },
    {
        "key": "attendance_report",
        "route": "attendance_v2:report",
        "label": "تقرير الحضور",
        "query_budget": 50,
        "response_budget_ms": 3500,
    },
    {
        "key": "student_list",
        "route": "students:student_list",
        "label": "قائمة الطلبة",
        "query_budget": 60,
        "response_budget_ms": 2500,
    },
    {
        "key": "teacher_list",
        "route": "teachers:teacher_list",
        "label": "قائمة المعلمين",
        "query_budget": 30,
        "response_budget_ms": 2500,
    },
    {
        "key": "academic_dashboard",
        "route": "academics:dashboard",
        "label": "الشؤون الأكاديمية",
        "query_budget": 70,
        "response_budget_ms": 3000,
    },
    {
        "key": "timetable_dashboard",
        "route": "timetable:dashboard",
        "label": "الجدول المدرسي",
        "query_budget": 40,
        "response_budget_ms": 3000,
    },
    {
        "key": "report_center",
        "route": "enterprise_ops:report_center",
        "label": "مركز التقارير",
        "query_budget": 70,
        "response_budget_ms": 3000,
    },
)


def normalize_sql(sql: str) -> str:
    """Return a value-free SQL fingerprint suitable for duplicate detection."""
    normalized = str(sql or "")
    normalized = _HEX_LITERAL_RE.sub("?", normalized)
    normalized = _STRING_LITERAL_RE.sub("?", normalized)
    normalized = _NUMBER_LITERAL_RE.sub("?", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized


def _query_time_ms(query: Mapping[str, object]) -> float:
    try:
        return float(query.get("time") or 0) * 1000
    except (TypeError, ValueError):
        return 0.0


def summarize_queries(
    queries: Iterable[Mapping[str, object]],
    *,
    duplicate_limit: int = 10,
    slow_limit: int = 10,
) -> dict[str, object]:
    """Summarize captured Django queries without retaining live values."""
    rows = list(queries)
    fingerprints = [normalize_sql(str(row.get("sql") or "")) for row in rows]
    counts = Counter(fingerprint for fingerprint in fingerprints if fingerprint)
    duplicate_groups = [
        {"count": count, "sql": sql}
        for sql, count in counts.most_common()
        if count > 1
    ][:duplicate_limit]
    slow_queries = sorted(
        (
            {
                "time_ms": round(_query_time_ms(row), 3),
                "sql": normalize_sql(str(row.get("sql") or "")),
            }
            for row in rows
        ),
        key=lambda item: item["time_ms"],
        reverse=True,
    )[:slow_limit]
    duplicate_query_count = sum(max(count - 1, 0) for count in counts.values() if count > 1)
    return {
        "query_count": len(rows),
        "db_time_ms": round(sum(_query_time_ms(row) for row in rows), 3),
        "duplicate_query_count": duplicate_query_count,
        "duplicate_groups": duplicate_groups,
        "slow_queries": slow_queries,
        "n_plus_one_suspected": any(group["count"] >= 4 for group in duplicate_groups),
    }


def median_number(values: Sequence[float | int]) -> float:
    return round(float(median(values)), 3) if values else 0.0


def compare_reports(current: Mapping[str, object], baseline: Mapping[str, object]) -> list[dict[str, object]]:
    """Return route-level before/after deltas for two performance reports."""
    baseline_rows = {
        str(row.get("key")): row
        for row in baseline.get("results", [])
        if isinstance(row, Mapping) and row.get("key")
    }
    comparisons: list[dict[str, object]] = []
    for current_row in current.get("results", []):
        if not isinstance(current_row, Mapping):
            continue
        previous = baseline_rows.get(str(current_row.get("key")))
        if not previous:
            continue
        current_ms = float(current_row.get("median_response_ms") or 0)
        previous_ms = float(previous.get("median_response_ms") or 0)
        current_queries = float(current_row.get("median_query_count") or 0)
        previous_queries = float(previous.get("median_query_count") or 0)
        comparisons.append({
            "key": current_row.get("key"),
            "label": current_row.get("label"),
            "response_ms_before": previous_ms,
            "response_ms_after": current_ms,
            "response_ms_delta": round(current_ms - previous_ms, 3),
            "response_percent_change": round(((current_ms - previous_ms) / previous_ms) * 100, 1) if previous_ms else None,
            "queries_before": previous_queries,
            "queries_after": current_queries,
            "queries_delta": round(current_queries - previous_queries, 3),
            "queries_percent_change": round(((current_queries - previous_queries) / previous_queries) * 100, 1) if previous_queries else None,
        })
    return comparisons


def release_version(root: Path) -> str:
    try:
        return (root / "OPAL_VERSION.txt").read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown"
