from django.db import models
from django.contrib.auth.models import User

class Family(models.Model):
    school = models.ForeignKey("core.School", on_delete=models.CASCADE, related_name="families", null=True, blank=True)
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="family_account")
    guardian_name = models.CharField("اسم ولي الأمر", max_length=200, blank=True)
    phone = models.CharField("الهاتف", max_length=50, blank=True)
    guardian_national_id = models.CharField("الرقم الوطني لولي الأمر", max_length=50, blank=True, db_index=True)
    family_code = models.CharField("رمز العائلة", max_length=50, blank=True, db_index=True)
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
