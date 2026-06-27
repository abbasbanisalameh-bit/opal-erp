from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required

from .models import Attendance


@login_required
def attendance_edit(request, pk):
    record = get_object_or_404(Attendance, pk=pk)

    if request.method == "POST":
        record.status = request.POST.get("status")
        record.notes = request.POST.get("notes", "")
        record.save()
        return redirect("attendance_v2:report")

    return render(
        request,
        "attendance_v2/edit.html",
        {
            "record": record,
        },
    )
