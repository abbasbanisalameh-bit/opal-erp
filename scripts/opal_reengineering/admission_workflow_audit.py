#!/usr/bin/env python3
"""Static audit for OPAL admission/registration workflow.

No database access and no source mutation. Produces a JSON map under
`docs/reengineering/admission_workflow_snapshot.json`.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "reengineering" / "admission_workflow_snapshot.json"

TARGETS = {
    "admissions": ["views.py", "services.py", "financial_services.py", "forms.py", "models.py", "urls.py"],
    "students": ["models.py", "student360.py", "urls.py"],
    "parent_portal": ["models.py", "services.py", "urls.py"],
    "accounting": ["models.py", "urls.py"],
    "documents": ["services/generation.py", "urls.py"],
    "academics": ["models.py", "urls.py"],
}


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def audit_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []
    decorators: dict[str, list[str]] = {}
    calls: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
            decorators[node.name] = [dotted_name(d.func if isinstance(d, ast.Call) else d) for d in node.decorator_list]
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.extend(f"{module}.{alias.name}".strip(".") for alias in node.names)
        elif isinstance(node, ast.Call):
            name = dotted_name(node.func)
            if name:
                calls.append(name)

    return {
        "path": str(path.relative_to(ROOT)),
        "sha256_source_length": len(text.encode("utf-8")),
        "functions": sorted(set(functions)),
        "classes": sorted(set(classes)),
        "imports": sorted(set(imports)),
        "decorators": decorators,
        "notable_calls": sorted({c for c in calls if any(k in c.lower() for k in ("student", "registration", "family", "receipt", "payment", "finance"))}),
    }


def main() -> int:
    missing: list[str] = []
    files: list[dict[str, Any]] = []
    for app, rels in TARGETS.items():
        for rel in rels:
            path = ROOT / app / rel
            if not path.exists():
                missing.append(str(path.relative_to(ROOT)))
                continue
            if path.suffix == ".py":
                files.append(audit_file(path))

    required_symbols = {
        "admissions/services.py": ["create_student_registration", "calculate_registration_totals"],
        "admissions/financial_services.py": ["student_finance_snapshot", "create_siblings_fee_payment"],
        "admissions/views.py": ["direct_registration", "registration_receipt"],
    }
    symbol_errors: list[str] = []
    by_path = {item["path"]: item for item in files}
    for rel, symbols in required_symbols.items():
        present = set(by_path.get(rel, {}).get("functions", []))
        for symbol in symbols:
            if symbol not in present:
                symbol_errors.append(f"{rel}: missing {symbol}")

    snapshot = {
        "title": "OPAL Admission Workflow Baseline",
        "scope": "admission-registration-student-family-finance-receipt",
        "files_checked": len(files),
        "missing_files": missing,
        "contract_errors": symbol_errors,
        "files": files,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Admission workflow files checked: {len(files)}")
    print(f"Missing files: {len(missing)}")
    print(f"Contract errors: {len(symbol_errors)}")
    print(f"Snapshot: {OUTPUT}")
    return 1 if missing or symbol_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
