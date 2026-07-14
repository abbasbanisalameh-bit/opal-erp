from django.shortcuts import render

# Create your views here.

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Role, UserProfile
from .forms import RoleForm, UserProfileForm


def can_manage_roles(user):
    return user.is_superuser

@login_required
def my_profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث المعلومات الشخصية بنجاح.")
            return redirect("accounts:my_profile")
    else:
        form = UserProfileForm(instance=profile, user=request.user)
    return render(request, "accounts/my_profile.html", {"form": form})


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
    return render(request, "accounts/role_list.html", {"form": form, "items": Role.objects.all()})


@login_required
def role_update(request, pk):
    if not can_manage_roles(request.user):
        messages.error(request, "هذه الشاشة متاحة لمدير النظام فقط.")
        return redirect("accounts:my_profile")
    from django.shortcuts import get_object_or_404
    item = get_object_or_404(Role, pk=pk)
    form = RoleForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم تعديل الدور.")
        return redirect("accounts:role_list")
    return render(request, "accounts/role_form.html", {"form": form, "title": "تعديل الدور"})
