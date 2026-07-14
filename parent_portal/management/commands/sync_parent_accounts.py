from django.core.management.base import BaseCommand
from django.db import transaction

from students.models import Student
from parent_portal.services import create_or_update_parent_family_for_student


class Command(BaseCommand):
    help = "إنشاء/تحديث حسابات أولياء الأمور وربط الأبناء بناءً على بيانات الطلاب الحالية."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="عرض ما سيتم تنفيذه دون حفظ.")
        parser.add_argument("--active-only", action="store_true", default=True, help="معالجة الطلاب النشطين فقط.")

    def handle(self, *args, **options):
        dry_run = options.get("dry_run")
        qs = Student.objects.all().order_by("full_name")
        if options.get("active_only"):
            qs = qs.filter(is_active=True)

        total = qs.count()
        linked = 0
        skipped = 0
        created_users = 0

        if dry_run:
            self.stdout.write(self.style.WARNING("وضع التجربة فقط: لن يتم حفظ أي تعديل."))

        with transaction.atomic():
            for student in qs:
                phone = (getattr(student, "phone", "") or "").strip()
                guardian_name = (getattr(student, "guardian_name", "") or getattr(student, "father_name", "") or "ولي أمر").strip()
                if not phone and not guardian_name:
                    skipped += 1
                    self.stdout.write(self.style.WARNING(f"تخطي: {student.full_name} — لا توجد بيانات ولي أمر كافية."))
                    continue
                family = create_or_update_parent_family_for_student(
                    student,
                    guardian_name=guardian_name,
                    phone=phone,
                    school=None,
                    national_id="",
                )
                linked += 1
                if getattr(family, "account_created_now", False):
                    created_users += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"تم إنشاء حساب: {student.full_name} -> {family.user.username} / {getattr(family, 'initial_password', '')}"
                    ))
                else:
                    username = family.user.username if family.user else "بدون مستخدم"
                    self.stdout.write(f"تم الربط: {student.full_name} -> {username}")

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("-" * 60)
        self.stdout.write(self.style.SUCCESS(f"إجمالي الطلاب: {total}"))
        self.stdout.write(self.style.SUCCESS(f"تم الربط/التحديث: {linked}"))
        self.stdout.write(self.style.SUCCESS(f"حسابات جديدة: {created_users}"))
        self.stdout.write(self.style.WARNING(f"تم التخطي: {skipped}"))
