from datetime import date, timedelta
from development_center.models import Module, Release, Milestone, Sprint, Task

today = date.today()

def valid_fields(model):
    return {f.name for f in model._meta.fields}

def safe_create(model, lookup, data):
    fields = valid_fields(model)
    clean = {k: v for k, v in data.items() if k in fields}
    obj, created = model.objects.update_or_create(**lookup, defaults=clean)
    return obj

release = safe_create(
    Release,
    {"version": "OPAL ERP v1.0"},
    {
        "title": "الإصدار الأول من OPAL ERP",
        "description": "نسخة تشغيلية أولى جاهزة للاستخدام المدرسي.",
        "planned_date": today + timedelta(days=14),
        "released": False,
    }
)

modules_names = [
    "Core System", "Academics", "Students", "Attendance", "Exams",
    "Curriculum", "Finance", "Parents Portal", "Documents",
    "Reports & BI", "Security"
]

modules = {}
for name in modules_names:
    modules[name] = safe_create(
        Module,
        {"name": name},
        {
            "description": f"وحدة {name} ضمن OPAL ERP v1.0",
            "status": "planned",
            "progress": 0,
        }
    )

milestones = [
    ("Core System Ready", 2),
    ("Academics Complete", 5),
    ("Operations Complete", 9),
    ("Finance & Portal Complete", 12),
    ("OPAL ERP v1.0 Release", 14),
]

for title, days in milestones:
    safe_create(
        Milestone,
        {"title": title},
        {
            "version": release,
            "target_date": today + timedelta(days=days),
            "progress": 0,
            "completed": False,
        }
    )

sprints = {}
for i in range(1, 8):
    start = today + timedelta(days=(i - 1) * 2)
    end = start + timedelta(days=1)
    sprints[i] = safe_create(
        Sprint,
        {"title": f"Sprint {i}"},
        {
            "goal": f"إنجاز أهداف Sprint {i} ضمن خطة OPAL ERP v1.0",
            "start_date": start,
            "end_date": end,
            "status": "planned" if i > 1 else "active",
        }
    )

tasks = [
    (1, "Core System", "مراجعة هيكل مشروع OPAL ERP"),
    (1, "Core System", "مراجعة قاعدة البيانات والعلاقات"),
    (1, "Core System", "مراجعة الصلاحيات الأساسية"),
    (1, "Core System", "تنظيف الأخطاء الحرجة"),
    (1, "Core System", "اعتماد Core System للإصدار v1.0"),

    (2, "Academics", "إكمال السجل الأكاديمي للطالب"),
    (2, "Academics", "إكمال إدارة الصفوف والشعب"),
    (2, "Academics", "إكمال إدارة المواد"),
    (2, "Academics", "إضافة اختبارات الوحدة الأكاديمية"),
    (2, "Students", "مراجعة إدارة بيانات الطلاب"),

    (3, "Students", "إكمال ملف الطالب الشامل"),
    (3, "Students", "ربط الطالب بولي الأمر"),
    (3, "Documents", "ربط وثائق الطالب"),
    (3, "Students", "اختبار دورة تسجيل الطالب"),
    (3, "Academics", "تجهيز ترقية الطلاب بين الصفوف"),

    (4, "Attendance", "مراجعة نظام الحضور"),
    (4, "Attendance", "ربط الحضور بالطلاب والشعب"),
    (4, "Curriculum", "مراجعة الخطة الدراسية"),
    (4, "Curriculum", "ربط المواد بالصفوف"),
    (4, "Reports & BI", "تقرير حضور أولي"),

    (5, "Exams", "مراجعة نظام الامتحانات"),
    (5, "Exams", "ربط العلامات بالطلاب"),
    (5, "Reports & BI", "تقرير علامات أولي"),
    (5, "Reports & BI", "لوحة تقارير أكاديمية"),
    (5, "Security", "اختبار الصلاحيات الأكاديمية"),

    (6, "Finance", "مراجعة النظام المالي"),
    (6, "Finance", "ربط الرسوم بالطلاب"),
    (6, "Parents Portal", "مراجعة بوابة ولي الأمر"),
    (6, "Parents Portal", "عرض بيانات الطالب لولي الأمر"),
    (6, "Reports & BI", "تقرير مالي أولي"),

    (7, "Core System", "اختبار شامل لجميع الوحدات"),
    (7, "Security", "مراجعة الأمان والصلاحيات"),
    (7, "Reports & BI", "مراجعة التقارير النهائية"),
    (7, "Core System", "إنشاء نسخة احتياطية نهائية"),
    (7, "Core System", "إصدار OPAL ERP v1.0"),
]

for sprint_no, module_name, title in tasks:
    start = sprints[sprint_no].start_date
    end = sprints[sprint_no].end_date

    task, created = Task.objects.update_or_create(
        title=title,
        defaults={
            "module": modules[module_name],
            "release": release,
            "sprint": sprints[sprint_no],
            "status": "todo",
            "progress": 0,
            "start_date": start,
            "due_date": end,
        }
    )

print("✅ OPAL ERP v1.0 seed completed successfully")
print(f"Modules: {Module.objects.count()}")
print(f"Sprints: {Sprint.objects.count()}")
print(f"Tasks: {Task.objects.count()}")
