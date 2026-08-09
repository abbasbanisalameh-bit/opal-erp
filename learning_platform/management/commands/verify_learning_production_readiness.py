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
        category_labels = {"required": "إلزامي", "optional": "اختياري", "hosting": "قيد استضافة"}
        for item in result["checks"]:
            marker = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}[item["status"]]
            category = category_labels.get(item.get("requirement"), "إلزامي")
            self.stdout.write(f"[{marker}] [{category}] {item['label']}: {item['detail']}")
        breakdown = result.get("warning_breakdown", {})
        self.stdout.write(
            f"overall={result['overall']} blocking_failures={result['blocking_failures']} warnings={result['warnings']} "
            f"required_warnings={breakdown.get('required', 0)} optional_warnings={breakdown.get('optional', 0)} "
            f"hosting_warnings={breakdown.get('hosting', 0)} sales_mode={result.get('subscription_sales_mode', 'cards')}"
        )
        if result["blocking_failures"] or (options["strict"] and result["warnings"]):
            raise CommandError("منصة أوبال التعليمية لم تجتز بوابة الجاهزية المطلوبة.")
        self.stdout.write(self.style.SUCCESS("اجتازت المنصة بوابة الجاهزية المطلوبة."))
