from django.core.management.base import BaseCommand, CommandError

from learning_platform.production import collect_learning_readiness_checks


class Command(BaseCommand):
    help = "افحص جاهزية منصة أوبال التعليمية للتشغيل التجريبي أو الفعلي."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="اعتبر التحذيرات سببًا لفشل الأمر أيضًا.",
        )

    def handle(self, *args, **options):
        result = collect_learning_readiness_checks(include_migrations=True)
        for item in result["checks"]:
            marker = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}[item["status"]]
            self.stdout.write(f"[{marker}] {item['label']}: {item['detail']}")
        self.stdout.write(
            f"overall={result['overall']} blocking_failures={result['blocking_failures']} warnings={result['warnings']}"
        )
        if result["blocking_failures"] or (options["strict"] and result["warnings"]):
            raise CommandError("منصة أوبال التعليمية لم تجتز بوابة الجاهزية المطلوبة.")
        self.stdout.write(self.style.SUCCESS("اجتازت المنصة بوابة الجاهزية المطلوبة."))
