from django import forms

from academics.models import Grade, Section, Subject
from core.models import AcademicYear, Semester
from teachers.models import TeacherAssignment

from .models import Exam


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = [
            "name",
            "exam_type",
            "academic_year",
            "semester",
            "grade",
            "section",
            "subject",
            "pass_percentage",
            "exam_date",
            "is_active",
        ]
        labels = {
            "name": "اسم الامتحان (اختياري)",
            "exam_type": "نوع الامتحان",
            "academic_year": "العام الدراسي",
            "semester": "الفصل الدراسي",
            "grade": "الصف",
            "section": "الشعبة",
            "subject": "المادة",
            "pass_percentage": "نسبة النجاح",
            "exam_date": "تاريخ الامتحان",
            "is_active": "فعال",
        }
        widgets = {
            "exam_date": forms.DateInput(attrs={"type": "date"}),
            "name": forms.TextInput(attrs={"placeholder": "يُنشأ تلقائيًا عند تركه فارغًا"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        data = self.data if self.is_bound else None
        year_id = (data.get("academic_year") if data else None) or getattr(self.instance, "academic_year_id", None)
        grade_id = (data.get("grade") if data else None) or getattr(self.instance, "grade_id", None)
        section_id = (data.get("section") if data else None) or getattr(self.instance, "section_id", None)

        years = AcademicYear.objects.filter(is_closed=False).order_by("-is_current", "-start_date")
        self.fields["academic_year"].queryset = years
        current_year = years.filter(is_current=True).first() or years.first()
        if not self.is_bound and not self.instance.pk and current_year:
            self.initial.setdefault("academic_year", current_year.pk)
            year_id = current_year.pk

        semesters = Semester.objects.filter(academic_year__is_closed=False).select_related("academic_year")
        if year_id:
            semesters = semesters.filter(academic_year_id=year_id)
        self.fields["semester"].queryset = semesters.order_by("academic_year__start_date", "code")
        if not self.is_bound and not self.instance.pk and current_year:
            current_semester = current_year.semesters.filter(is_current=True).first() or current_year.semesters.order_by("code").first()
            if current_semester:
                self.initial.setdefault("semester", current_semester.pk)

        grades = Grade.objects.filter(is_active=True)
        if year_id:
            grades = grades.filter(school_id=AcademicYear.objects.filter(pk=year_id).values_list("school_id", flat=True).first())
        self.fields["grade"].queryset = grades.order_by("order", "name")

        sections = Section.objects.filter(is_active=True).select_related("grade", "academic_year")
        if year_id:
            sections = sections.filter(academic_year_id=year_id)
        if grade_id:
            sections = sections.filter(grade_id=grade_id)
        self.fields["section"].queryset = sections.order_by("grade__order", "name")

        subjects = Subject.objects.filter(is_active=True).select_related("grade")
        if grade_id:
            subjects = subjects.filter(grade_id=grade_id)
        self.fields["subject"].queryset = subjects.order_by("name")

        for name, field in self.fields.items():
            css = "form-check-input" if getattr(field.widget, "input_type", "") == "checkbox" else "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs.setdefault("class", css)
            if name in {"academic_year", "semester", "grade", "section", "subject"}:
                field.widget.attrs["data-exam-scope-field"] = name

        self.fields["section"].required = True
        self.fields["subject"].required = True
        self.fields["academic_year"].help_text = "يُحدد العام الحالي تلقائيًا ويمكن تغييره."
        self.fields["semester"].help_text = "يُحدد الفصل الحالي تلقائيًا ويمكن تغييره."
        self.fields["section"].help_text = "تحديد الشعبة ضروري لضبط قائمة الطلبة والمعلم المكلف."

    def clean(self):
        cleaned = super().clean()
        year = cleaned.get("academic_year")
        semester = cleaned.get("semester")
        grade = cleaned.get("grade")
        section = cleaned.get("section")
        subject = cleaned.get("subject")
        if year and semester and semester.academic_year_id != year.pk:
            self.add_error("semester", "الفصل الدراسي لا يتبع العام المحدد.")
        if grade and section and section.grade_id != grade.pk:
            self.add_error("section", "الشعبة لا تتبع الصف المحدد.")
        if year and section and section.academic_year_id != year.pk:
            self.add_error("section", "الشعبة لا تتبع العام المحدد.")
        if grade and subject and subject.grade_id != grade.pk:
            self.add_error("subject", "المادة لا تتبع الصف المحدد.")
        if year and section and subject:
            assignments = TeacherAssignment.objects.filter(
                academic_year=year,
                section=section,
                subject=subject,
                is_active=True,
                teacher__is_active=True,
            ).select_related("teacher")
            count = assignments.count()
            if count == 0:
                self.add_error("subject", "لا يوجد معلم مكلف بهذه المادة في الشعبة المحددة.")
            elif count > 1:
                self.add_error("subject", "يوجد أكثر من تكليف فعال للمادة والشعبة. صحح التكليفات أولًا.")
            else:
                self._resolved_assignment = assignments.first()
        return cleaned

    def save(self, commit=True):
        exam = super().save(commit=False)
        exam.teacher_assignment = getattr(self, "_resolved_assignment", None)
        if commit:
            exam.save()
            self.save_m2m()
        return exam
