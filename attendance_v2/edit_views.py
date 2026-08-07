from django.contrib import messages
from django.shortcuts import redirect, render

from enterprise_ops.permissions import management_required
from .workflow import build_attendance_edit_state, save_attendance_edit


@management_required
def attendance_edit(request, pk):
    state = build_attendance_edit_state(request=request, pk=pk)
    record = state["record"]
    if state["blocked_reason"] == "closed_year":
        messages.error(request, "العام الدراسي مغلق ولا يمكن تعديل سجل الحضور التاريخي.")
        return redirect("attendance_v2:report")
    if state["blocked_reason"] == "locked":
        messages.error(request, "السجل مقفل ولا يمكن تعديله إلا بواسطة مدير النظام.")
        return redirect("attendance_v2:report")

    form = state["form"]
    if form.is_valid():
        save_attendance_edit(request=request, form=form)
        messages.success(request, "تم تحديث سجل الحضور.")
        return redirect("attendance_v2:report")
    return render(request, "attendance_v2/edit.html", {"record": record, "form": form})
