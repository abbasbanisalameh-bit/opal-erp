from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from enterprise_ops.permissions import management_required
from enterprise_ops.services import audit

from .forms import AnnouncementForm
from .models import Announcement


@management_required
def announcement_list(request):
    items = Announcement.objects.all()
    return render(request, "announcements/list.html", {"items": items})


@management_required
def announcement_create(request):
    form = AnnouncementForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        audit(request, "create", "announcements.Announcement", item.pk, f"إضافة إعلان: {item.title}")
        messages.success(request, "تمت إضافة الإعلان وسيظهر للمستخدمين ما دام فعالًا.")
        return redirect("announcements:list")
    return render(request, "announcements/form.html", {"form": form, "title": "إضافة إعلان"})


@management_required
def announcement_update(request, pk):
    item = get_object_or_404(Announcement, pk=pk)
    form = AnnouncementForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        audit(request, "update", "announcements.Announcement", item.pk, f"تعديل إعلان: {item.title}")
        messages.success(request, "تم تحديث الإعلان.")
        return redirect("announcements:list")
    return render(request, "announcements/form.html", {"form": form, "title": "تعديل الإعلان", "item": item})


@management_required
@require_POST
def announcement_toggle(request, pk):
    item = get_object_or_404(Announcement, pk=pk)
    item.is_active = not item.is_active
    item.save(update_fields=["is_active"])
    audit(request, "update", "announcements.Announcement", item.pk, f"تغيير حالة الإعلان: {item.title}")
    messages.success(request, "تم تشغيل الإعلان." if item.is_active else "تم إيقاف الإعلان.")
    return redirect("announcements:list")


@management_required
@require_POST
def announcement_delete(request, pk):
    item = get_object_or_404(Announcement, pk=pk)
    title = item.title
    item.delete()
    audit(request, "delete", "announcements.Announcement", pk, f"حذف إعلان: {title}")
    messages.success(request, "تم حذف الإعلان.")
    return redirect("announcements:list")
