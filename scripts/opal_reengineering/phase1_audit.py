#!/usr/bin/env python3
"""OPAL ERP conservative reengineering baseline audit.
Read-only: does not modify project files or database.
"""
from __future__ import annotations
import ast, hashlib, json, os, re, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED = {'.git', '.venv', 'venv', '__pycache__', 'staticfiles', 'media', 'node_modules'}


def files(pattern: str):
    return sorted(p for p in ROOT.rglob(pattern) if not any(x in EXCLUDED for x in p.parts))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str]) -> dict:
    try:
        p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=180)
        return {'command': cmd, 'returncode': p.returncode, 'stdout': p.stdout[-12000:], 'stderr': p.stderr[-12000:]}
    except Exception as exc:
        return {'command': cmd, 'returncode': None, 'error': repr(exc)}


def parse_python():
    models, urls, imports = [], [], []
    for path in files('*.py'):
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
        except SyntaxError as exc:
            imports.append({'file': rel, 'syntax_error': str(exc)})
            continue
        if path.name == 'models.py':
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    bases = [ast.unparse(b) for b in node.bases]
                    if any('Model' in b for b in bases):
                        fields = []
                        for item in node.body:
                            if isinstance(item, (ast.Assign, ast.AnnAssign)):
                                value = getattr(item, 'value', None)
                                if isinstance(value, ast.Call):
                                    fn = ast.unparse(value.func)
                                    if 'models.' in fn:
                                        target = ast.unparse(item.targets[0]) if isinstance(item, ast.Assign) else ast.unparse(item.target)
                                        fields.append({'name': target, 'type': fn})
                        models.append({'file': rel, 'class': node.name, 'bases': bases, 'fields': fields})
        if path.name == 'urls.py':
            source = path.read_text(encoding='utf-8', errors='replace')
            app_name = re.search(r"app_name\s*=\s*['\"]([^'\"]+)", source)
            names = re.findall(r"\bname\s*=\s*['\"]([^'\"]+)", source)
            urls.append({'file': rel, 'app_name': app_name.group(1) if app_name else None, 'names': names})
    return models, urls, imports


def parse_templates():
    result = []
    url_tag = re.compile(r"{%-?\s*url\s+['\"]([^'\"]+)")
    extends_tag = re.compile(r"{%-?\s*extends\s+['\"]([^'\"]+)")
    include_tag = re.compile(r"{%-?\s*include\s+['\"]([^'\"]+)")
    for path in files('*.html'):
        text = path.read_text(encoding='utf-8', errors='replace')
        result.append({
            'file': path.relative_to(ROOT).as_posix(),
            'urls': sorted(set(url_tag.findall(text))),
            'extends': sorted(set(extends_tag.findall(text))),
            'includes': sorted(set(include_tag.findall(text))),
        })
    return result


def main():
    out_dir = ROOT / 'docs' / 'reengineering'
    out_dir.mkdir(parents=True, exist_ok=True)
    models, urls, parse_errors = parse_python()
    templates = parse_templates()
    py_files = files('*.py')
    html_files = files('*.html')
    top_apps = sorted(p.name for p in ROOT.iterdir() if p.is_dir() and (p / 'apps.py').exists())
    duplicate_url_names = []
    for item in urls:
        seen = set()
        dup = sorted({n for n in item['names'] if n in seen or seen.add(n)})
        if dup:
            duplicate_url_names.append({'file': item['file'], 'names': dup})
    student_models = [m for m in models if m['class'].lower() == 'student']
    snapshot = {
        'schema_version': 1,
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'project_root': str(ROOT),
        'counts': {'django_apps': len(top_apps), 'python_files': len(py_files), 'html_templates': len(html_files), 'models': len(models), 'url_modules': len(urls)},
        'apps': top_apps,
        'student_model_candidates': student_models,
        'duplicate_url_names_within_module': duplicate_url_names,
        'models': models,
        'urls': urls,
        'templates': templates,
        'parse_errors': parse_errors,
        'checks': {
            'django_check': run([sys.executable, 'manage.py', 'check']),
            'migration_drift': run([sys.executable, 'manage.py', 'makemigrations', '--check', '--dry-run']),
        },
        'critical_file_hashes': {str(p.relative_to(ROOT)): sha256(p) for p in [ROOT/'config/settings.py', ROOT/'config/urls.py', ROOT/'templates/includes/sidebar.html', ROOT/'templates/includes/topbar.html', ROOT/'static/css/opal_erp.css'] if p.exists()},
    }
    json_path = out_dir / 'phase1_baseline_snapshot.json'
    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    md = [
        '# OPAL ERP — Phase 1 Baseline', '',
        f"Generated: {snapshot['generated_at_utc']}", '',
        f"- Django apps: {len(top_apps)}",
        f"- Python files: {len(py_files)}",
        f"- HTML templates: {len(html_files)}",
        f"- Model classes: {len(models)}",
        f"- URL modules: {len(urls)}",
        f"- Student model candidates: {', '.join(m['file'] + ':' + m['class'] for m in student_models) or 'None'}",
        f"- Django check return code: {snapshot['checks']['django_check']['returncode']}",
        f"- Migration drift return code: {snapshot['checks']['migration_drift']['returncode']}", '',
        'This report is read-only and is used as the immutable comparison baseline for later updates.',
    ]
    (out_dir / 'phase1_baseline_summary.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(json_path)
    return 0 if snapshot['checks']['django_check']['returncode'] == 0 and snapshot['checks']['migration_drift']['returncode'] == 0 else 2

if __name__ == '__main__':
    raise SystemExit(main())
