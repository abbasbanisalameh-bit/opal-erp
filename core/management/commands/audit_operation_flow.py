"""Read-only command for the OPAL canonical operation integration audit."""

import json

from django.core.management.base import BaseCommand, CommandError

from core.operation_audit import build_operation_audit


class Command(BaseCommand):
    help = "يفحص ترابط العمليات الأساسية دون تعديل البيانات."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json", help="إخراج النتيجة بصيغة JSON")
        parser.add_argument(
            "--allow-issues",
            action="store_true",
            help="إرجاع نجاح حتى عند وجود حالات تحتاج مراجعة؛ مناسب للفحص الاستطلاعي.",
        )

    def handle(self, *args, **options):
        result = build_operation_audit()
        payload = {
            "health_percent": result["integration_health_percent"],
            "health_label": result["integration_health_label"],
            "passed_checks": result["integration_passed_checks"],
            "total_checks": result["integration_total_checks"],
            "open_records": result["integration_open_issues"],
            "counts": result["integration_counts"],
            "checks": [
                {
                    "code": item["code"],
                    "label": item["label"],
                    "count": item["count"],
                    "severity": item["severity"],
                    "route": item["route"],
                }
                for item in result["integration_issues"]
            ],
        }

        if options["as_json"]:
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            self.stdout.write(self.style.MIGRATE_HEADING("OPAL ERP - فحص تكامل سير العمليات"))
            self.stdout.write(
                f"الصحة: {payload['health_percent']}% ({payload['health_label']}) | "
                f"الفحوص السليمة: {payload['passed_checks']}/{payload['total_checks']}"
            )
            for item in payload["checks"]:
                status = "سليم" if item["count"] == 0 else f"يحتاج مراجعة: {item['count']}"
                style = self.style.SUCCESS if item["count"] == 0 else self.style.WARNING
                self.stdout.write(style(f"[{item['code']}] {item['label']}: {status}"))

        if payload["open_records"] and not options["allow_issues"]:
            raise CommandError(
                "فشل فحص تكامل العمليات: توجد حالات تحتاج مراجعة. "
                "استخدم --allow-issues للفحص الاستطلاعي فقط."
            )
