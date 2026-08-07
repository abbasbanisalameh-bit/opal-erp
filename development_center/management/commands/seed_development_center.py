from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from development_center.models import Milestone, Module, Release, Sprint, Task


MODULE_NAMES = [
    "Core System",
    "Academics",
    "Students",
    "Guardians",
    "Admissions",
    "Attendance",
    "Exams",
    "Finance",
    "Documents",
    "Parents Portal",
    "Reports & BI",
    "Security",
]

TASKS = [
    (1, "Core System", "مراجعة هيكل المشروع وقاعدة البيانات"),
    (1, "Security", "مراجعة الصلاحيات والأمان الأساسي"),
    (1, "Core System", "تثبيت نسخة احتياطية مستقرة"),
    (2, "Academics", "إكمال الصفوف والشعب والمواد والأعوام"),
    (2, "Academics", "اختبار العلاقات الأكاديمية"),
    (3, "Students", "إكمال ملف الطالب الشامل"),
    (3, "Guardians", "ربط الطالب بملف ولي الأمر"),
    (3, "Admissions", "اختبار دورة تسجيل طالب جديد"),
    (3, "Documents", "ربط وثائق الطالب"),
    (4, "Attendance", "اختبار الحضور وتقاريره"),
    (4, "Academics", "مراجعة خطة المواد السنوية"),
    (5, "Exams", "اختبار الامتحانات والنشر"),
    (5, "Reports & BI", "مراجعة التقارير الأكاديمية"),
    (6, "Finance", "اختبار الرسوم والدفعات والإيصالات"),
    (6, "Parents Portal", "اختبار بوابة ولي الأمر"),
    (7, "Security", "مراجعة الصلاحيات النهائية"),
    (7, "Core System", "اختبار شامل واعتماد الإصدار"),
]


class Command(BaseCommand):
    help = "إنشاء أو تحديث بيانات مركز تطوير OPAL بصورة آمنة ومتكررة"

    def handle(self, *args, **options):
        today = timezone.localdate()
        release, _ = Release.objects.update_or_create(
            version="OPAL ERP Core",
            defaults={
                "title": "OPAL ERP Core",
                "description": "خطة النواة التشغيلية المعتمدة لنظام OPAL ERP.",
                "planned_date": today + timedelta(days=14),
                "released": False,
            },
        )

        modules = {}
        for name in MODULE_NAMES:
            modules[name], _ = Module.objects.update_or_create(
                name=name,
                defaults={
                    "description": f"وحدة {name} ضمن OPAL ERP",
                    "status": "planned",
                    "progress": 0,
                },
            )

        sprints = {}
        for number in range(1, 8):
            start = today + timedelta(days=(number - 1) * 2)
            sprints[number], _ = Sprint.objects.update_or_create(
                title=f"Sprint {number}",
                defaults={
                    "goal": f"إنجاز أهداف الحزمة {number}",
                    "start_date": start,
                    "end_date": start + timedelta(days=1),
                    "status": "active" if number == 1 else "planned",
                },
            )

        for number, title in enumerate(
            [
                "اعتماد النواة",
                "اعتماد الأكاديميات",
                "اعتماد الطالب وملف ولي الأمر",
                "اعتماد التشغيل اليومي",
                "اعتماد النتائج والتقارير",
                "اعتماد الرسوم والبوابة",
                "اعتماد الإصدار النهائي",
            ],
            start=1,
        ):
            Milestone.objects.update_or_create(
                title=title,
                defaults={
                    "version": release,
                    "target_date": today + timedelta(days=number * 2),
                    "progress": 0,
                    "completed": False,
                },
            )

        for sprint_number, module_name, title in TASKS:
            sprint = sprints[sprint_number]
            Task.objects.update_or_create(
                title=title,
                defaults={
                    "module": modules[module_name],
                    "release": release,
                    "sprint": sprint,
                    "status": "todo",
                    "progress": 0,
                    "start_date": sprint.start_date,
                    "due_date": sprint.end_date,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"تم تحديث مركز التطوير: {Module.objects.count()} وحدة، "
                f"{Sprint.objects.count()} حزم، {Task.objects.count()} مهمة."
            )
        )
