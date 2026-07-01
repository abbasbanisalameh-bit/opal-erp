from django.db import models
from django.conf import settings


class Module(models.Model):
    STATUS_CHOICES = [
        ("planned", "🔴 مخطط لها"),
        ("development", "🟡 قيد التطوير"),
        ("completed", "🟢 مكتملة"),
    ]

    name = models.CharField("اسم الوحدة", max_length=120)
    category = models.CharField("التصنيف", max_length=100, blank=True)
    description = models.TextField("الوصف", blank=True)
    version = models.CharField("الإصدار المستهدف", max_length=30, blank=True)
    progress = models.PositiveSmallIntegerField("نسبة الإنجاز", default=0)
    priority = models.PositiveSmallIntegerField("الأولوية", default=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "name"]
        verbose_name = "وحدة تطوير"
        verbose_name_plural = "وحدات التطوير"

    def __str__(self):
        return self.name



class Sprint(models.Model):
    STATUS = [
        ("planned", "مخطط"),
        ("active", "نشط"),
        ("completed", "مكتمل"),
    ]

    title = models.CharField(max_length=200, verbose_name="اسم السبرنت")
    goal = models.TextField(blank=True, verbose_name="هدف السبرنت")
    start_date = models.DateField(null=True, blank=True, verbose_name="تاريخ البداية")
    end_date = models.DateField(null=True, blank=True, verbose_name="تاريخ النهاية")
    status = models.CharField(max_length=20, choices=STATUS, default="planned", verbose_name="الحالة")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date", "-id"]

    def __str__(self):
        return self.title


class Task(models.Model):
    STATUS = [
        ("todo","To Do"),
        ("doing","Doing"),
        ("review","Review"),
        ("done","Done"),
    ]

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="tasks")
    release = models.ForeignKey("Release", on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    sprint = models.ForeignKey("Sprint", on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks", verbose_name="السبرنت")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="todo")
    progress = models.PositiveSmallIntegerField(default=0)
    start_date = models.DateField(null=True, blank=True, verbose_name="تاريخ البداية")
    due_date = models.DateField(null=True, blank=True, verbose_name="تاريخ النهاية")
    depends_on = models.ManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="blocked_tasks",
        verbose_name="يعتمد على"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["status","title"]

    @property
    def is_blocked(self):
        return self.depends_on.exclude(status="done").exists()

    @property
    def has_dependencies(self):
        return self.depends_on.exists()

    def __str__(self):
        return self.title


class Release(models.Model):
    version = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    planned_date = models.DateField(null=True, blank=True)
    released = models.BooleanField(default=False)

    class Meta:
        ordering = ["-planned_date", "-id"]

    def __str__(self):
        return self.version


class Milestone(models.Model):
    title = models.CharField(max_length=200)
    version = models.ForeignKey(Release, on_delete=models.CASCADE)
    target_date = models.DateField(null=True, blank=True)
    progress = models.PositiveSmallIntegerField(default=0)
    completed = models.BooleanField(default=False)

    class Meta:
        ordering = ["target_date", "title"]

    def __str__(self):
        return self.title


class Idea(models.Model):
    STATUS = [
        ("new", "جديدة"),
        ("study", "قيد الدراسة"),
        ("approved", "معتمدة"),
        ("implemented", "تم تنفيذها"),
        ("rejected", "مرفوضة"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)
    priority = models.PositiveSmallIntegerField(default=3)
    status = models.CharField(max_length=20, choices=STATUS, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["priority", "-created_at"]

    def __str__(self):
        return self.title


class Decision(models.Model):
    STATUS = [
        ("proposed", "مقترح"),
        ("approved", "معتمد"),
        ("deprecated", "ملغي"),
    ]

    title = models.CharField(max_length=200)
    decision = models.TextField()
    reason = models.TextField(blank=True)
    impact = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="approved")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Bug(models.Model):
    SEVERITY = [
        ("low", "منخفض"),
        ("medium", "متوسط"),
        ("high", "مرتفع"),
        ("critical", "حرج"),
    ]

    STATUS = [
        ("open", "مفتوح"),
        ("in_progress", "قيد الإصلاح"),
        ("fixed", "تم الإصلاح"),
        ("closed", "مغلق"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="bugs")
    release = models.ForeignKey("Release", on_delete=models.SET_NULL, null=True, blank=True, related_name="release_bugs")
    severity = models.CharField(max_length=20, choices=SEVERITY, default="medium")
    status = models.CharField(max_length=20, choices=STATUS, default="open")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class ActivityLog(models.Model):
    ACTIONS = [
        ("create", "إنشاء"),
        ("update", "تعديل"),
        ("delete", "حذف"),
        ("status", "تغيير حالة"),
    ]

    module = models.ForeignKey(Module, on_delete=models.SET_NULL, null=True, blank=True, related_name="activity_logs")
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name="activity_logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="development_logs")
    action = models.CharField(max_length=20, choices=ACTIONS)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

class SprintDailySnapshot(models.Model):
    sprint = models.ForeignKey(Sprint, on_delete=models.CASCADE, related_name="snapshots")
    date = models.DateField()
    total_tasks = models.PositiveIntegerField(default=0)
    remaining_tasks = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("sprint", "date")
        ordering = ["date"]

    def __str__(self):
        return f"{self.sprint} - {self.date}"

class Notification(models.Model):
    LEVELS = [
        ("info", "معلومة"),
        ("warning", "تنبيه"),
        ("danger", "خطر"),
        ("success", "نجاح"),
    ]

    title = models.CharField(max_length=200)
    message = models.TextField()
    level = models.CharField(max_length=20, choices=LEVELS, default="info")
    is_read = models.BooleanField(default=False)
    url = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
