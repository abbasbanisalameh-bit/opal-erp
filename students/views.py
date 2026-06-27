from django.shortcuts import redirect


def student_list(request):
    return redirect("academics:student_list")


def student_create(request):
    return redirect("academics:student_admission")


def student_update(request, pk=None, student_id=None):
    sid = pk or student_id
    if sid:
        return redirect("academics:student_update", student_id=sid)
    return redirect("academics:student_list")


def student_delete(request, pk=None, student_id=None):
    return redirect("academics:student_list")
