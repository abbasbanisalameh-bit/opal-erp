from django.db import models
from django.contrib.auth.models import User

class ParentProfile(models.Model):
    user=models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    student=models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="parents"
    )

    phone=models.CharField(
        max_length=30,
        blank=True
    )

    def __str__(self):
        return self.user.username



class Family(models.Model):
    school = models.ForeignKey("core.School", on_delete=models.CASCADE, related_name="families", null=True, blank=True)
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="family_account")
    guardian_name = models.CharField("اسم ولي الأمر", max_length=200, blank=True)
    phone = models.CharField("الهاتف", max_length=50, blank=True)
    national_id = models.CharField("الرقم الوطني لولي الأمر", max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "أسرة"
        verbose_name_plural = "الأسر"

    def __str__(self):
        return self.guardian_name or self.phone or f"Family #{self.pk}"


class FamilyStudent(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="children")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="family_links")
    relation = models.CharField("صلة القرابة", max_length=50, default="ولي أمر")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("family", "student"),)
        verbose_name = "طالب ضمن أسرة"
        verbose_name_plural = "طلاب الأسر"

    def __str__(self):
        return f"{self.family} - {self.student}"
