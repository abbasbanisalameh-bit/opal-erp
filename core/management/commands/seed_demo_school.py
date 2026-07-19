from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core.system_data import seed_system_data


class Command(BaseCommand):
    help = "إدخال بيانات مدرسة شاملة مترابطة عبر المصادر الرسمية في OPAL."

    def add_arguments(self, parser):
        parser.add_argument("--students", type=int, default=500)
        parser.add_argument("--teachers", type=int, default=50)
        parser.add_argument("--user", default="", help="اسم مستخدم إداري لنسب السجلات إليه.")

    def handle(self, *args, **options):
        user = None
        if options["user"]:
            user = get_user_model().objects.filter(username=options["user"]).first()
            if user is None:
                raise CommandError("اسم المستخدم الإداري غير موجود.")
        result = seed_system_data(student_count=500, teacher_count=50, guardian_count=300, user=user)
        self.stdout.write(self.style.SUCCESS(
            f"تم إدخال البيانات الشاملة: {result['students']} طالب، {result['families']} ملف ولي أمر، "
            f"{result['teachers']} معلم، {result['sections']} شعب."
        ))
