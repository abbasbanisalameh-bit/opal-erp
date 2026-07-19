"""Canonical OPAL operation catalogue.

Each business operation is assigned one canonical route. Other pages may link to the
same route, but they must not implement a second form or a second source of truth.
"""

from __future__ import annotations

from django.conf import settings
from django.urls import NoReverseMatch, reverse


MANAGEMENT = "management"
TEACHER = "teacher"
PARENT = "parent"
AUTHENTICATED = "authenticated"


MODULES = {
    "overview": {"label": "القيادة والمتابعة", "icon": "speedometer2", "color": "indigo", "order": 10},
    "students": {"label": "الطلاب وأولياء الأمور", "icon": "people-fill", "color": "blue", "order": 20},
    "academics": {"label": "الشؤون الأكاديمية", "icon": "mortarboard-fill", "color": "violet", "order": 30},
    "finance": {"label": "الرسوم المدرسية", "icon": "cash-stack", "color": "emerald", "order": 40},
    "communication": {"label": "التواصل والإشعارات", "icon": "bell-fill", "color": "amber", "order": 50},
    "documents": {"label": "الوثائق والتقارير", "icon": "file-earmark-text-fill", "color": "cyan", "order": 60},
    "settings": {"label": "الإعدادات والسلامة", "icon": "gear-fill", "color": "slate", "order": 70},
    "portal": {"label": "بوابتي", "icon": "person-workspace", "color": "rose", "order": 80},
}


def _op(key, module, label, route, description, *, roles=(MANAGEMENT,), icon="arrow-left-circle", keywords="", optional=None, order=100):
    return {
        "key": key,
        "module": module,
        "label": label,
        "route": route,
        "description": description,
        "roles": tuple(roles),
        "icon": icon,
        "keywords": keywords,
        "optional": optional,
        "order": order,
    }


# No object-specific route appears here. Actions such as edit/delete/issue are launched
# from their canonical list/detail screen so the user always starts in one predictable place.
OPERATIONS = [
    _op("operations-center", "overview", "دليل العمليات الموحد", "core:operations_center", "الخريطة الرسمية لجميع إجراءات النظام ومسارات التكامل.", icon="signpost-split-fill", keywords="دليل خريطة بحث عمليات", order=1),
    _op("executive-dashboard", "overview", "لوحة الإدارة", "dashboard:home", "المؤشرات التنفيذية، المخاطر، رضا المستخدمين وآخر المستجدات.", icon="grid-1x2-fill", keywords="لوحة مدير مؤشرات رضا", order=2),

    _op("student-list", "students", "قائمة الطلاب", "students:student_list", "البحث عن الطالب وفتح بطاقة الطالب 360؛ وهي الملف الرسمي الموحد.", icon="people-fill", keywords="طلاب طالب 360 ملف", order=10),
    _op("student-registration", "students", "تسجيل طالب", "admissions:direct_registration", "المسار الوحيد لإنشاء طالب جديد وربطه بالقيد والرسوم وولي الأمر.", icon="person-plus-fill", keywords="تسجيل قبول طالب جديد", order=11),
    _op("candidates", "students", "المرشحون للقبول", "admissions:candidate_list", "إدارة المرشحين قبل تحويلهم إلى تسجيل فعلي.", icon="person-lines-fill", keywords="مرشح قبول طلب", order=12),
    _op("student-register", "students", "سجل الطلبة", "admissions:admission_list", "سجل عمليات التسجيل والإيصالات المرتبطة بها.", icon="card-checklist", keywords="سجل التسجيل الطلبة", order=13),
    _op("families", "students", "ملفات أولياء الأمور", "parent_portal:family_management", "إدارة الأسرة والحساب والأبناء وكشف الأسرة من مكان واحد.", icon="person-vcard-fill", keywords="ولي أمر أسرة إخوة حساب", order=14),
    _op("student-lifecycle", "students", "حركة الطلاب", "academics:lifecycle_list", "الترفيع والنقل والانسحاب وإعادة القيد والتخرج مع سجل تدقيق.", icon="arrow-repeat", keywords="ترفيع نقل انسحاب تخرج", order=15),
    _op("registration-settings", "students", "إعدادات التسجيل", "admissions:registration_settings", "إعداد رسوم التسجيل والخصومات والسياسات من الشاشة الرسمية.", icon="sliders", keywords="إعداد تسجيل خصم رسوم", order=16),

    _op("academic-structure", "academics", "الهيكل الدراسي", "academics:academic_structure", "إدارة الصفوف والشعب ورسوم الصف في الشاشة الرسمية المترابطة.", icon="diagram-3-fill", keywords="صفوف شعب رسوم هيكل", order=20),
    _op("academic-years", "academics", "الأعوام الدراسية", "academics:academic_year_list", "إنشاء العام وتنشيطه وإغلاقه وفق دورة أكاديمية واحدة.", icon="calendar-range-fill", keywords="عام أكاديمي إغلاق", order=21),
    _op("semesters", "academics", "الفصول الدراسية", "academics:semester_list", "إدارة الفصلين داخل العام الدراسي.", icon="calendar2-event-fill", keywords="فصل دراسي", order=22),
    _op("subjects", "academics", "المواد الدراسية", "academics:subject_list", "تعريف مواد كل صف قبل التكليف والجدول والامتحانات.", icon="book-half", keywords="مادة مواد", order=23),
    _op("curriculum", "academics", "الخطة الدراسية", "curriculum:curriculum_list", "ربط مواد الصف بعدد الحصص الأسبوعية داخل العام الدراسي.", icon="journal-bookmark-fill", keywords="خطة منهاج حصص أسبوعية", order=24),
    _op("teachers", "academics", "إدارة المعلمين", "teachers:dashboard", "ملفات المعلمين والحسابات والتكليفات التدريسية.", icon="person-badge-fill", keywords="معلم تكليف حساب", order=25),
    _op("timetable", "academics", "الجدول الدراسي", "timetable:dashboard", "عرض وإدارة الجدول حسب اليوم والمعلم والمادة والصف.", icon="calendar3", keywords="جدول حصة معلم صف مادة", order=26),
    _op("smart-timetable", "academics", "منشئ الجدول الذكي", "timetable:smart_builder", "توليد الجدول من التكليفات مع منع التعارضات.", icon="magic", keywords="توليد جدول ذكي", order=27),
    _op("schedule-settings", "academics", "إعدادات اليوم المدرسي", "timetable:schedule_settings", "الحصص والاستراحات والطابور والتنبيهات الزمنية.", icon="clock-fill", keywords="حصة وقت استراحة طابور", order=28),
    _op("teacher-absence", "academics", "غياب المعلمين والإشغال", "timetable:absence_center", "تسجيل غياب المعلم وتعيين البديل للحصص المتأثرة.", icon="person-x-fill", keywords="غياب معلم بديل إشغال", order=29),
    _op("attendance", "academics", "الحضور والغياب", "attendance_v2:dashboard", "تسجيل الحضور الإداري؛ والمعلم يسجل من بوابته وفق صلاحياته.", icon="calendar-check-fill", keywords="حضور غياب تأخر مغادرة", order=30),
    _op("attendance-report", "academics", "تقرير الحضور", "attendance_v2:report", "تحليل سجلات الحضور والغياب والتأخر.", icon="clipboard-data-fill", keywords="تقرير حضور", order=31),
    _op("exams", "academics", "الامتحانات", "exams:exam_list", "إنشاء الامتحان وفتحه واعتماده ونشره وإغلاقه.", icon="file-earmark-check-fill", keywords="امتحان اختبار", order=32),
    _op("marks", "academics", "العلامات", "exams:mark_list", "المراجعة الإدارية للعلامات؛ وإدخال المعلم يبدأ من تكليفه.", icon="list-ol", keywords="علامة درجات نتائج", order=33),
    _op("exam-analysis", "academics", "تحليل النتائج", "exams:exam_dashboard", "تحليل النجاح والمتوسطات حسب العام والصف والمادة.", icon="graph-up-arrow", keywords="تحليل نتائج نجاح", order=34),

    _op("finance-dashboard", "finance", "ملخص الرسوم", "accounting:dashboard", "التحصيل والمتبقي والمتأخر والمصروفات دون محاسبة عامة.", icon="speedometer", keywords="رسوم تحصيل متبقي", order=40),
    _op("fee-categories", "finance", "فئات الرسوم", "accounting:fee_category_list", "تعريف أنواع الرسوم وقيمها الأساسية من مكان واحد.", icon="tags-fill", keywords="فئة نوع رسوم", order=41),
    _op("student-invoices", "finance", "رسوم الطلاب", "accounting:invoice_list", "عرض الرسوم وإصدار رسم إضافي وإلغاء الرسم وفق الضوابط.", icon="file-earmark-spreadsheet-fill", keywords="فاتورة رسم طالب إصدار", order=42),
    _op("fee-payment", "finance", "تسديد الرسوم", "admissions:fee_payment_create", "المسار الوحيد لدفعة طالب أو دفعة عن جميع الإخوة والتوزيع التلقائي.", icon="cash-coin", keywords="دفع دفعة إيصال إخوة", order=43),
    _op("payment-archive", "finance", "أرشيف التسديد", "admissions:fee_payment_archive", "عرض الإيصالات والطباعة والحذف الآمن من الأرشيف الرسمي.", icon="archive-fill", keywords="أرشيف إيصال حذف آمن", order=44),
    _op("installments", "finance", "الأقساط", "accounting:installment_list", "متابعة أقساط الرسوم ومواعيدها وحالاتها.", icon="calendar2-week-fill", keywords="قسط أقساط موعد", order=45),
    _op("discounts", "finance", "طلبات الخصم", "accounting:discount_list", "طلبات الخصم وقراراتها المرتبطة بسير العمل الداخلي.", icon="percent", keywords="خصم طلب اعتماد", order=46),
    _op("expenses", "finance", "المصروفات المدرسية", "accounting:expense_list", "سجل المصروفات المبسط مع حذف آمن.", icon="receipt-cutoff", keywords="مصروف", order=47),
    _op("monthly-finance", "finance", "كشف 28 الشهري", "accounting:monthly_report", "كشف التحصيل والمصروف والمتوقع للدورة الشهرية.", icon="calendar2-check-fill", keywords="كشف شهري 28", order=48),
    _op("finance-close", "finance", "إغلاق العام المالي", "accounting:financial_year_close", "إغلاق الرسوم وترحيل الأرصدة وفق العام الدراسي.", icon="arrow-left-right", keywords="إغلاق مالي ترحيل", order=49),

    _op("communication-center", "communication", "مركز التواصل", "enterprise_ops:dashboard", "ملخص الشكاوى والتقييمات والتعاميم والإشعارات.", icon="chat-square-heart-fill", keywords="تواصل شكوى تقييم", order=50),
    _op("feedback", "communication", "الشكاوى والاقتراحات", "enterprise_ops:feedback_list", "استقبال الرسائل وتقييم جودة التدريس والخدمات الإلكترونية والرد عليها.", roles=(MANAGEMENT, TEACHER, PARENT), icon="chat-square-text-fill", keywords="شكوى اقتراح تقييم", order=51),
    _op("broadcasts", "communication", "التعاميم والتنبيهات", "enterprise_ops:broadcast_list", "إرسال تعميم للمعلمين أو أولياء الأمور أو الجميع وتنبيه معلم محدد.", icon="megaphone-fill", keywords="تعميم تنبيه", order=52),
    _op("announcements", "communication", "إدارة الإعلانات", "announcements:list", "إنشاء الإعلان العام وتشغيله أو إيقافه أو حذفه.", icon="badge-ad-fill", keywords="إعلان", order=53),
    _op("notifications", "communication", "الإشعارات", "enterprise_ops:notification_list", "الإشعارات الشخصية المقروءة وغير المقروءة والتنبيه الصوتي.", roles=(MANAGEMENT, TEACHER, PARENT), icon="bell-fill", keywords="إشعار تنبيه صوت", order=54),
    _op("internal-workflow", "communication", "الطلبات الإدارية الداخلية", "enterprise_ops:workflow_list", "سير داخلي باقٍ للعمليات التي تتطلب قرارًا مثل الخصومات والإغلاقات؛ وليس بديلًا للشكاوى.", icon="bezier2", keywords="موافقة خصم طلب داخلي", order=55),
    _op("permissions", "communication", "مصفوفة الصلاحيات", "enterprise_ops:permission_matrix", "إدارة صلاحيات الأدوار من الشاشة الرسمية الوحيدة.", icon="person-lock", keywords="صلاحية دور", order=56),

    _op("documents", "documents", "مركز الوثائق", "documents:document_list", "أرشيف الوثائق الرسمية؛ والإصدار يبدأ من ملف المستفيد.", icon="file-earmark-text-fill", keywords="وثيقة شهادة كتاب", order=60),
    _op("document-templates", "documents", "قوالب الوثائق", "documents:template_list", "إدارة القوالب والنصوص الافتراضية دون تغيير الوثائق السابقة.", icon="file-earmark-richtext-fill", keywords="قالب وثيقة", order=61),
    _op("document-settings", "documents", "إعدادات الوثائق", "documents:settings", "التوقيع والختم وبيانات المدير على الوثائق.", icon="pen-fill", keywords="توقيع ختم", order=62),
    _op("reports", "documents", "مركز التقارير", "enterprise_ops:report_center", "التقارير المتاحة وفق دور المستخدم وصلاحياته.", roles=(MANAGEMENT, TEACHER, PARENT), icon="file-earmark-bar-graph-fill", keywords="تقرير تصدير", order=63),
    _op("audit-log", "documents", "سجل العمليات", "enterprise_ops:audit_log", "تتبع العمليات؛ الإدارة ترى العام والمستخدم يرى عملياته المسموحة.", roles=(MANAGEMENT, TEACHER, PARENT), icon="shield-check", keywords="سجل تدقيق عمليات", order=64),

    _op("system-settings", "settings", "إعدادات النظام", "core:system_settings", "بيانات المدرسة ومراكز الإدارة الأساسية.", icon="gear-fill", keywords="إعدادات مدرسة شعار", order=70),
    _op("branches", "settings", "فروع المدرسة", "core:branch_list", "إدارة الفروع وتحديد الفرع الرئيسي.", icon="building-fill", keywords="فرع مدرسة", order=71),
    _op("integrity", "settings", "سلامة البيانات", "core:integrity_center", "كشف التعارضات وإصلاح الحالات الآمنة فقط.", icon="shield-fill-check", keywords="سلامة بيانات تعارض تكرار", order=72),
    _op("system-updates", "settings", "تحديثات النظام", "core:system_updates", "النسخ الاحتياطية ورفع التحديث والاستعادة وإعادة التحميل.", icon="arrow-repeat", keywords="تحديث نسخة احتياطية استعادة", order=73),
    _op("openemis", "settings", "تكامل OpenEMIS", "openemis:settings", "إعداد الربط واختبار الاتصال؛ النظام الوزاري تكامل وليس مصدر OPAL الداخلي.", icon="cloud-arrow-up-fill", keywords="وزارة OpenEMIS مزامنة", optional="openemis", order=74),
    _op("openemis-logs", "settings", "سجل مزامنة OpenEMIS", "openemis:logs", "متابعة عمليات الإرسال والاستيراد ونتائجها.", icon="clock-history", keywords="سجل مزامنة", optional="openemis", order=75),
    _op("development", "settings", "مركز التطوير", "development_center:dashboard", "إدارة خطة تطوير OPAL والإصدارات والأخطاء دون خلطها بالتشغيل المدرسي.", icon="tools", keywords="تطوير مهمة إصدار خطأ", optional="development", order=76),

    _op("teacher-home", "portal", "رئيسية المعلم", "teachers:portal_dashboard", "التكليفات ومنها يبدأ الحضور والعلامات والواجبات وقوائم الطلاب.", roles=(TEACHER,), icon="house-door-fill", keywords="معلم تكليف واجب حضور علامات", order=80),
    _op("teacher-timetable", "portal", "جدولي الدراسي", "teachers:portal_timetable", "جدول المعلم حسب اليوم والصف والمادة.", roles=(TEACHER,), icon="calendar3", keywords="جدول معلم", order=81),
    _op("parent-home", "portal", "رئيسية ولي الأمر", "parent_portal:dashboard", "ملخص الأبناء والتنبيهات والبيانات المهمة.", roles=(PARENT,), icon="house-heart-fill", keywords="ولي أمر أبناء", order=82),
    _op("parent-360", "portal", "ملف الأسرة 360", "parent_portal:parent_360", "ملخص الأسرة والأبناء والرسوم والحضور والعلامات.", roles=(PARENT,), icon="person-bounding-box", keywords="أسرة 360", order=83),
    _op("parent-children", "portal", "الأبناء", "parent_portal:children", "فتح بيانات كل ابن من البوابة.", roles=(PARENT,), icon="people", keywords="ابن أبناء", order=84),
    _op("parent-fees", "portal", "الرسوم والإيصالات", "parent_portal:fees", "رسوم الأبناء والدفعات والإيصالات.", roles=(PARENT,), icon="wallet2", keywords="رسوم إيصال", order=85),
    _op("parent-attendance", "portal", "حضور الأبناء", "parent_portal:attendance", "الحضور والغياب والتأخر لكل ابن.", roles=(PARENT,), icon="calendar-check", keywords="حضور ابن", order=86),
    _op("parent-marks", "portal", "علامات الأبناء", "parent_portal:marks", "العلامات المنشورة للأبناء.", roles=(PARENT,), icon="bar-chart-fill", keywords="علامات نتائج ابن", order=87),
    _op("parent-homework", "portal", "واجبات الأبناء", "parent_portal:homework", "الواجبات الفعالة ومواعيد التسليم.", roles=(PARENT,), icon="journal-text", keywords="واجب", order=88),
    _op("parent-timetable", "portal", "جداول الأبناء", "parent_portal:timetable", "الجدول حسب الابن واليوم والمادة.", roles=(PARENT,), icon="calendar3", keywords="جدول ابن", order=89),
    _op("parent-documents", "portal", "وثائق الأبناء", "parent_portal:documents", "الوثائق المتاحة للأسرة.", roles=(PARENT,), icon="file-earmark-text", keywords="وثيقة ابن", order=90),
    _op("parent-announcements", "portal", "إعلانات المدرسة", "parent_portal:announcements", "الإعلانات الفعالة الموجهة للمستخدمين.", roles=(PARENT,), icon="megaphone", keywords="إعلان مدرسة", order=91),
    _op("parent-account", "portal", "حساب ولي الأمر", "parent_portal:account", "بيانات الحساب وملف ولي الأمر.", roles=(PARENT,), icon="person-gear", keywords="حساب ولي أمر", order=92),
    _op("profile", "portal", "الملف الشخصي", "accounts:my_profile", "تحديث الاسم والصورة وبيانات المستخدم.", roles=(MANAGEMENT, TEACHER, PARENT, AUTHENTICATED), icon="person-circle", keywords="ملف شخصي صورة", order=99),
]


def user_role_key(user):
    if not getattr(user, "is_authenticated", False):
        return None
    from enterprise_ops.permissions import is_management

    if is_management(user):
        return MANAGEMENT
    try:
        if user.teacher_profile:
            return TEACHER
    except Exception:
        pass
    try:
        if user.family_account:
            return PARENT
    except Exception:
        pass
    return AUTHENTICATED


def _optional_enabled(code):
    if code == "openemis":
        return bool(settings.OPAL_ENABLE_OPENEMIS)
    if code == "development":
        return bool(settings.OPAL_ENABLE_DEVELOPMENT_CENTER)
    return True


def get_operations_for_user(user):
    role = user_role_key(user)
    if not role:
        return []
    resolved = []
    for definition in OPERATIONS:
        if role not in definition["roles"] and AUTHENTICATED not in definition["roles"]:
            continue
        if definition.get("optional") and not _optional_enabled(definition["optional"]):
            continue
        try:
            url = reverse(definition["route"])
        except NoReverseMatch:
            continue
        module = MODULES[definition["module"]]
        item = {
            **definition,
            "url": url,
            "module_label": module["label"],
            "module_icon": module["icon"],
            "module_color": module["color"],
            "search_text": " ".join([
                definition["label"], definition["description"], definition.get("keywords", ""), module["label"]
            ]).strip(),
        }
        resolved.append(item)
    return sorted(resolved, key=lambda item: (MODULES[item["module"]]["order"], item["order"], item["label"]))


def group_operations(operations):
    groups = []
    by_module = {}
    for operation in operations:
        code = operation["module"]
        if code not in by_module:
            meta = MODULES[code]
            group = {"code": code, **meta, "operations": []}
            by_module[code] = group
            groups.append(group)
        by_module[code]["operations"].append(operation)
    return sorted(groups, key=lambda group: group["order"])
