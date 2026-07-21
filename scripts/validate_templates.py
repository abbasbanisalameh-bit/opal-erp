#!/usr/bin/env python3
from __future__ import annotations
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()
from django.template import engines

EXCLUDED_DIRS = {'.git', '.opal_updates', 'venv', '.venv', 'staticfiles', '__pycache__'}
html_files = sorted(p for p in ROOT.rglob('*.html') if not any(part in EXCLUDED_DIRS for part in p.relative_to(ROOT).parts))
errors = []
engine = engines['django']
for path in html_files:
    try:
        rel = path.relative_to(ROOT)
        # Templates under the global templates directory can be loaded by name.
        if rel.parts and rel.parts[0] == 'templates':
            engine.get_template(str(Path(*rel.parts[1:])).replace('\\', '/'))
        else:
            # App templates are compiled directly to verify syntax.
            engine.from_string(path.read_text(encoding='utf-8', errors='strict'))
    except Exception as exc:
        errors.append((str(path.relative_to(ROOT)), f'{type(exc).__name__}: {exc}'))

print(f'Templates checked: {len(html_files)}')
if errors:
    for path, error in errors:
        print(f'ERROR {path}: {error}')
    raise SystemExit(1)
print('Template validation: OK')
