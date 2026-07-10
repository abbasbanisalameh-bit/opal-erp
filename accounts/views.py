from django.shortcuts import render

# Create your views here.

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import UserProfile
from .forms import UserProfileForm

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
