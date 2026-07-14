from django.db import models
from django.contrib.auth.models import User
from core.models import School, Branch


class Role(models.Model):
    ROLE_CODES = [
        ("super_admin", "مدير النظام"),
        ("school_owner", "مالك المدرسة"),
        ("principal", "مدير المدرسة"),
        ("accountant", "محاسب"),
        ("secretary", "سكرتير"),
        ("teacher", "معلم"),
        ("student", "طالب مدرسة"),
        ("parent", "ولي أمر"),
        ("academy_student", "طالب أكاديمية"),
        ("guest", "زائر"),
    ]

    code = models.CharField(max_length=50, choices=ROLE_CODES, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)

    full_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    photo = models.ImageField(upload_to="profiles/", blank=True, null=True)

    is_online_student = models.BooleanField(default=False)
    is_school_user = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name or self.user.username
