"""Static Update 131 contracts for the consolidated smart timetable workflow."""
from pathlib import Path

from django.conf import settings


def run_smart_timetable_contract_audit(root=None):
    root = Path(root or settings.BASE_DIR)
    issues = []

    def require(path, snippets):
        target = root / path
        if not target.exists():
            issues.append({"code": "smart_missing_file", "message": f"ملف مطلوب غير موجود: {path}", "path": path})
            return
        text = target.read_text(encoding="utf-8")
        for snippet, message in snippets:
            if snippet not in text:
                issues.append({"code": "smart_contract_missing", "message": message, "path": path})

    require("teachers/models.py", [
        ("weekly_teaching_load", "حقل النصاب الأسبوعي غير موجود في نموذج المعلم الحالي."),
        ("free_period_policy", "سياسة فراغ المعلم غير موجودة في نموذج المعلم الحالي."),
    ])
    require("academics/models.py", [
        ("weekly_periods =", "عدد الحصص الأسبوعية ليس محفوظًا في المادة السنوية الرسمية."),
        ("canonical_key =", "هوية المادة الموحدة غير موجودة."),
        ("color =", "لون المادة الرسمي غير موجود."),
    ])
    require("timetable/models.py", [
        ("generated_for_smart_schedule", "تمييز أوقات الحصص المشتقة آليًا غير موجود."),
        ("placement_mode", "طريقة توزيع الاستراحة غير موجودة في سجل الحدث الحالي."),
        ("sections = models.ManyToManyField", "ربط الاستراحة بالشعب غير موجود في سجل الحدث الحالي."),
        ("time_slot__start_time__lt", "منع تعارض الأوقات المتداخلة غير مفعل."),
    ])
    require("timetable/services.py", [
        ("Subject.objects.filter", "المحرك لا يقرأ المادة والخطة السنوية الرسمية."),
        ("source_fingerprint", "حماية بصمة مصادر الاقتراح غير مفعلة."),
        ("official_entries", "الجدول الرسمي الحالي غير داخل بصمة مصادر الاقتراح."),
        ("transaction.atomic()", "اعتماد الجدول ليس داخل معاملة ذرية."),
        ("BREAK_MARGIN_MINUTES = 120", "نافذة الاستراحة الوسطية ذات الساعتين غير مثبتة."),
        ("CANONICAL_WORKING_DAYS", "أيام الأحد إلى الخميس غير مثبتة في المحرك."),
        ("boundary + duration <= latest_end", "الاستراحة لا تُلزم بالكامل بالنافذة الوسطية الآمنة."),
        ("teacher_day_caps", "توزيع الفراغ الأسبوعي على أيام المعلم غير مفعل."),
    ])
    require("timetable/views.py", [
        ('request.POST.get("action") in {"builder_preview", "builder_apply"}', "أفعال المعاينة والاعتماد المدمجة غير موجودة."),
        ('Sunset"] = "OPAL Update 132.0"', "المسار القديم غير معلّم للحذف في الإصدار التالي."),
    ])
    require("templates/timetable/dashboard.html", [
        ('id="smart-builder"', "المنشئ الذكي غير مدمج في شاشة الجدول الرسمية."),
        ('value="builder_apply"', "زر الاعتماد الذري غير موجود في شاشة الجدول."),
        ('name="source_fingerprint"', "بصمة المصادر غير مرسلة من الشاشة المدمجة."),
    ])

    forbidden = {
        "timetable/models.py": ["class TimetableDraft", "class SmartTimetable"],
        "timetable/urls.py": ["draft/", "proposal/", "new-smart-builder/"],
        "templates/timetable/dashboard.html": ["timetable:smart_builder"],
    }
    for path, snippets in forbidden.items():
        target = root / path
        if not target.exists():
            continue
        text = target.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet in text:
                issues.append({
                    "code": "smart_parallel_system",
                    "message": f"تم اكتشاف مكون موازٍ محظور: {snippet}",
                    "path": path,
                })

    if (root / "templates/timetable/smart_builder.html").exists():
        issues.append({
            "code": "smart_parallel_template",
            "message": "قالب المنشئ المستقل ما يزال موجودًا بعد الدمج.",
            "path": "templates/timetable/smart_builder.html",
        })

    return {
        "audit": "OPAL Update 131 consolidated smart timetable contracts",
        "ok": not issues,
        "issues": issues,
        "safety": {
            "new_timetable_model": False,
            "new_operational_route": False,
            "new_full_template": False,
            "canonical_student_model": "students.Student",
            "canonical_plan_model": "academics.Subject",
        },
    }
