from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class ExamCycle(models.Model):
    """One management-created assessment cycle distributed to assignments."""

    STATUS_CHOICES = [
        ("open", "مفتوحة للمعلمين"),
        ("closed", "مغلقة"),
    ]
    EXAM_TYPES = [
        ("first", "الامتحان الأول"),
        ("second", "الامتحان الثاني"),
        ("third", "الامتحان الثالث"),
        ("final", "الامتحان النهائي"),
    ]

    academic_year = models.ForeignKey("core.AcademicYear", on_delete=models.PROTECT, related_name="exam_cycles")
    semester = models.ForeignKey("core.Semester", on_delete=models.PROTECT, related_name="exam_cycles")
    exam_type = models.CharField("نوع الدورة", max_length=30, choices=EXAM_TYPES)
    name = models.CharField("اسم الدورة", max_length=200, blank=True)
    status = models.CharField("الحالة", max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="opened_exam_cycles")
    opened_at = models.DateTimeField(default=timezone.now, editable=False)
    closed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField("ملاحظات", blank=True)

    class Meta:
        ordering = ["-academic_year__start_date", "semester__code", "exam_type"]
        constraints = [
            models.UniqueConstraint(fields=["academic_year", "semester", "exam_type"], name="uniq_exam_cycle_per_term_type"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.academic_year_id and self.academic_year.is_closed:
            errors["academic_year"] = "العام الدراسي مغلق ولا يقبل دورة امتحانية جديدة."
        if self.semester_id and self.semester.academic_year_id != self.academic_year_id:
            errors["semester"] = "الفصل الدراسي لا يتبع العام المحدد."
        if self.semester_id and self.semester.is_closed:
            errors["semester"] = "الفصل الدراسي مغلق أكاديميًا."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.name and self.exam_type:
            self.name = self.get_exam_type_display()
        self.full_clean(exclude=["opened_by"])
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.semester}"


class Exam(models.Model):
    EXAM_TYPES = [
        ("first", "الامتحان الأول"),
        ("second", "الامتحان الثاني"),
        ("third", "الامتحان الثالث"),
        ("final", "الامتحان النهائي"),
    ]
    MAX_MARKS = {
        "first": Decimal("20.00"),
        "second": Decimal("20.00"),
        "third": Decimal("20.00"),
        "final": Decimal("40.00"),
    }
    STATUS_CHOICES = [
        ("draft", "مسودة"),
        ("open", "مفتوح لإدخال العلامات"),
        ("submitted", "مرسل للإدارة للمراجعة"),
        ("approved", "معتمد"),
        ("published", "منشور"),
        ("closed", "مغلق"),
    ]

    name = models.CharField(max_length=200, blank=True)
    cycle = models.ForeignKey(
        ExamCycle,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="exams",
        verbose_name="الدورة الامتحانية العامة",
    )
    exam_type = models.CharField(max_length=30, choices=EXAM_TYPES)
    academic_year = models.ForeignKey("core.AcademicYear", on_delete=models.CASCADE, related_name="exams")
    semester = models.ForeignKey("core.Semester", on_delete=models.CASCADE, related_name="exams")
    grade = models.ForeignKey("academics.Grade", on_delete=models.CASCADE, related_name="exams")
    section = models.ForeignKey(
        "academics.Section",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="exams",
        verbose_name="الشعبة",
    )
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, related_name="exams")
    teacher_assignment = models.ForeignKey(
        "teachers.TeacherAssignment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="exams",
        verbose_name="تكليف المعلم",
    )
    max_mark = models.DecimalField(max_digits=6, decimal_places=2, default=20, editable=False)
    pass_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=60)
    # Retained for compatibility with existing analytics; it mirrors the official
    # share of the 100-mark semester total (20/20/20/40).
    weight = models.DecimalField("وزن الامتحان", max_digits=5, decimal_places=2, default=20, editable=False)
    exam_date = models.DateField(null=True, blank=True)
    marks_due_date = models.DateField(
        "الموعد النهائي لإدخال العلامات",
        null=True,
        blank=True,
        help_text="الموعد المعتمد لقياس إدخال العلامات ضمن الوقت في مؤشر TPI.",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    is_locked = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_exams",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_exams",
        verbose_name="أرسله للمراجعة",
    )
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ الإرسال للمراجعة")

    class Meta:
        ordering = ["academic_year", "semester__code", "grade__order", "section__name", "subject__name", "exam_type"]
        indexes = [models.Index(fields=["academic_year", "grade", "status"])]
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "semester", "section", "subject", "exam_type"],
                condition=models.Q(section__isnull=False),
                name="uniq_section_assessment_per_subject_term",
            ),
            models.UniqueConstraint(
                fields=["academic_year", "semester", "grade", "subject", "exam_type"],
                condition=models.Q(section__isnull=True),
                name="uniq_legacy_assessment_per_subject_term",
            ),
        ]

    @property
    def can_edit_marks(self):
        return not self.is_locked and self.status in {"draft", "open"}

    def clean(self):
        super().clean()
        errors = {}
        if self.academic_year_id and self.academic_year.is_closed:
            errors["academic_year"] = "العام الدراسي مغلق ولا يقبل تعديل الامتحانات."
        if self.exam_type not in self.MAX_MARKS:
            errors["exam_type"] = "نوع الامتحان غير معتمد."
        if self.pass_percentage is not None and not (Decimal("0") <= self.pass_percentage <= Decimal("100")):
            errors["pass_percentage"] = "نسبة النجاح يجب أن تكون بين 0 و100."
        if self.exam_date and self.marks_due_date and self.marks_due_date < self.exam_date:
            errors["marks_due_date"] = "الموعد النهائي لإدخال العلامات لا يمكن أن يسبق تاريخ الامتحان."
        if self.subject_id and self.subject.grade_id != self.grade_id:
            errors["subject"] = "المادة لا تتبع الصف المحدد."
        if self.subject_id and self.academic_year_id and self.subject.academic_year_id != self.academic_year_id:
            errors["subject"] = "المادة لا تتبع العام الدراسي المحدد."
        if self.section_id:
            if self.section.grade_id != self.grade_id:
                errors["section"] = "الشعبة لا تتبع الصف المحدد."
            if self.section.academic_year_id != self.academic_year_id:
                errors["section"] = "الشعبة لا تتبع العام الدراسي المحدد."
        if self.teacher_assignment_id:
            assignment = self.teacher_assignment
            if assignment.academic_year_id != self.academic_year_id:
                errors["teacher_assignment"] = "تكليف المعلم لا يتبع العام الدراسي المحدد."
            if assignment.section_id != self.section_id:
                errors["teacher_assignment"] = "تكليف المعلم لا يتبع الشعبة المحددة."
            if assignment.subject_id != self.subject_id:
                errors["teacher_assignment"] = "تكليف المعلم لا يتبع المادة المحددة."
        if self.semester_id and self.semester.academic_year_id != self.academic_year_id:
            errors["semester"] = "الفصل الدراسي لا يتبع العام المحدد."
        if self.grade_id and self.academic_year_id and self.grade.school_id != self.academic_year.school_id:
            errors["grade"] = "الصف لا يتبع مدرسة العام الدراسي."
        if self.cycle_id:
            if self.cycle.academic_year_id != self.academic_year_id:
                errors["cycle"] = "الدورة الامتحانية لا تتبع العام المحدد."
            elif self.cycle.semester_id != self.semester_id:
                errors["cycle"] = "الدورة الامتحانية لا تتبع الفصل المحدد."
            elif self.cycle.exam_type != self.exam_type:
                errors["cycle"] = "نوع الامتحان لا يطابق الدورة العامة."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        official_mark = self.MAX_MARKS.get(self.exam_type, Decimal("20.00"))
        self.max_mark = official_mark
        self.weight = official_mark
        if not self.name and self.exam_type and self.subject_id:
            suffix = f" - {self.section}" if self.section_id else ""
            self.name = f"{self.get_exam_type_display()} - {self.subject.name}{suffix}"
        self.full_clean(exclude=["approved_by"])
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name or self.get_exam_type_display()


class StudentMark(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="marks")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="marks")
    mark = models.DecimalField(max_digits=6, decimal_places=2)
    notes = models.TextField(blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entered_marks",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_marks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student__full_name"]
        constraints = [
            models.UniqueConstraint(fields=["exam", "student"], name="uniq_student_mark_per_exam"),
        ]

    def clean(self):
        super().clean()
        if self.exam_id and self.exam.academic_year.is_closed:
            raise ValidationError("العام الدراسي مغلق ولا يقبل تعديل العلامات.")
        if self.mark is None:
            return
        if self.mark < 0 or (self.exam_id and self.mark > self.exam.max_mark):
            maximum = self.exam.max_mark if self.exam_id else "الحد الأقصى"
            raise ValidationError({"mark": f"العلامة يجب أن تكون بين 0 و{maximum}."})
        if self.exam_id and self.pk and not self.exam.can_edit_marks:
            raise ValidationError("الامتحان معتمد أو مقفل ولا يمكن تعديل علاماته.")

    def save(self, *args, **kwargs):
        self.full_clean(exclude=["entered_by", "updated_by"])
        return super().save(*args, **kwargs)

    @property
    def percentage(self):
        if self.exam.max_mark:
            return round((float(self.mark) / float(self.exam.max_mark)) * 100, 2)
        return 0

    @property
    def is_passed(self):
        return Decimal(str(self.percentage)) >= self.exam.pass_percentage

    @property
    def weighted_percentage(self):
        # Because the official marks already sum to 100, the weighted result is
        # the raw mark itself (20/20/20/40).
        return Decimal(self.mark).quantize(Decimal("0.01"))

    @property
    def grade_letter(self):
        p = self.percentage
        if p >= 90:
            return "ممتاز"
        if p >= 80:
            return "جيد جداً"
        if p >= 70:
            return "جيد"
        if p >= 60:
            return "مقبول"
        return "راسب"

    def __str__(self):
        return f"{self.student.full_name} - {self.exam.name}"


class SemesterSubjectResult(models.Model):
    """Immutable-at-closure term snapshot built from the official marks."""

    semester = models.ForeignKey("core.Semester", on_delete=models.PROTECT, related_name="subject_results")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="semester_subject_results")
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, related_name="semester_results")
    score = models.DecimalField("نتيجة الفصل من 100", max_digits=6, decimal_places=2)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student__full_name", "subject__name"]
        constraints = [
            models.UniqueConstraint(fields=["semester", "student", "subject"], name="uniq_term_student_subject_result"),
        ]

    def clean(self):
        super().clean()
        if self.subject_id and self.semester_id and self.subject.academic_year_id != self.semester.academic_year_id:
            raise ValidationError({"subject": "المادة لا تتبع العام الدراسي للفصل المحدد."})

    def __str__(self):
        return f"{self.student} - {self.subject} - {self.semester}"


class AnnualSubjectResult(models.Model):
    academic_year = models.ForeignKey("core.AcademicYear", on_delete=models.PROTECT, related_name="annual_subject_results")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="annual_subject_results")
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, related_name="annual_results")
    first_semester_score = models.DecimalField(max_digits=6, decimal_places=2)
    second_semester_score = models.DecimalField(max_digits=6, decimal_places=2)
    annual_score = models.DecimalField("المعدل السنوي للمادة", max_digits=6, decimal_places=2)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student__full_name", "subject__name"]
        constraints = [
            models.UniqueConstraint(fields=["academic_year", "student", "subject"], name="uniq_year_student_subject_result"),
        ]

    def clean(self):
        super().clean()
        if self.subject_id and self.academic_year_id and self.subject.academic_year_id != self.academic_year_id:
            raise ValidationError({"subject": "المادة لا تتبع العام الدراسي المحدد."})


class AnnualStudentResult(models.Model):
    academic_year = models.ForeignKey("core.AcademicYear", on_delete=models.PROTECT, related_name="annual_student_results")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="annual_results")
    general_average = models.DecimalField("المعدل السنوي العام", max_digits=6, decimal_places=2)
    subject_count = models.PositiveSmallIntegerField(default=0)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student__full_name"]
        constraints = [
            models.UniqueConstraint(fields=["academic_year", "student"], name="uniq_year_student_summary"),
        ]
