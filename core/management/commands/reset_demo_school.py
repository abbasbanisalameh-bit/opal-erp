from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core.system_data import reset_all_operational_data


class Command(BaseCommand):
    help = "تصفير جميع البيانات التشغيلية مع إبقاء حساب المدير الأعلى المحدد وبنية الصلاحيات."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="تأكيد تصفير جميع البيانات التشغيلية.")
        parser.add_argument("--user", default="", help="اسم مستخدم المدير الأعلى الذي يجب إبقاؤه.")

    def _resolve_superuser(self, username):
        users = get_user_model().objects.filter(is_superuser=True, is_active=True)
        if username:
            user = users.filter(username=username).first()
            if user is None:
                raise CommandError("اسم مستخدم المدير الأعلى غير موجود أو غير فعال.")
            return user
        if users.count() == 1:
            return users.first()
        raise CommandError("حدد حساب المدير الأعلى الذي سيبقى عبر --user USERNAME.")

    def handle(self, *args, **options):
        if not options["yes"]:
            raise CommandError("أضف --yes للتأكيد. لن تُحذف أي بيانات دون التأكيد.")
        user = self._resolve_superuser(options["user"])
        result = reset_all_operational_data(keep_user=user)
        self.stdout.write(self.style.SUCCESS(
            f"تم تصفير البيانات التشغيلية: {result['students']} طالب، "
            f"{result['families']} ملف ولي أمر، {result['teachers']} معلم."
        ))
