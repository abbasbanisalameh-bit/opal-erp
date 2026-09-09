"""Canonical OPAL operation catalogue.

Each business operation is assigned one canonical route and one approved visible
entry door. Detail and compatibility routes remain inside the owning workflow; they
never become a second navigation path or source of truth.
"""

from __future__ import annotations

from urllib.parse import parse_qs

from django.conf import settings
from django.urls import NoReverseMatch, reverse


MANAGEMENT = "management"
TEACHER = "teacher"
PARENT = "parent"
AUTHENTICATED = "authenticated"
DRIVER = "driver"


MODULES = {
    "transport": {"label": "المواصلات", "icon": "bus-front-fill", "color": "orange", "order": 25},
    "overview": {"label": "القيادة والمتابعة", "icon": "speedometer2", "color": "indigo", "order": 10},
    "students": {"label": "الطلاب وأولياء الأمور", "icon": "people-fill", "color": "blue", "order": 20},
    "academics": {"label": "الشؤون الأكاديمية", "icon": "mortarboard-fill", "color": "violet", "order": 30},
    "finance": {"label": "الرسوم المدرسية", "icon": "cash-stack", "color": "emerald", "order": 40},
    "communication": {"label": "التواصل والإشعارات", "icon": "bell-fill", "color": "amber", "order": 50},
    "documents": {"label": "الوثائق والتقارير", "icon": "file-earmark-text-fill", "color": "cyan", "order": 60},
    "settings": {"label": "الإعدادات والسلامة", "icon": "gear-fill", "color": "slate", "order": 70},
    "portal": {"label": "بوابتي", "icon": "person-workspace", "color": "rose", "order": 80},
}


def _op(
    key,
    module,
    label,
    route,
    description,
    *,
    roles=(MANAGEMENT,),
    icon="arrow-left-circle",
    keywords="",
    optional=None,
    query="",
    fragment="",
    superuser_only=False,
    staff_only=False,
    order=100,
):
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
        "query": query,
        "fragment": fragment,
        "superuser_only": superuser_only,
        "staff_only": staff_only,
        "order": order,
    }


# No object-specific route appears here. Actions such as edit/delete/issue are launched
# from their canonical list/detail screen so the user always starts in one predictable place.
OPERATIONS = [
    _op("transport-dashboard", "settings", "المواصلات", "transport:transport-dashboard", "مركز المواصلات الموحد للسائقين وأولياء الأمور والإدارة.", roles=(MANAGEMENT, DRIVER, PARENT), icon="bus-front-fill", keywords="مواصلات حافلة سائق رحلة موقع تتبع", order=25),
    _op("operations-center", "overview", "دليل العمليات الموحد", "core:operations_center", "الخريطة الرسمية لجميع إجراءات النظام ومسارات التكامل.", icon="signpost-split-fill", keywords="دليل خريطة بحث عمليات", order=1),
    _op("executive-dashboard", "overview", "لوحة الإدارة", "dashboard:home", "المؤشرات التنفيذية، المخاطر، رضا المستخدمين وآخر المستجدات.", icon="grid-1x2-fill", keywords="لوحة مدير مؤشرات رضا", order=2),
    _op("learning-platform", "overview", "منصة أوبال التعليمية", "learning_platform:manager_dashboard", "دخول مدير OPAL ERP إلى لوحة إدارة المنصة التعليمية دون إنشاء حساب تعليمي موازٍ.", icon="play-btn-fill", keywords="منصة تعلم دورات اشتراكات", order=3),

    _op("student-list", "students", "قائمة الطلاب", "students:student_list", "البحث عن الطالب وفتح بطاقة الطالب 360؛ وهي الملف الرسمي الموحد.", icon="people-fill", keywords="طلاب طالب 360 ملف", order=10),
    _op("student-registration", "students", "تسجيل طالب", "admissions:direct_registration", "المسار الوحيد لإنشاء طالب جديد وربطه بالقيد والرسوم وولي الأمر.", icon="person-plus-fill", keywords="تسجيل قبول طالب جديد", order=11),
    _op("student-register", "students", "سجل الطلبة", "admissions:admission_list", "سجل عمليات التسجيل والإيصالات المرتبطة بها.", icon="card-checklist", keywords="سجل التسجيل الطلبة", order=13),
    _op("families", "students", "ملفات أولياء الأمور", "parent_portal:family_management", "إدارة الأسرة والحساب والأبناء وكشف الأسرة من مكان واحد.", icon="person-vcard-fill", keywords="ولي أمر أسرة إخوة حساب", order=14),
    _op("student-lifecycle", "students", "حركة الطلاب الفردية", "academics:lifecycle_list", "النقل والانسحاب وإعادة القيد والحركات الفردية مع سجل تدقيق.", icon="arrow-repeat", keywords="نقل انسحاب إعادة قيد", order=15),
    _op("registration-settings", "settings", "إعدادات التسجيل", "core:system_settings", "إعدادات التسجيل والخصومات والسياسات داخل إعدادات النظام الموحدة.", icon="sliders", keywords="إعداد تسجيل خصم رسوم", query="section=registration", fragment="registration-settings", order=16),

    _op("academic-structure", "academics", "الهيكل الدراسي", "academics:academic_structure", "إدارة الصفوف والشعب ورسوم الصف في الشاشة الرسمية المترابطة.", icon="diagram-3-fill", keywords="صفوف شعب رسوم هيكل", order=20),
    _op("academic-years", "academics", "الأعوام الدراسية", "academics:academic_year_list", "إنشاء العام وتنشيطه وإغلاقه وفق دورة أكاديمية واحدة.", icon="calendar-range-fill", keywords="عام أكاديمي إغلاق", order=21),
    _op("annual-lifecycle", "academics", "مركز دورة العام", "academics:annual_lifecycle_center", "إغلاق الفصلين وتهيئة العام الجديد والترفيع والتخريج من بوابة واحدة.", icon="arrow-repeat", keywords="إغلاق فصل عام تهيئة ترفيع تخريج", order=22),
    _op("subjects", "academics", "المواد والخطة الدراسية", "academics:subject_list", "تعريف مواد الصف وحصصها الأسبوعية داخل العام الدراسي من مصدر واحد.", icon="book-half", keywords="مادة مواد خطة منهاج حصص أسبوعية", order=23),
    _op("teachers", "academics", "إدارة المعلمين", "teachers:dashboard", "ملفات المعلمين والحسابات والتكليفات التدريسية.", icon="person-badge-fill", keywords="معلم تكليف حساب", order=25),
    _op("timetable", "academics", "الجدول والمنشئ الذكي", "timetable:dashboard", "عرض الجدول الرسمي وتوليده من التكليفات مع منع التعارضات.", icon="calendar3", keywords="جدول حصة معلم صف مادة توليد ذكي", order=26),
    _op("schedule-settings", "academics", "إعدادات اليوم المدرسي", "timetable:schedule_settings", "الحصص والاستراحات والطابور والتنبيهات الزمنية.", icon="clock-fill", keywords="حصة وقت استراحة طابور", order=28),
    _op("teacher-absence", "academics", "غياب المعلمين والإشغال", "timetable:absence_center", "تسجيل غياب المعلم وتعيين البديل للحصص المتأثرة.", icon="person-x-fill", keywords="غياب معلم بديل إشغال", order=29),
    _op("attendance", "academics", "الغياب والمغادرة", "attendance_v2:dashboard", "المركز الرسمي الوحيد لتسجيل ومراجعة الغياب والمغادرة وإغلاق السجلات.", icon="calendar-check-fill", keywords="حضور غياب تأخر مغادرة", order=30),
    _op("exams", "academics", "الدورات الامتحانية", "exams:exam_cycle_center", "فتح الدورة مرة واحدة وتوزيعها آليًا على تكليفات المعلمين.", icon="file-earmark-check-fill", keywords="امتحان دورة اختبار توزيع", order=32),
    _op("marks", "academics", "العلامات والتحليل", "exams:exam_list", "السجل الرسمي للامتحانات والعلامات والتحليل المعياري.", icon="list-ol", keywords="علامة درجات نتائج تحليل", order=33),


    _op("finance-dashboard", "finance", "ملخص الرسوم", "accounting:dashboard", "التحصيل والمتبقي والمتأخر ضمن دورة الرسوم المدرسية فقط.", icon="speedometer", keywords="رسوم تحصيل متبقي", order=40),
    _op("fee-categories", "finance", "فئات الرسوم", "accounting:fee_category_list", "تعريف أنواع الرسوم وقيمها الأساسية من مكان واحد.", icon="tags-fill", keywords="فئة نوع رسوم", order=41),
    _op("student-invoices", "finance", "رسوم الطلاب", "accounting:invoice_list", "عرض الرسوم وإصدار رسم إضافي وإلغاء الرسم وفق الضوابط.", icon="file-earmark-spreadsheet-fill", keywords="فاتورة رسم طالب إصدار", order=42),
    _op("fee-payment", "finance", "تسديد الرسوم", "admissions:fee_payment_create", "المسار الوحيد لدفعة طالب أو دفعة عن جميع الإخوة والتوزيع التلقائي.", icon="cash-coin", keywords="دفع دفعة إيصال إخوة", order=43),
    _op("payment-archive", "finance", "أرشيف التسديد", "admissions:fee_payment_archive", "عرض الإيصالات والطباعة والحذف الآمن من الأرشيف الرسمي.", icon="archive-fill", keywords="أرشيف إيصال حذف آمن", order=44),
    _op("installments", "finance", "الأقساط", "accounting:installment_list", "متابعة أقساط الرسوم ومواعيدها وحالاتها.", icon="calendar2-week-fill", keywords="قسط أقساط موعد", order=45),
    _op("discounts", "finance", "طلبات الخصم", "accounting:discount_list", "طلبات الخصم وقراراتها المرتبطة بسير العمل الداخلي.", icon="percent", keywords="خصم طلب اعتماد", order=46),
    _op("teacher-payroll", "finance", "رواتب المعلمين والسلف", "teachers:payroll_center", "بطاقات الرواتب والسلف وخصومات الغياب المعتمدة وإنهاء الدورة بالإقرار.", icon="wallet2", keywords="راتب رواتب سلفة خصم", order=48),
    _op("finance-close", "finance", "إغلاق العام المالي", "accounting:financial_year_close", "إغلاق الرسوم وترحيل الأرصدة وفق العام الدراسي.", icon="arrow-left-right", keywords="إغلاق مالي ترحيل", order=49),

    _op("feedback", "communication", "الشكاوى والاقتراحات", "enterprise_ops:feedback_list", "استقبال الرسائل وتقييم جودة التدريس والخدمات الإلكترونية والرد عليها.", roles=(MANAGEMENT, TEACHER, PARENT), icon="chat-square-text-fill", keywords="شكوى اقتراح تقييم", order=51),
    _op("broadcasts", "communication", "التعاميم والتنبيهات", "enterprise_ops:broadcast_list", "إرسال تعميم للمعلمين أو أولياء الأمور أو الجميع وتنبيه معلم محدد.", icon="megaphone-fill", keywords="تعميم تنبيه", order=52),
    _op("announcements", "communication", "إدارة الإعلانات", "announcements:list", "إنشاء الإعلان العام وتشغيله أو إيقافه أو حذفه.", icon="badge-ad-fill", keywords="إعلان", order=53),
    _op("notifications", "communication", "الإشعارات", "enterprise_ops:notification_list", "الإشعارات الشخصية المقروءة وغير المقروءة والتنبيه الصوتي.", roles=(MANAGEMENT, TEACHER, PARENT), icon="bell-fill", keywords="إشعار تنبيه صوت", order=54),
    _op("internal-workflow", "communication", "الطلبات الإدارية الداخلية", "enterprise_ops:workflow_list", "سير داخلي باقٍ للعمليات التي تتطلب قرارًا مثل الخصومات والإغلاقات؛ وليس بديلًا للشكاوى.", icon="bezier2", keywords="موافقة خصم طلب داخلي", order=55),
    _op("permissions", "settings", "مصفوفة الصلاحيات", "enterprise_ops:permission_matrix", "إدارة صلاحيات الأدوار من الشاشة الرسمية الوحيدة.", icon="person-lock", keywords="صلاحية دور", superuser_only=True, order=56),

    _op("documents", "documents", "مركز الوثائق", "documents:document_list", "أرشيف الوثائق الرسمية؛ والإصدار يبدأ من ملف المستفيد.", icon="file-earmark-text-fill", keywords="وثيقة شهادة كتاب", order=60),
    _op("document-templates", "documents", "قوالب الوثائق", "documents:template_list", "إدارة القوالب والنصوص الافتراضية دون تغيير الوثائق السابقة.", icon="file-earmark-richtext-fill", keywords="قالب وثيقة", order=61),
    _op("document-settings", "documents", "إعدادات الوثائق", "documents:settings", "التوقيع والختم وبيانات المدير على الوثائق.", icon="pen-fill", keywords="توقيع ختم", order=62),
    _op("reports", "documents", "مركز التقارير", "enterprise_ops:report_center", "التقارير الإدارية الموحدة والتصدير حسب الصلاحيات المعتمدة.", icon="file-earmark-bar-graph-fill", keywords="تقرير تصدير", order=63),
    _op("audit-log", "documents", "سجل العمليات", "enterprise_ops:audit_log", "تتبع العمليات الإدارية وسجل التدقيق العام.", icon="shield-check", keywords="سجل تدقيق عمليات", order=64),

    _op("system-settings",  "settings", "إعدادات النظام", "core:system_settings", "بيانات المدرسة ومراكز الإدارة الأساسية.", icon="gear-fill", keywords="إعدادات مدرسة شعار", order=70),
    _op("branches", "settings", "فروع المدرسة", "core:branch_list", "إدارة الفروع وتحديد الفرع الرئيسي.", icon="building-fill", keywords="فرع مدرسة", order=71),
    _op("integrity", "settings", "سلامة البيانات", "core:integrity_center", "كشف التعارضات وإصلاح الحالات الآمنة فقط.", icon="shield-fill-check", keywords="سلامة بيانات تعارض تكرار", superuser_only=True, order=72),
    _op("system-updates", "settings", "تحديثات النظام", "core:system_updates", "النسخ الاحتياطية ورفع التحديث والاستعادة وإعادة التحميل.", icon="arrow-repeat", keywords="تحديث نسخة احتياطية استعادة", superuser_only=True, order=73),
    _op("openemis", "settings", "تكامل OpenEMIS", "openemis:settings", "إعداد الربط واختبار الاتصال؛ النظام الوزاري تكامل وليس مصدر OPAL الداخلي.", icon="cloud-arrow-up-fill", keywords="وزارة OpenEMIS مزامنة", optional="openemis", staff_only=True, order=74),
    _op("openemis-logs", "settings", "سجل مزامنة OpenEMIS", "openemis:logs", "متابعة عمليات الإرسال والاستيراد ونتائجها.", icon="clock-history", keywords="سجل مزامنة", optional="openemis", staff_only=True, order=75),
    _op("role-management", "settings", "إدارة الأدوار", "accounts:role_list", "تعريف الأدوار المعتمدة داخل النظام من شاشة مدير النظام.", icon="person-gear", keywords="دور أدوار صلاحيات", superuser_only=True, order=76),
    _op("development", "settings", "مركز التطوير", "development_center:dashboard", "إدارة خطة تطوير OPAL والإصدارات والأخطاء دون خلطها بالتشغيل المدرسي.", icon="tools", keywords="تطوير مهمة إصدار خطأ", optional="development", superuser_only=True, order=77),

    _op("teacher-home", "portal", "رئيسية المعلم", "teachers:portal_dashboard", "التكليفات ومنها يبدأ الحضور والعلامات والواجبات وقوائم الطلاب.", roles=(TEACHER,), icon="house-door-fill", keywords="معلم تكليف واجب حضور علامات", order=80),
    _op("teacher-subjects", "portal", "موادي", "teachers:portal_workspace", "المساحة الرسمية لمواد المعلم وتكليفاته.", roles=(TEACHER,), icon="journal-bookmark-fill", keywords="معلم مادة تكليف", query="mode=subjects", order=81),
    _op("teacher-students", "portal", "طلابي", "teachers:portal_workspace", "القائمة الرسمية لطلاب التكليف المحدد.", roles=(TEACHER,), icon="people-fill", keywords="طلاب معلم", query="mode=students", order=82),
    _op("teacher-marks", "portal", "امتحاناتي وعلاماتي", "teachers:portal_workspace", "المسار الموحد لفتح التكليف ثم إدخال العلامات الرسمية.", roles=(TEACHER,), icon="file-earmark-check-fill", keywords="امتحان علامات معلم", query="mode=marks", order=83),
    _op("teacher-homework", "portal", "واجباتي", "teachers:portal_workspace", "المسار الرسمي لاختيار التكليف ثم إدارة الواجبات.", roles=(TEACHER,), icon="journal-text", keywords="واجب معلم", query="mode=homework", order=84),
    _op("teacher-timetable", "portal", "جدولي الدراسي", "teachers:portal_timetable", "جدول المعلم حسب اليوم والصف والمادة.", roles=(TEACHER,), icon="calendar3", keywords="جدول معلم", order=85),
    _op("teacher-payroll-portal", "portal", "راتبي وسلفي", "teachers:portal_payroll", "بطاقات الرواتب والسلف والإقرار أو الاعتراض.", roles=(TEACHER,), icon="wallet2", keywords="راتب سلفة", order=86),
    _op("parent-home", "portal", "رئيسية ولي الأمر", "parent_portal:dashboard", "ملخص الأبناء والتنبيهات والبيانات المهمة.", roles=(PARENT,), icon="house-heart-fill", keywords="ولي أمر أبناء", order=82),
    _op("parent-children", "portal", "الأبناء", "parent_portal:children", "فتح بيانات كل ابن من البوابة.", roles=(PARENT,), icon="people", keywords="ابن أبناء", order=84),
    _op("parent-fees", "portal", "الرسوم والدفعات والإيصالات", "parent_portal:fees", "الشاشة المالية العائلية الموحدة للرسوم والمدفوع والمتبقي والإيصالات.", roles=(PARENT,), icon="wallet2", keywords="رسوم إيصال", order=85),
    _op("parent-attendance", "portal", "غياب ومغادرة الأبناء", "parent_portal:attendance", "السجل الموحد للغياب والمغادرة لكل ابن؛ وعدم وجود استثناء يعني حاضرًا.", roles=(PARENT,), icon="calendar-check", keywords="حضور ابن", order=86),
    _op("parent-marks", "portal", "علامات الأبناء", "parent_portal:marks", "العلامات المنشورة للأبناء.", roles=(PARENT,), icon="bar-chart-fill", keywords="علامات نتائج ابن", order=87),
    _op("parent-homework", "portal", "واجبات الأبناء", "parent_portal:homework", "الواجبات الفعالة ومواعيد التسليم.", roles=(PARENT,), icon="journal-text", keywords="واجب", order=88),
    _op("parent-timetable", "portal", "جداول الأبناء", "parent_portal:timetable", "الجدول حسب الابن واليوم والمادة.", roles=(PARENT,), icon="calendar3", keywords="جدول ابن", order=89),
    _op("parent-documents", "portal", "وثائق الأبناء", "parent_portal:documents", "الوثائق المتاحة للأسرة.", roles=(PARENT,), icon="file-earmark-text", keywords="وثيقة ابن", order=90),
    _op("parent-announcements", "portal", "إعلانات المدرسة", "parent_portal:announcements", "الإعلانات الفعالة الموجهة للمستخدمين.", roles=(PARENT,), icon="megaphone", keywords="إعلان مدرسة", order=91),
    _op("parent-teacher-evaluations", "portal", "تقييم معلمي أبنائي", "parent_portal:teacher_evaluations", "تقييم شهري للمعلمين الذين يدرسون الأبناء فقط.", roles=(PARENT,), icon="star-fill", keywords="تقييم معلم", order=92),
    _op("parent-account", "portal", "حساب ولي الأمر", "parent_portal:account", "بيانات الحساب وملف ولي الأمر وكلمة المرور من مكان واحد.", roles=(PARENT,), icon="person-gear", keywords="حساب ولي أمر", order=93),
    _op("profile", "portal", "الملف الشخصي", "accounts:my_profile", "تحديث الاسم والصورة وبيانات المستخدم.", roles=(MANAGEMENT, TEACHER, AUTHENTICATED), icon="person-circle", keywords="ملف شخصي صورة", order=99),
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
    try:
        if user.transport_driver:
            return DRIVER
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
        if definition.get("superuser_only") and not getattr(user, "is_superuser", False):
            continue
        if definition.get("staff_only") and not (
            getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
        ):
            continue
        try:
            url = reverse(definition["route"])
        except NoReverseMatch:
            continue
        if definition.get("query"):
            url = f"{url}?{definition['query']}"
        if definition.get("fragment"):
            url = f"{url}#{definition['fragment']}"
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


def get_entry_operations_for_user(user):
    """Return only the role's approved top-level entry doors.

    The complete operation catalogue remains available for diagnostics and
    ownership metadata, while navigation and global search expose only the
    gateway keys declared in ``SIDEBAR_SECTIONS``.
    """
    role = user_role_key(user)
    allowed = {
        key
        for section in SIDEBAR_SECTIONS.get(role, ())
        for key in section["items"]
    }
    return [item for item in get_operations_for_user(user) if item["key"] in allowed]


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


# The sidebar and the management sub-navigation deliberately refer to operation
# keys, not literal URLs.  ``OPERATIONS`` above remains the one source for each
# route, its label, icon, access scope and optional-module state.
SIDEBAR_SECTIONS = {
    # The sidebar exposes domain gateways only.  Object actions and business
    # operations begin inside the owning gateway, never from a second menu.
    MANAGEMENT: (
        {"label": "الرئيسية", "items": ("executive-dashboard",)},
        {"label": "المنصة التعليمية", "items": ("learning-platform",)},
        {"label": "البوابات الرئيسية", "items": (
            "student-list", "academic-structure", "finance-dashboard", "documents", "system-settings", "transport-dashboard",
        )},
    ),
    TEACHER: (
        {"label": "بوابة المعلم", "items": ("teacher-home",)},
        {"label": "التواصل", "items": ("feedback",)},
    ),
    PARENT: (
        {"label": "بوابة ولي الأمر", "items": ("parent-home", "transport-dashboard")},
    ),
    DRIVER: (
        {"label": "المواصلات", "items": ("transport-dashboard",)},
    ),
    AUTHENTICATED: (
        {"label": "الحساب", "items": ("profile",)},
    ),
}


MANAGEMENT_SUBNAV_GROUPS = (

    {
        "key": "students",
        "label": "إدارة الطلاب",
        "icon": "people-fill",
        "items": ("student-list", "student-registration", "student-register", "families", "student-lifecycle"),
        "prefixes": ("students:", "admissions:", "parent_portal:family_", "parent_portal:guardian_"),
        "excluded_prefixes": ("admissions:fee_payment", "admissions:student_financial_record"),
    },
    {
        "key": "academics",
        "label": "الشؤون الأكاديمية",
        "icon": "mortarboard-fill",
        "items": (
            "academic-structure", "academic-years", "annual-lifecycle", "subjects",
            "teachers", "timetable", "schedule-settings", "teacher-absence",
            "attendance", "exams", "marks",
        ),
        "prefixes": ("academics:", "attendance_v2:", "exams:", "timetable:", "teachers:"),
        "excluded_prefixes": ("teachers:payroll", "teachers:advance"),
    },
    {
        "key": "finance",
        "label": "الرسوم المدرسية",
        "icon": "cash-stack",
        "items": (
            "finance-dashboard", "fee-categories", "student-invoices", "fee-payment", "payment-archive",
            "installments", "discounts", "teacher-payroll", "finance-close",
        ),
        "prefixes": ("accounting:", "admissions:fee_payment", "admissions:student_financial_record", "teachers:payroll", "teachers:advance"),
        "excluded_prefixes": (),
    },
    {
        "key": "communication",
        "label": "التواصل والمتابعة",
        "icon": "bell-fill",
        "items": ("feedback", "broadcasts", "announcements", "notifications", "internal-workflow"),
        "prefixes": ("enterprise_ops:", "announcements:"),
        "excluded_prefixes": ("enterprise_ops:permission_matrix", "enterprise_ops:report_", "enterprise_ops:audit_"),
    },
    {
        "key": "documents",
        "label": "الوثائق والتقارير",
        "icon": "file-earmark-text-fill",
        "items": ("documents", "document-templates", "document-settings", "reports", "audit-log"),
        "prefixes": ("documents:", "enterprise_ops:report_", "enterprise_ops:audit_"),
        "excluded_prefixes": (),
    },
    {
        "key": "settings",
        "label": "إعدادات النظام",
        "icon": "gear-fill",
        "items": (

            "system-settings", "registration-settings", "branches", "permissions", "role-management",
            "integrity", "system-updates", "openemis", "openemis-logs", "development",
        ),
        "prefixes": ("core:", "openemis:", "development_center:", "accounts:role_", "enterprise_ops:permission_matrix"),
        "excluded_prefixes": ("core:operations_center",),
    },
)


# Compatibility/detail routes keep the corresponding gateway active without
# creating a second entry in the navigation.
ACTIVE_ROUTE_ALIASES = {
    "student-list": frozenset({"students:student_list", "students:student_360", "students:student_update", "students:student_confirm_delete"}),
    "student-registration": frozenset({"admissions:direct_registration"}),
    "student-register": frozenset({"admissions:admission_list", "admissions:admission_detail"}),
    "families": frozenset({
        "parent_portal:family_management", "parent_portal:family_detail", "parent_portal:family_update",
        "parent_portal:family_statement_print", "parent_portal:family_statement_csv",
        "parent_portal:family_account_create", "parent_portal:family_account_reset",
        "parent_portal:guardian_duplicates", "parent_portal:guardian_duplicate_merge",
    }),
    "academic-structure": frozenset({
        "academics:academic_structure", "academics:grade_list", "academics:grade_create", "academics:grade_update",
        "academics:grade_delete", "academics:section_list", "academics:section_create", "academics:section_update",
        "academics:section_delete",
    }),
    "academic-years": frozenset({
        "academics:academic_year_list", "academics:academic_year_create", "academics:academic_year_update",
        "academics:academic_year_close", "academics:academic_year_activate", "academics:semester_list",
        "academics:semester_create", "academics:semester_update", "academics:semester_delete",
    }),
    "timetable": frozenset({"timetable:dashboard", "timetable:entry_create", "timetable:entry_update", "timetable:entry_delete", "timetable:section_print", "timetable:teacher_print"}),
    "attendance": frozenset({"attendance_v2:dashboard", "attendance_v2:report", "attendance_v2:take_attendance", "attendance_v2:attendance_lock", "attendance_v2:register_action", "attendance_v2:attendance_edit"}),
    "marks": frozenset({"exams:exam_list"}),
    "documents": frozenset({"documents:document_list", "documents:document_detail", "documents:document_cancel", "documents:document_reissue", "documents:issue_student", "documents:issue_teacher", "documents:issue_guardian", "documents:issue_student_certificate"}),
    "teacher-home": frozenset({"teachers:portal_dashboard"}),
    "teacher-students": frozenset({"teachers:portal_workspace", "teachers:portal_students"}),
    "teacher-marks": frozenset({"teachers:portal_workspace", "teachers:portal_marks", "exams:exam_marks_bulk"}),
    "teacher-homework": frozenset({"teachers:portal_workspace", "teachers:portal_homework", "teachers:portal_homework_update", "teachers:portal_homework_delete"}),
    "parent-children": frozenset({"parent_portal:children", "parent_portal:student_detail", "parent_portal:student_personal_update", "parent_portal:parent_360"}),
    "parent-account": frozenset({"parent_portal:account", "accounts:my_profile"}),
}


def _operation_is_active(operation, route_name, query_params):
    """Return whether a menu operation owns the current request.

    Workspace operations share one route and are distinguished by ``mode``;
    detail and legacy routes use the explicit alias map above.
    """
    routes = ACTIVE_ROUTE_ALIASES.get(operation["key"], frozenset({operation["route"]}))
    if route_name not in routes:
        return False
    if operation.get("query") and route_name == operation["route"]:
        target_query = parse_qs(operation["query"])
        return all(
            str(query_params.get(key, "")) in values
            for key, values in target_query.items()
        )
    return True


def navigation_sections_for_user(user, *, route_name="", query_params=None):
    """Build the role-aware sidebar exclusively from canonical operations."""
    query_params = query_params or {}
    operations = {item["key"]: item for item in get_operations_for_user(user)}
    role = user_role_key(user)
    sections = []
    for definition in SIDEBAR_SECTIONS.get(role, ()):
        items = []
        for key in definition["items"]:
            operation = operations.get(key)
            if not operation:
                continue
            items.append({
                **operation,
                "active": _operation_is_active(operation, route_name, query_params),
            })
        if items:
            sections.append({
                "label": definition["label"],
                "items": items,
                "active": any(item["active"] for item in items),
            })
    return sections


def _route_matches_subnav_group(route_name, group):
    if not route_name:
        return False
    if any(route_name.startswith(prefix) for prefix in group.get("excluded_prefixes", ())):
        return False
    return any(route_name.startswith(prefix) for prefix in group["prefixes"])


def management_subnavigation_for_user(user, *, route_name="", query_params=None):
    """Do not expose a second management doorway inside operational pages.

    Management actions are launched from the owning domain gateway.  Keeping
    this compatibility function returning ``None`` prevents older templates
    from rendering a duplicate action row while preserving the public API.
    """
    del user, route_name, query_params
    return None
