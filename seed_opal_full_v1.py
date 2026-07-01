from datetime import date, timedelta
from development_center.models import Module, Release, Milestone, Sprint, Task

today = date.today()

def fields(model):
    return {f.name for f in model._meta.fields}

def create_or_update(model, lookup, defaults):
    clean = {k: v for k, v in defaults.items() if k in fields(model)}
    obj, created = model.objects.update_or_create(**lookup, defaults=clean)
    return obj

release = create_or_update(
    Release,
    {"version": "OPAL ERP v1.0"},
    {
        "title": "OPAL ERP v1.0",
        "description": "الإصدار التشغيلي الأول لنظام OPAL ERP خلال 14 يوم.",
        "planned_date": today + timedelta(days=14),
        "released": False,
    }
)

module_names = [
    "Core System",
    "Academics",
    "Students",
    "Guardians",
    "Admissions",
    "Attendance",
    "Curriculum",
    "Exams",
    "Finance",
    "Documents",
    "Parents Portal",
    "Reports & BI",
    "Security",
]

modules = {}
for name in module_names:
    modules[name] = create_or_update(
        Module,
        {"name": name},
        {
            "description": f"وحدة {name} ضمن OPAL ERP v1.0",
            "status": "planned",
            "progress": 0,
        }
    )

sprints = {}
for i in range(1, 8):
    start = today + timedelta(days=(i - 1) * 2)
    end = start + timedelta(days=1)

    sprints[i] = create_or_update(
        Sprint,
        {"title": f"Sprint {i}"},
        {
            "goal": f"إنجاز أهداف Sprint {i} ضمن خطة OPAL ERP v1.0",
            "start_date": start,
            "end_date": end,
            "status": "active" if i == 1 else "planned",
        }
    )

milestones = [
    ("Core System Ready", 2),
    ("Academics Ready", 4),
    ("Students & Guardians Ready", 6),
    ("Attendance & Curriculum Ready", 8),
    ("Exams & Reports Ready", 10),
    ("Finance & Parent Portal Ready", 12),
    ("Final Testing & Release", 14),
]

for title, days in milestones:
    create_or_update(
        Milestone,
        {"title": title},
        {
            "version": release,
            "target_date": today + timedelta(days=days),
            "progress": 0,
            "completed": False,
        }
    )

tasks = [
    # Sprint 1 - Core
    (1, "Core System", "مراجعة هيكل المشروع"),
    (1, "Core System", "مراجعة قاعدة البيانات"),
    (1, "Core System", "مراجعة العلاقات بين الجداول"),
    (1, "Core System", "مراجعة الصلاحيات الأساسية"),
    (1, "Core System", "تنظيف الأخطاء الحرجة"),
    (1, "Security", "مراجعة الأمان الأساسي"),
    (1, "Reports & BI", "تثبيت لوحة Executive Dashboard"),
    (1, "Core System", "إنشاء نسخة احتياطية مستقرة"),

    # Sprint 2 - Academics
    (2, "Academics", "إكمال الصفوف الدراسية"),
    (2, "Academics", "إكمال الشعب الدراسية"),
    (2, "Academics", "إكمال المواد الدراسية"),
    (2, "Academics", "إكمال السنوات الدراسية"),
    (2, "Academics", "إكمال السجل الأكاديمي للطالب"),
    (2, "Academics", "إضافة اختبارات Academics"),
    (2, "Academics", "مراجعة واجهات Academics"),

    # Sprint 3 - Students
    (3, "Students", "إكمال ملف الطالب الشامل"),
    (3, "Students", "إكمال بيانات الطالب الشخصية"),
    (3, "Students", "ربط الطالب بالفرع والمدرسة"),
    (3, "Guardians", "إكمال أولياء الأمور"),
    (3, "Guardians", "ربط الطالب بولي الأمر"),
    (3, "Documents", "إكمال وثائق الطالب"),
    (3, "Admissions", "مراجعة دورة تسجيل طالب جديد"),

    # Sprint 4 - Attendance + Curriculum
    (4, "Attendance", "إكمال سجل الحضور اليومي"),
    (4, "Attendance", "ربط الحضور بالطلاب والشعب"),
    (4, "Attendance", "تقرير الحضور الأساسي"),
    (4, "Curriculum", "إكمال الخطة الدراسية"),
    (4, "Curriculum", "ربط المواد بالصفوف"),
    (4, "Curriculum", "مراجعة واجهات الخطة الدراسية"),

    # Sprint 5 - Exams + Reports
    (5, "Exams", "إكمال إدارة الامتحانات"),
    (5, "Exams", "ربط العلامات بالطلاب"),
    (5, "Exams", "إدخال العلامات"),
    (5, "Reports & BI", "تقرير علامات الطلاب"),
    (5, "Reports & BI", "تقرير أكاديمي شامل"),
    (5, "Reports & BI", "اختبار التقارير الأساسية"),

    # Sprint 6 - Finance + Parent Portal
    (6, "Finance", "مراجعة النظام المالي"),
    (6, "Finance", "ربط الرسوم بالطلاب"),
    (6, "Finance", "تقرير مالي أولي"),
    (6, "Parents Portal", "إكمال بوابة ولي الأمر"),
    (6, "Parents Portal", "عرض بيانات الطالب لولي الأمر"),
    (6, "Parents Portal", "عرض الحضور والنتائج لولي الأمر"),

    # Sprint 7 - Final
    (7, "Security", "مراجعة الصلاحيات النهائية"),
    (7, "Core System", "اختبار شامل لجميع الوحدات"),
    (7, "Reports & BI", "مراجعة التقارير النهائية"),
    (7, "Core System", "إصلاح الأخطاء النهائية"),
    (7, "Core System", "إنشاء نسخة احتياطية نهائية"),
    (7, "Core System", "اعتماد OPAL ERP v1.0"),
]

for sprint_no, module_name, title in tasks:
    sprint = sprints[sprint_no]
    start = sprint.start_date
    end = sprint.end_date

    Task.objects.update_or_create(
        title=title,
        defaults={
            "module": modules[module_name],
            "release": release,
            "sprint": sprint,
            "status": "todo",
            "progress": 0,
            "start_date": start,
            "due_date": end,
        }
    )

print("✅ تم تعبئة بيانات OPAL ERP v1.0 بنجاح")
print("Modules:", Module.objects.count())
print("Sprints:", Sprint.objects.count())
print("Tasks:", Task.objects.count())
