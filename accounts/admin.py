from django.contrib import admin
from .models import Role, UserProfile


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    search_fields = ("name", "code")
    list_filter = ("is_active",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "full_name", "role", "school", "branch", "phone", "is_school_user", "is_online_student")
    search_fields = ("user__username", "full_name", "phone")
    list_filter = ("role", "school", "branch", "is_school_user", "is_online_student")
