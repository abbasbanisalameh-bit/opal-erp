#!/usr/bin/env python3
"""Read-only SQLite preflight for OPAL Update 131.

This script intentionally uses only Python's standard library so it can run
before Django migrations and on a safety copy.  It never writes to the DB.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path


def _tables(conn):
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _columns(conn, table):
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def _section_name(value, grade_name=""):
    text = _clean(value)
    grade = _clean(grade_name)
    if grade:
        pattern = re.compile(re.escape(grade), re.IGNORECASE)
        previous = None
        while previous != text:
            previous = text
            text = pattern.sub(" ", text).strip()
    text = re.sub(r"^[\s\-–—,:،/|]+|[\s\-–—,:،/|]+$", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^(?:ال)?شعب(?:ة|ه)\s*", "", text, flags=re.IGNORECASE).strip()
    if not text or text in {"الشعبة العامة", "شعبة عامة", "العامة"}:
        text = "عامة"
    return f"شعبة {text}"


def validate(path: Path):
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    tables = _tables(conn)
    required = {
        "academics_subject", "academics_grade", "academics_section", "core_academicyear",
        "curriculum_curriculum", "teachers_teacherassignment", "timetable_timetableentry",
        "exams_exam", "django_migrations",
    }
    missing = sorted(required - tables)
    issues = []
    warnings = []
    if missing:
        return {"ok": False, "database": str(path), "issues": [f"جداول مفقودة: {', '.join(missing)}"], "warnings": [], "metrics": {}}

    subjects = {row["id"]: row for row in conn.execute(
        "SELECT id,name,code,grade_id,is_active FROM academics_subject ORDER BY id"
    )}
    grades = {row["id"]: row for row in conn.execute(
        "SELECT id,name,school_id FROM academics_grade ORDER BY id"
    )}
    years = {row["id"]: row for row in conn.execute(
        "SELECT id,name,school_id,is_current FROM core_academicyear ORDER BY id"
    )}
    sections = {row["id"]: row for row in conn.execute(
        "SELECT id,name,grade_id,academic_year_id,branch_id FROM academics_section ORDER BY id"
    )}

    pair_sources = defaultdict(set)
    plan_values = defaultdict(set)
    for row in conn.execute(
        "SELECT id,academic_year_id,grade_id,subject_id,weekly_periods,is_required,is_active FROM curriculum_curriculum ORDER BY id"
    ):
        subject = subjects.get(row["subject_id"])
        if not subject:
            issues.append(f"Curriculum {row['id']} يشير إلى مادة مفقودة {row['subject_id']}")
            continue
        if row["grade_id"] != subject["grade_id"]:
            issues.append(f"Curriculum {row['id']} لا يطابق صف المادة {row['subject_id']}")
        pair = (row["subject_id"], row["academic_year_id"])
        pair_sources[pair].add("curriculum")
        plan_values[pair].add((row["weekly_periods"], row["is_required"], row["is_active"]))

    owner_specs = [
        ("teachers_teacherassignment", "تكليف", "academic_year_id", "section_id", True),
        ("timetable_timetableentry", "حصة", "academic_year_id", "section_id", False),
        ("exams_exam", "امتحان", "academic_year_id", "grade_id", False),
    ]
    assignment_periods = defaultdict(set)
    reference_counts = {}
    for table, label, year_col, grade_owner_col, carries_periods in owner_specs:
        count = 0
        columns = _columns(conn, table)
        selected = f"id,subject_id,{year_col},{grade_owner_col}"
        if carries_periods and "weekly_periods" in columns:
            selected += ",weekly_periods"
        for row in conn.execute(f"SELECT {selected} FROM {table} ORDER BY id"):
            count += 1
            subject = subjects.get(row["subject_id"])
            if not subject:
                issues.append(f"{label} {row['id']} يشير إلى مادة مفقودة {row['subject_id']}")
                continue
            owner_grade = sections[row[grade_owner_col]]["grade_id"] if grade_owner_col == "section_id" else row[grade_owner_col]
            if owner_grade != subject["grade_id"]:
                issues.append(f"{label} {row['id']} صفه لا يطابق صف المادة {row['subject_id']}")
            pair = (row["subject_id"], row[year_col])
            pair_sources[pair].add(label)
            if carries_periods and "weekly_periods" in row.keys():
                assignment_periods[pair].add(row["weekly_periods"])
        reference_counts[table] = count

    for table, label, year_sql in (
        ("exams_semestersubjectresult", "نتيجة فصلية", "s.academic_year_id"),
        ("exams_annualsubjectresult", "نتيجة سنوية", "r.academic_year_id"),
    ):
        if table not in tables:
            continue
        if table == "exams_semestersubjectresult":
            query = (
                "SELECT r.id,r.subject_id,s.academic_year_id AS year_id "
                "FROM exams_semestersubjectresult r JOIN core_semester s ON s.id=r.semester_id"
            )
        else:
            query = "SELECT r.id,r.subject_id,r.academic_year_id AS year_id FROM exams_annualsubjectresult r"
        count = 0
        for row in conn.execute(query):
            count += 1
            if row["subject_id"] not in subjects:
                issues.append(f"{label} {row['id']} يشير إلى مادة مفقودة")
            pair_sources[(row["subject_id"], row["year_id"])].add(label)
        reference_counts[table] = count

    resolved_plans = {}
    for pair in sorted(pair_sources):
        values = plan_values.get(pair, set())
        periods = {value for value in assignment_periods.get(pair, set()) if value is not None}
        if len(values) > 1:
            issues.append(f"قيم خطة متعارضة للمادة/العام {pair}: {sorted(values)}")
            continue
        if len(periods) > 1:
            issues.append(f"قيم حصص تكليف متعارضة للمادة/العام {pair}: {sorted(periods)}")
            continue
        if values:
            weekly, required, active = next(iter(values))
            if periods and next(iter(periods)) != weekly:
                issues.append(f"الخطة والتكليف مختلفان في عدد الحصص للمادة/العام {pair}")
                continue
        elif periods:
            weekly, required, active = next(iter(periods)), 1, 1
            warnings.append(f"المادة/العام {pair} بلا Curriculum؛ ستؤخذ قيمة التكليف المتطابقة")
        else:
            issues.append(f"المادة/العام المستخدم {pair} بلا خطة ولا قيمة تكليف صالحة")
            continue
        if not 1 <= int(weekly) <= 20:
            issues.append(f"عدد حصص خارج النطاق للمادة/العام {pair}: {weekly}")
            continue
        resolved_plans[pair] = (int(weekly), bool(required), bool(active))

    unused = [subject_id for subject_id in subjects if not any(pair[0] == subject_id for pair in pair_sources)]
    if unused:
        warnings.append(f"مواد كتالوج غير مستخدمة ستربط بأحدث عام في المدرسة: {len(unused)}")

    for pair in resolved_plans:
        subject = subjects[pair[0]]
        grade = grades.get(subject["grade_id"])
        year = years.get(pair[1])
        if not grade or not year:
            issues.append(f"المادة/العام {pair} مرتبط بصف أو عام مفقود")
        elif grade["school_id"] != year["school_id"]:
            issues.append(f"المادة/العام {pair} يعبر مدرستين مختلفتين")

    normalized = defaultdict(list)
    for section in sections.values():
        grade = grades.get(section["grade_id"])
        name = _section_name(section["name"], grade["name"] if grade else "")
        key = (section["academic_year_id"], section["branch_id"], section["grade_id"], name.casefold())
        normalized[key].append(section["id"])
    for ids in normalized.values():
        if len(ids) > 1:
            issues.append("تطبيع أسماء الشعب سينشئ تكرارًا: " + ",".join(map(str, ids)))

    metrics = {
        "database_size_bytes": path.stat().st_size,
        "subjects_before": len(subjects),
        "annual_subject_rows_expected": len(resolved_plans) + len(unused),
        "curriculum_rows_to_remove": conn.execute("SELECT COUNT(*) FROM curriculum_curriculum").fetchone()[0],
        "teacher_assignment_rows": reference_counts.get("teachers_teacherassignment", 0),
        "timetable_rows": reference_counts.get("timetable_timetableentry", 0),
        "exam_rows": reference_counts.get("exams_exam", 0),
        "semester_result_rows": reference_counts.get("exams_semestersubjectresult", 0),
        "annual_result_rows": reference_counts.get("exams_annualsubjectresult", 0),
        "section_rows": len(sections),
        "snapshot_rows": conn.execute("SELECT COUNT(*) FROM core_semesterstructuresnapshot").fetchone()[0] if "core_semesterstructuresnapshot" in tables else 0,
    }
    return {"ok": not issues, "database": str(path), "issues": issues, "warnings": warnings, "metrics": metrics}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("database", nargs="?", default="db.sqlite3")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = validate(Path(args.database).resolve())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("PASS" if report["ok"] else "FAIL", "OPAL Update 131 SQLite preflight")
        for key, value in report["metrics"].items():
            print(f"- {key}: {value}")
        for warning in report["warnings"]:
            print(f"WARNING: {warning}")
        for issue in report["issues"]:
            print(f"ERROR: {issue}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
