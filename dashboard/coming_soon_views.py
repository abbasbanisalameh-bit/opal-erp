from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def coming_soon(request, service_name):
    return render(request, "dashboard/coming_soon.html", {
        "service_name": service_name.replace("-", " ")
    })
