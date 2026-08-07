from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core.system_data import DEMO_TEACHER_COUNT, seed_system_data


class Command(BaseCommand):
    help = "إدخال بيانات مدرسة شاملة مترابطة عبر المصادر الرسمية في OPAL."

    def add_arguments(self, parser):
        parser.add_argument("--students", type=int, default=500)
        parser.add_argument("--teachers", type=int, default=DEMO_TEACHER_COUNT)
        parser.add_argument("--user", default="", help="اسم مستخدم المدير الأعلى الذي تُنسب العملية إليه.")

    def _resolve_superuser(self, username):
        users = get_user_model().objects.filter(is_superuser=True, is_active=True)
        if username:
            user = users.filter(username=username).first()
            if user is None:
                raise CommandError("اسم مستخدم المدير الأعلى غير موجود أو غير فعال.")
            return user
        if users.count() == 1:
            return users.first()
        raise CommandError("حدد حساب المدير الأعلى صراحةً عبر --user USERNAME.")

    def handle(self, *args, **options):
        user = self._resolve_superuser(options["user"])
        result = seed_system_data(user=user)
        self.stdout.write(self.style.SUCCESS(
            f"تم إدخال البيانات المترابطة والتحقق منها: {result['students']} طالب، "
            f"{result['families']} ملف ولي أمر، {result['teachers']} معلم، {result['sections']} شعبة، "
            f"{result['assignments']} تكليف، {result['breaks']} استراحات، "
            f"{result['timetable_entries']} حصة مجدولة."
        ))
