import json
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.critical_workflow_contracts import (
    audit_critical_workflow_data,
    run_critical_workflow_contract_audit,
)


class Command(BaseCommand):
    help = "تدقيق مسارات ولي الأمر وإنهاء خدمة المعلم وطباعة الإيصالات دون تعديل البيانات."

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=["text", "json"], default="text")
        parser.add_argument("--output", help="مسار اختياري لحفظ تقرير JSON.")
        parser.add_argument(
            "--strict-warnings",
            action="store_true",
            help="اعتبار التحذيرات الناتجة عن بيانات قديمة مانعة للاعتماد.",
        )

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR)
        contracts = run_critical_workflow_contract_audit(root=root)
        data = audit_critical_workflow_data()
        errors = [*contracts["issues"], *data["errors"]]
        warnings = data["warnings"]
        ok = not errors and (not warnings or not options["strict_warnings"])
        report = {
            "audit": "OPAL ERP critical workflow acceptance gate",
            "version": (root / "OPAL_VERSION.txt").read_text(encoding="utf-8").strip(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ok": ok,
            "contracts": contracts,
            "data": data,
            "summary": {"errors": len(errors), "warnings": len(warnings)},
            "errors": errors,
            "warnings": warnings,
            "safety": {
                "read_only": True,
                "database_modified": False,
                "student_model": "students.Student",
            },
        }

        if options.get("output"):
            output = Path(options["output"])
            if not output.is_absolute():
                output = root / output
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        if options["format"] == "json":
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self.stdout.write(self.style.MIGRATE_HEADING("OPAL ERP — اعتماد المسارات التشغيلية الحرجة"))
            self.stdout.write(
                "العقود: ولي الأمر والشكاوى | إنهاء وإعادة تفعيل المعلم | الإيصالات بنسختين A4 أفقي"
            )
            for item in warnings:
                self.stdout.write(self.style.WARNING(f"تحذير [{item['code']}]: {item['message']}"))
            for item in errors:
                location = f" ({item['path']})" if item.get("path") else ""
                self.stdout.write(self.style.ERROR(f"خطأ [{item['code']}]: {item['message']}{location}"))
            self.stdout.write(
                f"الملخص: أخطاء {len(errors)} | تحذيرات {len(warnings)} | "
                f"الحالة {'ناجح' if ok else 'فاشل'}"
            )

        if errors:
            raise CommandError(f"فشل اعتماد المسارات الحرجة: {len(errors)} مشكلة.")
        if options["strict_warnings"] and warnings:
            raise CommandError(f"فشل الاعتماد الصارم: {len(warnings)} تحذيرًا.")
        if options["format"] == "text":
            self.stdout.write(self.style.SUCCESS("نجحت بوابة المسارات الحرجة دون تعديل البيانات."))
