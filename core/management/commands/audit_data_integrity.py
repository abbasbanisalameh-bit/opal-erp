import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core.data_integrity import run_integrity_audit


class Command(BaseCommand):
    help = "فحص تعارضات وتكرارات OPAL، مع خيار إصلاح الحالات المؤكدة فقط."

    def add_arguments(self, parser):
        parser.add_argument("--fix-safe", action="store_true", help="تنفيذ الإصلاحات المؤكدة فقط.")
        parser.add_argument("--user", default="", help="اسم المستخدم الإداري المنفذ.")
        parser.add_argument("--format", choices=["text", "json"], default="text")
        parser.add_argument("--fail-on-critical", action="store_true")

    def handle(self, *args, **options):
        user = None
        if options["user"]:
            user = get_user_model().objects.filter(username=options["user"]).first()
            if user is None:
                raise CommandError("اسم المستخدم غير موجود.")
        run = run_integrity_audit(fix_safe=options["fix_safe"], user=user)
        rows = list(run.issues.values("code", "severity", "model_name", "object_id", "description", "is_fixable", "is_fixed", "resolution"))
        if options["format"] == "json":
            self.stdout.write(json.dumps({
                "run_id": run.pk, "mode": run.mode, "total": run.total_issues,
                "critical": run.critical_count, "warnings": run.warning_count,
                "fixed": run.fixed_count, "issues": rows,
            }, ensure_ascii=False, indent=2))
        else:
            self.stdout.write(self.style.MIGRATE_HEADING(f"OPAL Data Integrity — Run #{run.pk}"))
            for row in rows:
                state = "تم الإصلاح" if row["is_fixed"] else ("قابل للإصلاح" if row["is_fixable"] else "مراجعة يدوية")
                self.stdout.write(f"[{row['severity']}] {row['code']} — {row['description']} ({state})")
            self.stdout.write(self.style.SUCCESS(
                f"النتيجة: {run.total_issues} مشكلة، {run.fixed_count} أُصلحت، "
                f"{run.critical_count} حرجة متبقية، {run.warning_count} تحذير متبقٍ."
            ))
        if options["fail_on_critical"] and run.critical_count:
            raise CommandError(f"بقيت {run.critical_count} مشكلة حرجة تحتاج مراجعة.")
