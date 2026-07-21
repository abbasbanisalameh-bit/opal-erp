#!/usr/bin/env python3
"""Audit module-level imports between local Django apps without importing project code."""
from __future__ import annotations

import ast
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {"migrations", "__pycache__"}
EXCLUDED_FILES = {"tests.py"}


def discover_apps() -> set[str]:
    apps: set[str] = set()
    for apps_file in ROOT.glob("*/apps.py"):
        if apps_file.parent.name.startswith("."):
            continue
        apps.add(apps_file.parent.name)
    return apps


def iter_python_files(app: str):
    base = ROOT / app
    for path in base.rglob("*.py"):
        rel = path.relative_to(base)
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        if path.name in EXCLUDED_FILES or path.name.startswith("test_") or path.name.startswith("tests_"):
            continue
        yield path


def module_level_imports(path: Path, local_apps: set[str]) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in local_apps:
                    found.add(root)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            root = node.module.split(".", 1)[0]
            if root in local_apps:
                found.add(root)
    return found


def strongly_connected_components(graph: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for nxt in sorted(graph.get(node, set())):
            if nxt not in indices:
                visit(nxt)
                lowlinks[node] = min(lowlinks[node], lowlinks[nxt])
            elif nxt in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[nxt])

        if lowlinks[node] == indices[node]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1:
                components.append(sorted(component))

    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return sorted(components, key=lambda item: (len(item), item))


def main() -> int:
    apps = discover_apps()
    graph: dict[str, set[str]] = defaultdict(set)
    files_scanned = 0
    syntax_errors: list[str] = []
    for app in sorted(apps):
        graph.setdefault(app, set())
        for path in iter_python_files(app):
            files_scanned += 1
            try:
                graph[app].update(module_level_imports(path, apps) - {app})
            except SyntaxError as exc:
                syntax_errors.append(f"{path.relative_to(ROOT)}:{exc.lineno}: {exc.msg}")
    found_cycles = strongly_connected_components(graph)
    report = {
        "apps": len(apps),
        "python_files_scanned": files_scanned,
        "dependency_edges": sum(len(v) for v in graph.values()),
        "circular_dependency_groups": found_cycles,
        "syntax_errors": syntax_errors,
        "graph": {k: sorted(v) for k, v in sorted(graph.items())},
    }
    output = ROOT / "dependency_audit_report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Apps checked: {report['apps']}")
    print(f"Python files checked: {files_scanned}")
    print(f"Dependency edges: {report['dependency_edges']}")
    print(f"Circular dependency groups: {len(found_cycles)}")
    print(f"Syntax errors: {len(syntax_errors)}")
    print(f"Report: {output}")
    return 1 if syntax_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
