from django.core.management.base import BaseCommand, CommandError

from core.demo_data import reset_demo_school


class Command(BaseCommand):
    help = "حذف البيانات التجريبية الموسومة فقط، دون لمس البيانات الحقيقية أو إعدادات المدرسة."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="تأكيد حذف البيانات التجريبية.")

    def handle(self, *args, **options):
        if not options["yes"]:
            raise CommandError("أضف --yes للتأكيد. لن تُحذف أي بيانات دون التأكيد.")
        result = reset_demo_school()
        self.stdout.write(self.style.SUCCESS(
            f"تم حذف البيانات التجريبية فقط: {result['students']} طالب، "
            f"{result['families']} أسرة، {result['teachers']} معلم."
        ))
