from __future__ import annotations

import json
from pathlib import Path

from django.core.management import BaseCommand, call_command

from core.final_reengineering_audit import run_final_reengineering_audit


class Command(BaseCommand):
    help = "تشغيل التدقيق الختامي الآمن لإعادة هندسة OPAL ERP دون تعديل البيانات."

    def add_arguments(self, parser):
        parser.add_argument("--output", help="مسار اختياري لحفظ تقرير JSON.")
        parser.add_argument("--skip-templates", action="store_true")
        parser.add_argument("--skip-django-check", action="store_true")

    def handle(self, *args, **options):
        if not options["skip_django_check"]:
            call_command("check", verbosity=0)

        report = run_final_reengineering_audit(
            include_templates=not options["skip_templates"]
        )
        rendered = json.dumps(report, ensure_ascii=False, indent=2)

        if options.get("output"):
            output = Path(options["output"]).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered + "\n", encoding="utf-8")
            self.stdout.write(f"تم حفظ التقرير: {output}")

        if report["ok"]:
            self.stdout.write(self.style.SUCCESS("نجح التدقيق الختامي لإعادة هندسة OPAL ERP."))
            return

        self.stderr.write(rendered)
        raise SystemExit(1)
