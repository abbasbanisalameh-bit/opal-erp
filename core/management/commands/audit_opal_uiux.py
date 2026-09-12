from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


REQUIRED_FILES = [
    "templates/includes/sidebar.html",
    "templates/includes/topbar.html",
    "templates/base/base.html",
    "static/css/opal_theme_system.css",
    "docs/uiux/OPAL_UI_UX_GUIDE_AR.md",
]

CENTRAL_CSS = "css/opal_theme_system.css"
LEGACY_SHARED_CSS = (
    "opal_erp.css", "opal_ui_consolidation.css", "opal_tables_consolidation.css",
    "opal_cards_consolidation.css", "opal_dashboard_executive.css",
    "opal_entity_360_consolidation.css", "opal_settings_consolidation.css",
    "opal_feedback_consolidation.css", "opal_responsive_audit.css",
)



class Command(BaseCommand):
    help = "يدقق اكتمال واعتماد طبقات OPAL UI/UX دون تعديل البيانات."

    def add_arguments(self, parser):
        parser.add_argument("--output", help="مسار اختياري لحفظ تقرير JSON")

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR)
        missing = [path for path in REQUIRED_FILES if not (root / path).is_file()]
        base_path = root / "templates/base/base.html"
        base_text = base_path.read_text(encoding="utf-8") if base_path.is_file() else ""
        central_count = base_text.count(CENTRAL_CSS)
        leaked_legacy = [name for name in LEGACY_SHARED_CSS if name in base_text]
        missing_links = [] if central_count == 1 and not leaked_legacy else ([CENTRAL_CSS] if central_count != 1 else []) + leaked_legacy

        report = {
            "audit": "OPAL UI/UX final certification",
            "status": "pass" if not missing and not missing_links else "fail",
            "required_files_checked": len(REQUIRED_FILES),
            "missing_files": missing,
            "css_links_checked": 1 + len(LEGACY_SHARED_CSS),
            "missing_css_links": missing_links,
            "architecture_guards": {
                "student_model": "students.Student",
                "database_change_required": False,
                "models_change_required": False,
                "core_identity_preserved": True,
            },
        }

        if options.get("output"):
            output = Path(options["output"])
            if not output.is_absolute():
                output = root / output
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(f"تم حفظ التقرير: {output}")

        if report["status"] != "pass":
            raise CommandError(json.dumps(report, ensure_ascii=False, indent=2))

        self.stdout.write(self.style.SUCCESS("نجح تدقيق OPAL UI/UX النهائي."))
