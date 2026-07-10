from django.shortcuts import render

# Create your views here.

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import School
from .forms import SchoolSettingsForm

def can_manage_system(user):
    return user.is_superuser or user.is_staff

@login_required
@user_passes_test(can_manage_system)
def system_settings(request):
    school = School.objects.filter(is_active=True).first() or School.objects.create(name="OPAL School")
    if request.method == "POST":
        form = SchoolSettingsForm(request.POST, request.FILES, instance=school)
        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث إعدادات النظام بنجاح.")
            return redirect("core:system_settings")
    else:
        form = SchoolSettingsForm(instance=school)
    return render(request, "core/system_settings.html", {"form": form, "school": school})
