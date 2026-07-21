from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import RoleForm, UserProfileForm
from .models import Role, UserProfile
from .workflow import can_manage_roles, impersonation_target_kind, role_list_queryset


IMPERSONATOR_SESSION_KEY = "opal_impersonator_user_id"
IMPERSONATED_SESSION_KEY = "opal_impersonated_user_id"
DEFAULT_AUTH_BACKEND = "django.contrib.auth.backends.ModelBackend"


def _style_password_form(form):
    for field in form.fields.values():
        field.widget.attrs.setdefault("class", "form-control")


@login_required
def my_profile(request):
    profile, _created = UserProfile.objects.get_or_create(user=request.user)
    action = request.POST.get("action", "profile") if request.method == "POST" else ""

    profile_form = UserProfileForm(
        request.POST if action == "profile" else None,
        request.FILES if action == "profile" else None,
        instance=profile,
        user=request.user,
        prefix="profile",
    )
    password_form = PasswordChangeForm(
        request.user,
        request.POST if action == "password" else None,
        prefix="password",
    )
    _style_password_form(password_form)

    if request.method == "POST" and action == "profile" and profile_form.is_valid():
        profile_form.save()
        messages.success(request, "تم تحديث المعلومات الشخصية والصورة بنجاح.")
        return redirect("accounts:my_profile")

    if request.method == "POST" and action == "password" and password_form.is_valid():
        user = password_form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "تم تغيير كلمة المرور بنجاح.")
        return redirect("accounts:my_profile")

    return render(
        request,
        "accounts/my_profile.html",
        {
            "form": profile_form,
            "profile_form": profile_form,
            "password_form": password_form,
        },
    )



@login_required
@require_POST
def impersonate_user(request, user_id):
    if not request.user.is_superuser:
        raise PermissionDenied("هذه العملية متاحة للمدير العام فقط.")
    if request.session.get(IMPERSONATOR_SESSION_KEY):
        messages.error(request, "أنت داخل حساب مستخدم آخر بالفعل. ارجع إلى حساب المدير أولًا.")
        return redirect("dashboard:home")

    target = get_object_or_404(User, pk=user_id, is_active=True)
    target_kind = impersonation_target_kind(target)
    if not target_kind or target.is_staff or target.is_superuser:
        raise PermissionDenied("يسمح بالدخول فقط إلى حساب معلم أو ولي أمر فعال.")

    original_user_id = request.user.pk
    original_username = request.user.get_username()
    backend = request.session.get("_auth_user_backend", DEFAULT_AUTH_BACKEND)
    auth_login(request, target, backend=backend)
    request.session[IMPERSONATOR_SESSION_KEY] = original_user_id
    request.session[IMPERSONATED_SESSION_KEY] = target.pk
    request.session["opal_impersonator_username"] = original_username

    messages.info(request, f"أنت الآن داخل حساب {target.get_username()}. استخدم زر العودة للرجوع إلى حساب المدير.")
    if target_kind == "teacher":
        return redirect("teachers:portal_dashboard")
    return redirect("parent_portal:dashboard")


@login_required
@require_POST
def stop_impersonation(request):
    original_user_id = request.session.get(IMPERSONATOR_SESSION_KEY)
    if not original_user_id:
        messages.info(request, "لا توجد جلسة دخول بحساب مستخدم آخر.")
        return redirect("dashboard:home")

    original_user = get_object_or_404(
        User,
        pk=original_user_id,
        is_active=True,
        is_superuser=True,
    )
    backend = request.session.get("_auth_user_backend", DEFAULT_AUTH_BACKEND)
    auth_login(request, original_user, backend=backend)
    request.session.pop(IMPERSONATOR_SESSION_KEY, None)
    request.session.pop(IMPERSONATED_SESSION_KEY, None)
    request.session.pop("opal_impersonator_username", None)
    messages.success(request, "تم الرجوع إلى حساب المدير العام.")
    return redirect("dashboard:home")


@login_required
def role_list(request):
    if not can_manage_roles(request.user):
        messages.error(request, "هذه الشاشة متاحة لمدير النظام فقط.")
        return redirect("accounts:my_profile")
    form = RoleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تمت إضافة الدور من واجهة OPAL.")
        return redirect("accounts:role_list")
    return render(request, "accounts/role_list.html", {"form": form, "items": role_list_queryset()})


@login_required
def role_update(request, pk):
    if not can_manage_roles(request.user):
        messages.error(request, "هذه الشاشة متاحة لمدير النظام فقط.")
        return redirect("accounts:my_profile")
    item = get_object_or_404(Role, pk=pk)
    form = RoleForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم تعديل الدور.")
        return redirect("accounts:role_list")
    return render(request, "accounts/role_form.html", {"form": form, "title": "تعديل الدور"})
