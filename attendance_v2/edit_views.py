from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render

from enterprise_ops.services import audit
from .forms import AttendanceEditForm
from .models import Attendance
from .services import notify_parent_for_attendance


@staff_member_required
def attendance_edit(request, pk):
    record = get_object_or_404(Attendance, pk=pk)
    if record.academic_year_id and record.academic_year.is_closed:
        messages.error(request, "العام الدراسي مغلق ولا يمكن تعديل سجل الحضور التاريخي.")
        return redirect("attendance_v2:report")
    if record.is_locked and not request.user.is_superuser:
        messages.error(request, "السجل مقفل ولا يمكن تعديله إلا بواسطة مدير النظام.")
        return redirect("attendance_v2:report")
    form = AttendanceEditForm(request.POST or None, instance=record)
    if form.is_valid():
        record = form.save(commit=False)
        record.updated_by = request.user
        record.save()
        notify_parent_for_attendance(record)
        audit(request, "update", "attendance_v2.Attendance", record.pk, f"تعديل حضور {record.student.full_name} بتاريخ {record.date}")
        messages.success(request, "تم تحديث سجل الحضور.")
        return redirect("attendance_v2:report")
    return render(request, "attendance_v2/edit.html", {"record": record, "form": form})
