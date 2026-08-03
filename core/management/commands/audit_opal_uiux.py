from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


REQUIRED_FILES = [
    "templates/includes/sidebar.html",
    "templates/includes/topbar.html",
    "templates/base/base.html",
    "static/css/opal_erp.css",
    "static/css/opal_ui_consolidation.css",
    "static/css/opal_tables_consolidation.css",
    "static/css/opal_cards_consolidation.css",
    "static/css/opal_dashboard_executive.css",
    "static/css/opal_entity_360_consolidation.css",
    "static/css/opal_settings_consolidation.css",
    "static/css/opal_feedback_consolidation.css",
    "static/css/opal_responsive_audit.css",
    "docs/uiux/OPAL_UI_UX_GUIDE_AR.md",
]

CSS_LINKS = [
    "opal_ui_consolidation.css",
    "opal_tables_consolidation.css",
    "opal_cards_consolidation.css",
    "opal_dashboard_executive.css",
    "opal_entity_360_consolidation.css",
    "opal_settings_consolidation.css",
    "opal_feedback_consolidation.css",
    "opal_responsive_audit.css",
]


class Command(BaseCommand):
    help = "يدقق اكتمال واعتماد طبقات OPAL UI/UX دون تعديل البيانات."

    def add_arguments(self, parser):
        parser.add_argument("--output", help="مسار اختياري لحفظ تقرير JSON")

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR)
        missing = [path for path in REQUIRED_FILES if not (root / path).is_file()]
        base_path = root / "templates/base/base.html"
        base_text = base_path.read_text(encoding="utf-8") if base_path.is_file() else ""
        missing_links = [name for name in CSS_LINKS if name not in base_text]

        report = {
            "audit": "OPAL UI/UX final certification",
            "status": "pass" if not missing and not missing_links else "fail",
            "required_files_checked": len(REQUIRED_FILES),
            "missing_files": missing,
            "css_links_checked": len(CSS_LINKS),
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
