from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core.demo_data import seed_demo_school


class Command(BaseCommand):
    help = "إضافة بيانات مدرسة تجريبية مترابطة عبر المصادر الرسمية في OPAL."

    def add_arguments(self, parser):
        parser.add_argument("--students", type=int, default=100)
        parser.add_argument("--teachers", type=int, default=20)
        parser.add_argument("--user", default="", help="اسم مستخدم إداري لنسب السجلات إليه.")

    def handle(self, *args, **options):
        user = None
        if options["user"]:
            user = get_user_model().objects.filter(username=options["user"]).first()
            if user is None:
                raise CommandError("اسم المستخدم الإداري غير موجود.")
        result = seed_demo_school(student_count=options["students"], teacher_count=options["teachers"], user=user)
        self.stdout.write(self.style.SUCCESS(
            f"تم تجهيز البيانات التجريبية: {result['students']} طالب، {result['families']} ملف ولي أمر، "
            f"{result['teachers']} معلم، {result['sections']} شعب."
        ))
