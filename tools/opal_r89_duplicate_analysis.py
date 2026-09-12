from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "OPAL_CSS_AUTHORITY_AUDIT_R89.json"
OUT_JSON = ROOT / "OPAL_CSS_DUPLICATE_ANALYSIS_R89.json"
OUT_MD = ROOT / "OPAL_CSS_DUPLICATE_ANALYSIS_R89.md"

data = json.loads(AUDIT.read_text(encoding="utf-8"))

items = data.get("exact_duplicate_blocks", [])

protected = []
review = []
single_file = []

for item in items:
    files = item.get("files", [])
    selector = item.get("selector", "")

    record = {
        "selector": selector,
        "files": files,
        "file_count": len(files),
    }

    if "static/css/opal_theme_system.css" in files:
        record["classification"] = "PROTECTED_SHARED_AUTHORITY"
        record["reason"] = (
            "Shared theme authority is protected; no automatic consolidation."
        )
        protected.append(record)
    elif len(files) > 1:
        record["classification"] = "REVIEW_CROSS_FILE"
        record["reason"] = (
            "Exact duplicate appears across multiple CSS files and requires "
            "cascade/usage review before any change."
        )
        review.append(record)
    else:
        record["classification"] = "SINGLE_FILE_REVIEW"
        record["reason"] = (
            "Duplicate reported within one file; requires structural review."
        )
        single_file.append(record)

report = {
    "release": "OPAL Update 131.7 R89",
    "source_audit": AUDIT.name,
    "css_files": len(data.get("css_files", [])),
    "repeated_selectors": len(data.get("selector_occurrences", {})),
    "exact_duplicate_blocks": len(items),
    "classification_summary": {
        "protected_shared_authority": len(protected),
        "review_cross_file": len(review),
        "single_file_review": len(single_file),
    },
    "protected_shared_authority": protected,
    "review_cross_file": review,
    "single_file_review": single_file,
    "safety_rule": (
        "REPORT ONLY. No CSS files were modified or deleted."
    ),
}

OUT_JSON.write_text(
    json.dumps(report, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

lines = [
    "# OPAL R89 Duplicate Analysis",
    "",
    "## Safety",
    "REPORT ONLY — No CSS files were modified or deleted.",
    "",
    "## Summary",
    f"- CSS files: {report['css_files']}",
    f"- Repeated selectors: {report['repeated_selectors']}",
    f"- Exact duplicate blocks: {report['exact_duplicate_blocks']}",
    f"- Protected shared authority: {len(protected)}",
    f"- Cross-file review: {len(review)}",
    f"- Single-file review: {len(single_file)}",
    "",
    "## Classification Rules",
    "- PROTECTED_SHARED_AUTHORITY: includes static/css/opal_theme_system.css",
    "- REVIEW_CROSS_FILE: appears across multiple files",
    "- SINGLE_FILE_REVIEW: requires structural review inside one file",
]

OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("=== R89 DUPLICATE ANALYSIS ===")
print(f"CSS files: {report['css_files']}")
print(f"Repeated selectors: {report['repeated_selectors']}")
print(f"Exact duplicate blocks: {report['exact_duplicate_blocks']}")
print()
print("=== CLASSIFICATION ===")
print(f"PROTECTED_SHARED_AUTHORITY: {len(protected)}")
print(f"REVIEW_CROSS_FILE: {len(review)}")
print(f"SINGLE_FILE_REVIEW: {len(single_file)}")
print()
print("SAFETY: REPORT ONLY — no CSS files changed.")
print(f"Created: {OUT_JSON.name}")
print(f"Created: {OUT_MD.name}")
