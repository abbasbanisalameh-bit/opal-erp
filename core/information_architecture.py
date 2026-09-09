"""OPAL canonical information architecture.

This module is the UI-level companion to ``workflow_catalog``.  It defines one
full-detail gateway for each information domain and role. Dashboards and cards
may show lightweight summaries, but must link to these gateways rather than
re-implementing a second full view.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.urls import NoReverseMatch, reverse

from .workflow_catalog import DRIVER, MANAGEMENT, PARENT, TEACHER, user_role_key


@dataclass(frozen=True)
class InformationGateway:
    key: str
    label: str
    role: str
    route: str
    description: str
    summary_only_elsewhere: bool = True
    query: str = ""

    def resolve_url(self) -> str:
        try:
            url = reverse(self.route)
        except NoReverseMatch:
            return ""
        return f"{url}?{self.query}" if self.query else url


GATEWAYS: tuple[InformationGateway, ...] = (
    # Management
    InformationGateway("management.students", "بطاقة الطالب 360", MANAGEMENT, "students:student_list", "المرجع الرسمي لبيانات الطالب وقيده وملفه الشامل."),
    InformationGateway("management.attendance", "الغياب والمغادرة", MANAGEMENT, "attendance_v2:dashboard", "المركز الإداري الوحيد لمراجعة الغياب والمغادرة وإغلاق السجلات."),
    InformationGateway("management.student_finance", "رسوم الطلاب والمتبقي", MANAGEMENT, "accounting:invoice_list", "المرجع الرسمي لرسوم الطالب والمدفوع والمتبقي."),
    InformationGateway("management.payments", "تسديد الرسوم", MANAGEMENT, "admissions:fee_payment_create", "البوابة الوحيدة لتسجيل دفعة طالب أو دفعة عن جميع الإخوة."),
    InformationGateway("management.receipts", "أرشيف الإيصالات", MANAGEMENT, "admissions:fee_payment_archive", "المكان الوحيد للبحث عن الإيصالات وعرضها وطباعتها."),
    InformationGateway("management.marks", "العلامات والتحليل", MANAGEMENT, "exams:exam_list", "المرجع الإداري الموحد للامتحانات والعلامات والتحليل المعياري."),
    InformationGateway("management.teachers", "إدارة المعلمين", MANAGEMENT, "teachers:dashboard", "المرجع الرسمي للمعلمين والتكليفات."),
    InformationGateway("management.payroll", "الرواتب والسلف", MANAGEMENT, "teachers:payroll_center", "المركز الرسمي للرواتب والسلف والخصومات."),
    InformationGateway("management.notifications", "التواصل والمتابعة", MANAGEMENT, "dashboard:home", "ملخص التواصل مدمج في لوحة الإدارة، وتفتح البطاقات صفحات العمل التفصيلية مباشرة."),
    InformationGateway("management.transport", "المواصلات", MANAGEMENT, "transport:transport-dashboard", "مركز المواصلات الرسمي للرحلات والسائقين والتعيينات والتتبع."),

    # Teacher
    InformationGateway("teacher.home", "رئيسية المعلم", TEACHER, "teachers:portal_dashboard", "ملخص خفيف للتكليفات والتنبيهات."),
    InformationGateway("teacher.subjects", "موادي", TEACHER, "teachers:portal_workspace", "المساحة الرسمية لمواد المعلم.", query="mode=subjects"),
    InformationGateway("teacher.students", "طلابي", TEACHER, "teachers:portal_workspace", "القائمة الرسمية للطلاب حسب العام والصف والشعبة.", query="mode=students"),
    InformationGateway("teacher.exams", "امتحاناتي وعلاماتي", TEACHER, "teachers:portal_workspace", "المسار الموحد للامتحانات وإدخال العلامات.", query="mode=marks"),
    InformationGateway("teacher.homework", "واجباتي", TEACHER, "teachers:portal_workspace", "المركز الرسمي للواجبات.", query="mode=homework"),
    InformationGateway("teacher.timetable", "جدولي", TEACHER, "teachers:portal_timetable", "المرجع الوحيد لجدول المعلم."),
    InformationGateway("teacher.payroll", "راتبي وسلفي", TEACHER, "teachers:portal_payroll", "المرجع الوحيد للراتب والسلف والاعتراضات."),
    InformationGateway("teacher.notifications", "الإشعارات", TEACHER, "enterprise_ops:notification_list", "سجل الإشعارات، مع فتح الحدث المحدد مباشرة."),

    # Parent
    InformationGateway("parent.children", "أبنائي", PARENT, "parent_portal:children", "المرجع الرئيسي للأبناء."),
    InformationGateway("parent.finance", "الرسوم والدفعات والإيصالات", PARENT, "parent_portal:fees", "الشاشة المالية العائلية الموحدة."),
    InformationGateway("parent.attendance", "غياب ومغادرة أبنائي", PARENT, "parent_portal:attendance", "السجل الموحد للاستثناءات اليومية لكل ابن."),
    InformationGateway("parent.marks", "علامات أبنائي", PARENT, "parent_portal:marks", "المرجع الوحيد للنتائج المنشورة."),
    InformationGateway("parent.homework", "واجبات أبنائي", PARENT, "parent_portal:homework", "المركز الوحيد للواجبات."),
    InformationGateway("parent.timetable", "جداول الأبناء", PARENT, "parent_portal:timetable", "المكان الوحيد للجداول."),
    InformationGateway("parent.documents", "وثائق الأبناء", PARENT, "parent_portal:documents", "المكان الوحيد للوثائق المتاحة للأسرة."),
    InformationGateway("parent.notifications", "الإشعارات", PARENT, "enterprise_ops:notification_list", "سجل الإشعارات مع روابط مباشرة للأحداث."),
    InformationGateway("parent.transport", "مواصلات الأبناء", PARENT, "transport:transport-dashboard", "تحديد موقع الأسرة ومتابعة الرحلة النشطة للأبناء فقط."),
    InformationGateway("driver.transport", "مواصلات السائق", DRIVER, "transport:transport-dashboard", "رحلات السائق الحالية والتشغيل والتتبع."),
)


# Compatibility routes stay available, but they are not independent menu entries.
# The value is the canonical gateway key, not another URL implementation.
COMPATIBILITY_ROUTE_GATEWAYS = {
    "enterprise_ops:dashboard": "management.notifications",
    "parent_portal:parent_360": "parent.children",
    "parent_portal:student_detail": "parent.children",
    "teachers:portal_students": "teacher.students",
    "teachers:portal_marks": "teacher.exams",
    "teachers:portal_homework": "teacher.homework",
    "attendance_v2:report": "management.attendance",
    "accounting:dashboard": "management.student_finance",
}


def gateways_for_role(role: str) -> list[dict]:
    return [
        {"key": item.key, "label": item.label, "route": item.route, "url": item.resolve_url(), "description": item.description}
        for item in GATEWAYS
        if item.role == role and item.resolve_url()
    ]


def gateways_for_user(user) -> list[dict]:
    return gateways_for_role(user_role_key(user))


def gateway_by_key(key: str) -> InformationGateway | None:
    return next((item for item in GATEWAYS if item.key == key), None)


def gateway_for_route(route_name: str, role: str | None = None) -> InformationGateway | None:
    direct = next((item for item in GATEWAYS if item.route == route_name and (role is None or item.role == role)), None)
    if direct:
        return direct
    key = COMPATIBILITY_ROUTE_GATEWAYS.get(route_name)
    item = gateway_by_key(key) if key else None
    return item if item and (role is None or item.role == role) else None


def audit_gateway_definitions(items: Iterable[InformationGateway] = GATEWAYS) -> list[str]:
    """Return structural errors without touching operational data."""
    errors: list[str] = []
    seen_keys: set[str] = set()
    seen_role_routes: set[tuple[str, str, str]] = set()
    for item in items:
        if item.key in seen_keys:
            errors.append(f"duplicate gateway key: {item.key}")
        seen_keys.add(item.key)
        signature = (item.role, item.route, item.query)
        if signature in seen_role_routes:
            errors.append(f"duplicate gateway route for role: {item.role} {item.route}?{item.query}")
        seen_role_routes.add(signature)
        if not item.resolve_url():
            errors.append(f"unresolved gateway route: {item.key} -> {item.route}")
    for route, key in COMPATIBILITY_ROUTE_GATEWAYS.items():
        if gateway_by_key(key) is None:
            errors.append(f"compatibility route points to missing gateway: {route} -> {key}")
    return errors
