from django.db import models
from core.models import School, Branch, AcademicYear


class Grade(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="grades")
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]
        unique_together = ("school", "name")

    def __str__(self):
        return self.name


class Section(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="sections")
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["grade__order", "name"]
        unique_together = ("branch", "grade", "name")

    def __str__(self):
        return f"{self.grade.name} - {self.name}"


class Subject(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="subjects")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("school", "name")

    def __str__(self):
        return self.name


class StudentRecord(models.Model):
    GENDER_CHOICES = [
        ("male", "ذكر"),
        ("female", "أنثى"),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="student_records")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)

    student_number = models.CharField(max_length=50, unique=True)
    national_id = models.CharField(max_length=50, blank=True)
    full_name = models.CharField(max_length=200)
    father_name = models.CharField(max_length=200, blank=True)
    mother_name = models.CharField(max_length=200, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    blood_type = models.CharField(max_length=10, blank=True)

    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    medical_notes = models.TextField(blank=True)
    photo = models.ImageField(upload_to="students/", blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Enrollment(models.Model):
    STATUS_CHOICES = [
        ("active", "نشط"),
        ("transferred", "منقول"),
        ("withdrawn", "منسحب"),
        ("graduated", "متخرج"),
    ]

    student = models.ForeignKey(StudentRecord, on_delete=models.CASCADE, related_name="enrollments")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="enrollments")
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    joined_at = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ("student", "academic_year")
        ordering = ["-academic_year__start_date", "student__full_name"]

    def __str__(self):
        return f"{self.student.full_name} - {self.academic_year.name}"


class Guardian(models.Model):
    RELATION_CHOICES = [
        ("father", "الأب"),
        ("mother", "الأم"),
        ("guardian", "وصي"),
        ("other", "آخر"),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="guardians")
    full_name = models.CharField(max_length=200)
    relation = models.CharField(max_length=20, choices=RELATION_CHOICES)
    national_id = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=30)
    secondary_phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    job_title = models.CharField(max_length=150, blank=True)
    address = models.TextField(blank=True)
    medical_notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class StudentGuardian(models.Model):
    student = models.ForeignKey(StudentRecord, on_delete=models.CASCADE, related_name="guardians")
    guardian = models.ForeignKey(Guardian, on_delete=models.CASCADE, related_name="students")
    is_primary = models.BooleanField(default=False)
    can_receive_notifications = models.BooleanField(default=True)
    can_pickup_student = models.BooleanField(default=True)

    class Meta:
        unique_together = ("student", "guardian")

    def __str__(self):
        return f"{self.student.full_name} - {self.guardian.full_name}"


class StudentDocument(models.Model):
    DOCUMENT_TYPES = [
        ("birth_certificate", "شهادة ميلاد"),
        ("national_id", "هوية / جواز سفر"),
        ("photo", "صورة شخصية"),
        ("medical", "ملف طبي"),
        ("certificate", "شهادة مدرسية"),
        ("other", "أخرى"),
    ]

    student = models.ForeignKey(StudentRecord, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to="student_documents/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.full_name} - {self.title}"
