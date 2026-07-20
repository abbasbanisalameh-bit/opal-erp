import calendar

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounting.financial_services import close_monthly_statement
from core.models import School


class Command(BaseCommand):
    help = "يغلق الكشف المالي في آخر يوم فعلي من الشهر ويرحل صافي الرصيد للشهر التالي."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="السماح بالتنفيذ اليدوي بعد نهاية الشهر")
        parser.add_argument("--username", default="", help="اسم المستخدم الذي يسجل كمنفذ للإغلاق")

    def handle(self, *args, **options):
        today = timezone.localdate()
        month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        if today != month_end and not options["force"]:
            self.stdout.write(self.style.WARNING("اليوم ليس آخر يوم من الشهر؛ لم يُغلق أي كشف."))
            return
        User = get_user_model()
        user = None
        if options["username"]:
            user = User.objects.filter(username=options["username"], is_active=True).first()
        user = user or User.objects.filter(is_superuser=True, is_active=True).order_by("pk").first()
        if user is None:
            raise CommandError("لا يوجد مدير نظام فعال لتسجيل منفذ الإغلاق.")
        closed = 0
        for school in School.objects.filter(is_active=True):
            statement = close_monthly_statement(school=school, period_end=month_end, user=user)
            closed += 1
            self.stdout.write(self.style.SUCCESS(f"{school}: الرصيد المدور {statement.closing_balance}"))
        self.stdout.write(self.style.SUCCESS(f"تمت معالجة {closed} مدرسة."))
