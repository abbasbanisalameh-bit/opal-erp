from pathlib import Path
from collections import defaultdict
import re, json
ROOT=Path(__file__).resolve().parents[1]
CSS=ROOT/'static'/'css'
report={'css_files':[],'selector_occurrences':{},'exact_duplicate_blocks':[],'notes':[]}
blocks=defaultdict(list)
for p in sorted(CSS.glob('*.css')):
    txt=p.read_text(encoding='utf-8',errors='ignore')
    report['css_files'].append({'file':str(p.relative_to(ROOT)),'bytes':len(txt)})
    for m in re.finditer(r'([^{}@][^{}]*)\{([^{}]*)\}',txt,re.S):
        sel=' '.join(m.group(1).split())
        body=' '.join(m.group(2).split())
        if not sel: continue
        blocks[sel].append({'file':str(p.relative_to(ROOT)),'body':body})
for sel,items in blocks.items():
    if len(items)>1:
        report['selector_occurrences'][sel]=items
        bybody=defaultdict(list)
        for it in items: bybody[it['body']].append(it['file'])
        for body,files in bybody.items():
            if len(files)>1:
                report['exact_duplicate_blocks'].append({'selector':sel,'files':files})
report['notes']=[
 'R89 is conservative: it records repeated selectors and exact duplicate blocks without deleting cascade-sensitive rules.',
 'The shared authority remains static/css/opal_theme_system.css.',
 'Module-specific CSS is treated as an exception until usage is proven.'
]
out=ROOT/'OPAL_CSS_AUTHORITY_AUDIT_R89.json'
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(out)
print('CSS files:',len(report['css_files']))
print('Repeated selectors:',len(report['selector_occurrences']))
print('Exact duplicate blocks:',len(report['exact_duplicate_blocks']))
