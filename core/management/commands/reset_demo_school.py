from django.core.management.base import BaseCommand, CommandError

from core.system_data import reset_all_operational_data


class Command(BaseCommand):
    help = "تصفير جميع البيانات التشغيلية مع إبقاء حسابات المدير الأعلى وإعدادات النظام."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="تأكيد تصفير جميع البيانات التشغيلية.")

    def handle(self, *args, **options):
        if not options["yes"]:
            raise CommandError("أضف --yes للتأكيد. لن تُحذف أي بيانات دون التأكيد.")
        result = reset_all_operational_data()
        self.stdout.write(self.style.SUCCESS(
            f"تم تصفير البيانات التشغيلية: {result['students']} طالب، "
            f"{result['families']} ملف ولي أمر، {result['teachers']} معلم."
        ))
