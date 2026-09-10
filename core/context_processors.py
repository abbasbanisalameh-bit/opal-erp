from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.request_scope import request_academic_context, request_profile, request_school


def opal_identity(request):
    profile = request_profile(request)
    school = request_school(request)

    impersonator_id = request.session.get("opal_impersonator_user_id") if hasattr(request, "session") else None
    impersonator_name = request.session.get("opal_impersonator_username", "") if hasattr(request, "session") else ""
    if impersonator_id and not impersonator_name:
        User = get_user_model()
        impersonator_name = (
            User.objects.filter(pk=impersonator_id)
            .values_list("username", flat=True)
            .first()
            or "المدير العام"
        )

    transport_driver_impersonator_id = request.session.get("opal_transport_driver_impersonator_user_id") if hasattr(request, "session") else None
    transport_driver_impersonator_name = ""
    if transport_driver_impersonator_id:
        User = get_user_model()
        transport_driver_impersonator_name = (
            User.objects.filter(pk=transport_driver_impersonator_id)
            .values_list("username", flat=True)
            .first()
            or "الإدارة"
        )

    academic_context = request_academic_context(request, persist=True)
    return {
        "opal_school": school,
        "opal_profile": profile,
        "opal_openemis_enabled": settings.OPAL_ENABLE_OPENEMIS,
        "opal_development_center_enabled": settings.OPAL_ENABLE_DEVELOPMENT_CENTER,
        "opal_is_impersonating": bool(impersonator_id),
        "opal_impersonator_name": impersonator_name,
        "opal_is_transport_driver_impersonating": bool(transport_driver_impersonator_id),
        "opal_transport_driver_impersonator_name": transport_driver_impersonator_name,
        "opal_academic_year": academic_context.year if academic_context else None,
        "opal_semester": academic_context.semester if academic_context else None,
        "opal_semester_changed": academic_context.semester_changed if academic_context else False,
        "opal_time_zone": settings.TIME_ZONE,
        "opal_time_zone_label": "توقيت الأردن — إربد" if settings.TIME_ZONE == "Asia/Amman" else settings.TIME_ZONE,
        "opal_server_now": timezone.now(),
    }


def opal_operations(request):
    """Expose the role-aware canonical operation catalogue on every authenticated page."""
    if not getattr(getattr(request, "user", None), "is_authenticated", False):
        return {
            "opal_operation_catalog": [],
            "opal_operation_groups": [],
            "opal_current_operation": None,
            "opal_is_management": False,
            "opal_navigation_sections": [],
            "opal_module_subnav": None,
            "opal_module_registry": (),
            "opal_profile_url": "",
        }

    from enterprise_ops.permissions import is_management
    from django.urls import reverse

    from .workflow_catalog import (
        PARENT,
        get_entry_operations_for_user,
        get_operations_for_user,
        group_operations,
        management_subnavigation_for_user,
        navigation_sections_for_user,
        user_role_key,
    )
    from .information_architecture import gateway_for_route, gateways_for_user
    from .module_registry import enabled_module_registry

    operations = get_operations_for_user(request.user)
    entry_operations = get_entry_operations_for_user(request.user)
    resolver = getattr(request, "resolver_match", None)
    route_name = ""
    if resolver and resolver.url_name:
        route_name = f"{resolver.namespace}:{resolver.url_name}" if resolver.namespace else resolver.url_name
    current = next((item for item in operations if item["route"] == route_name), None)
    role = user_role_key(request.user)
    current_gateway = gateway_for_route(route_name, role=role)
    profile_url = reverse("parent_portal:account") if role == PARENT else reverse("accounts:my_profile")
    return {
        "opal_operation_catalog": entry_operations,
        "opal_operation_groups": group_operations(entry_operations),
        "opal_current_operation": current,
        "opal_is_management": is_management(request.user),
        "opal_information_gateways": gateways_for_user(request.user),
        "opal_current_gateway": current_gateway,
        "opal_navigation_sections": navigation_sections_for_user(
            request.user, route_name=route_name, query_params=request.GET,
        ),
        "opal_module_subnav": management_subnavigation_for_user(
            request.user, route_name=route_name, query_params=request.GET,
        ),
        "opal_module_registry": enabled_module_registry(),
        "opal_profile_url": profile_url,
    }
