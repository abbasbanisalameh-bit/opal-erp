from django import template

register = template.Library()


@register.filter
def ar_status(value):
    labels = {
        "todo": "لم يبدأ",
        "doing": "قيد التنفيذ",
        "review": "قيد المراجعة",
        "done": "مكتملة",
        "planned": "مخطط",
        "active": "نشط",
        "completed": "مكتمل",
        "development": "قيد التطوير",
        "open": "مفتوح",
        "in_progress": "قيد الإصلاح",
        "fixed": "تم الإصلاح",
        "closed": "مغلق",
        "new": "جديدة",
        "study": "قيد الدراسة",
        "approved": "معتمدة",
        "implemented": "تم تنفيذها",
        "rejected": "مرفوضة",
        "proposed": "مقترح",
        "deprecated": "ملغي",
    }
    return labels.get(value, value)


@register.filter
def ar_priority(value):
    labels = {
        "low": "منخفضة",
        "medium": "متوسطة",
        "high": "عالية",
        "critical": "حرجة",
        1: "حرجة",
        2: "عالية",
        3: "متوسطة",
        4: "منخفضة",
        5: "منخفضة",
    }
    return labels.get(value, value)
