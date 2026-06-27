from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import AdmissionApplication


@login_required
def admission_list(request):
    applications = AdmissionApplication.objects.all()

    return render(request, "admissions/admission_list.html", {
        "applications": applications,
    })
