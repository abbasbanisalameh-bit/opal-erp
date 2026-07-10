from django.contrib import admin
from .models import ParentProfile, Family, FamilyStudent
from .messages_models import ParentMessage
from .notifications import Notification


class FamilyStudentInline(admin.TabularInline):
    model = FamilyStudent
    extra = 0


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = ("guardian_name", "phone", "user", "created_at")
    search_fields = ("guardian_name", "phone", "user__username")
    inlines = [FamilyStudentInline]


admin.site.register(ParentProfile)
admin.site.register(ParentMessage)
admin.site.register(Notification)
