import json
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.final_reengineering_audit import run_final_reengineering_audit
from core.runtime_contracts import run_runtime_stability_audit
from core.critical_workflow_contracts import run_critical_workflow_contract_audit
from core.single_entry_contracts import run_single_entry_contract_audit
from core.school_finance_language_contracts import run_school_finance_language_audit
from core.smart_timetable_contracts import run_smart_timetable_contract_audit


class Command(BaseCommand):
    help = "تشغيل تدقيق OPAL النهائي للمعمارية وقشرة التشغيل دون تعديل البيانات."

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=["text", "json"], default="text")
        parser.add_argument("--output", help="مسار اختياري لحفظ تقرير JSON.")
        parser.add_argument("--skip-templates", action="store_true", help="تجاوز تجميع جميع القوالب في الفحص السريع.")

    def handle(self, *args, **options):
        architecture = run_final_reengineering_audit(include_templates=not options["skip_templates"])
        runtime = run_runtime_stability_audit()
        critical_workflows = run_critical_workflow_contract_audit()
        single_entry = run_single_entry_contract_audit()
        finance_language = run_school_finance_language_audit()
        smart_timetable = run_smart_timetable_contract_audit()
        issues = [
            *architecture["issues"],
            *runtime["issues"],
            *critical_workflows["issues"],
            *single_entry["issues"],
            *finance_language["issues"],
            *smart_timetable["issues"],
        ]
        report = {
            "audit": "OPAL ERP final stability gate",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "version": (Path(settings.BASE_DIR) / "OPAL_VERSION.txt").read_text(encoding="utf-8").strip(),
            "ok": not issues,
            "architecture": architecture,
            "runtime": runtime,
            "critical_workflows": critical_workflows,
            "single_entry": single_entry,
            "school_finance_language": finance_language,
            "smart_timetable": smart_timetable,
            "issue_count": len(issues),
            "issues": issues,
            "safety": {"read_only": True, "database_modified": False, "student_model": "students.Student"},
        }

        if options.get("output"):
            output = Path(options["output"])
            if not output.is_absolute():
                output = Path(settings.BASE_DIR) / output
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        if options["format"] == "json":
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self.stdout.write(self.style.MIGRATE_HEADING("OPAL ERP — بوابة الاستقرار النهائية"))
            for issue in issues:
                location = f" ({issue['path']})" if issue.get("path") else ""
                self.stdout.write(self.style.ERROR(f"[{issue['code']}] {issue['message']}{location}"))
            self.stdout.write(f"الملخص: {len(issues)} مشكلة | الحالة {'ناجح' if report['ok'] else 'فاشل'}")

        if issues:
            raise CommandError(f"فشل تدقيق الاستقرار: {len(issues)} مشكلة.")
        if options["format"] == "text":
            self.stdout.write(self.style.SUCCESS("نجحت بوابة الاستقرار النهائية دون تعديل البيانات."))
