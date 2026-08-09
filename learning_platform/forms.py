
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from .card_codes import generate_unique_card_code
from .models import (
    LearningAccount,
    LearningAIDraft,
    LearningAIInteraction,
    LearningAISettings,
    LearningAssessment,
    LearningQuestion,
    LearningSubmission,
    LearningCourse,
    LearningLesson,
    LearningSubject,
    LearningSubscriptionCard,
    LearningSubscriptionPlan,
)


INPUT_CLASS = "learning-input"


def _normalise_slug(value, fallback):
    return slugify((value or fallback or "").strip(), allow_unicode=True)


class LearningRegistrationForm(forms.Form):
    full_name = forms.CharField(label="الاسم الكامل", max_length=200)
    email = forms.EmailField(label="البريد الإلكتروني", max_length=254)
    phone = forms.CharField(label="رقم الهاتف", max_length=30, required=False)
    password1 = forms.CharField(label="كلمة المرور", strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label="تأكيد كلمة المرور", strip=False, widget=forms.PasswordInput)
    accept_terms = forms.BooleanField(label="أوافق على شروط استخدام منصة أوبال التعليمية")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "accept_terms":
                field.widget.attrs["class"] = "learning-check"
            else:
                field.widget.attrs["class"] = INPUT_CLASS
            if name == "email":
                field.widget.attrs["autocomplete"] = "email"
            elif name == "full_name":
                field.widget.attrs["autocomplete"] = "name"
            elif name == "phone":
                field.widget.attrs["autocomplete"] = "tel"
            elif name == "password1":
                field.widget.attrs["autocomplete"] = "new-password"
            elif name == "password2":
                field.widget.attrs["autocomplete"] = "new-password"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if LearningAccount.objects.filter(email__iexact=email).exists():
            raise ValidationError("يوجد حساب تعليمي بهذا البريد. استخدم تسجيل الدخول.")
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "كلمتا المرور غير متطابقتين.")
        if password1:
            try:
                validate_password(password1)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    @transaction.atomic
    def save(self):
        accepted_at = timezone.now()
        account = LearningAccount(
            full_name=self.cleaned_data["full_name"],
            email=self.cleaned_data["email"],
            phone=self.cleaned_data.get("phone", ""),
            role=LearningAccount.Role.LEARNER,
            terms_accepted_at=accepted_at,
            privacy_accepted_at=accepted_at,
        )
        account.set_password(self.cleaned_data["password1"])
        account.save()
        return account


class LearningLegalAcceptanceForm(forms.Form):
    accept_terms = forms.BooleanField(label="أوافق على شروط الاستخدام")
    accept_privacy = forms.BooleanField(label="أوافق على سياسة الخصوصية")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "learning-check"


class LearningLoginForm(forms.Form):
    email = forms.EmailField(label="البريد الإلكتروني", max_length=254)
    password = forms.CharField(label="كلمة المرور", strip=False, widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.account = None
        self.fields["email"].widget.attrs.update({"class": INPUT_CLASS, "autocomplete": "email"})
        self.fields["password"].widget.attrs.update({"class": INPUT_CLASS, "autocomplete": "current-password"})

    def clean(self):
        cleaned = super().clean()
        email = (cleaned.get("email") or "").strip().lower()
        password = cleaned.get("password") or ""
        from .security_services import account_is_locked, record_login_failure, record_login_success

        account = LearningAccount.objects.filter(email__iexact=email, is_active=True).first()
        if account is not None and account_is_locked(account):
            raise ValidationError("الحساب مقفل مؤقتًا بسبب محاولات دخول متكررة. حاول لاحقًا أو استخدم استعادة كلمة المرور.")
        if not account or not account.check_password(password):
            if account is not None:
                record_login_failure(account)
            raise ValidationError("البريد الإلكتروني أو كلمة المرور غير صحيحة.")
        if account.role == LearningAccount.Role.MANAGER:
            raise ValidationError("مدير المنصة يدخل من حساب OPAL ERP عبر الرابط الموجود في القائمة الجانبية.")
        self.account = record_login_success(account)
        return cleaned


class LearningTeacherCreateForm(forms.Form):
    full_name = forms.CharField(label="اسم المدرّس", max_length=200)
    email = forms.EmailField(label="البريد الإلكتروني", max_length=254)
    phone = forms.CharField(label="رقم الهاتف", max_length=30, required=False)
    password1 = forms.CharField(label="كلمة المرور الأولية", strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label="تأكيد كلمة المرور", strip=False, widget=forms.PasswordInput)
    is_active = forms.BooleanField(label="الحساب فعال", required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "learning-check" if name == "is_active" else INPUT_CLASS
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["phone"].widget.attrs["autocomplete"] = "tel"
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if LearningAccount.objects.filter(email__iexact=email).exists():
            raise ValidationError("يوجد حساب منصة بهذا البريد الإلكتروني.")
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "كلمتا المرور غير متطابقتين.")
        if password1:
            try:
                validate_password(password1)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    @transaction.atomic
    def save(self):
        account = LearningAccount(
            full_name=self.cleaned_data["full_name"],
            email=self.cleaned_data["email"],
            phone=self.cleaned_data.get("phone", ""),
            role=LearningAccount.Role.TEACHER,
            is_active=self.cleaned_data.get("is_active", False),
        )
        account.set_password(self.cleaned_data["password1"])
        account.save()
        return account


class LearningSubjectForm(forms.ModelForm):
    slug = forms.SlugField(label="المعرف", max_length=140, required=False, allow_unicode=True)

    class Meta:
        model = LearningSubject
        fields = ["name", "slug", "is_active"]
        labels = {"is_active": "المادة فعالة"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "learning-check" if name == "is_active" else INPUT_CLASS
        self.fields["slug"].help_text = "اتركه فارغًا ليُنشأ تلقائيًا من اسم المادة."

    def clean_slug(self):
        value = _normalise_slug(self.cleaned_data.get("slug"), self.cleaned_data.get("name"))
        if not value:
            raise ValidationError("تعذر إنشاء معرف صالح للمادة.")
        query = LearningSubject.objects.filter(slug=value)
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise ValidationError("هذا المعرف مستخدم لمادة أخرى.")
        return value


class LearningCourseForm(forms.ModelForm):
    slug = forms.SlugField(label="المعرف", max_length=240, required=False, allow_unicode=True)

    class Meta:
        model = LearningCourse
        fields = ["subject", "teacher", "title", "slug", "summary", "grade_label", "cover_color"]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 5}),
            "cover_color": forms.TextInput(attrs={"type": "color"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher"].queryset = LearningAccount.objects.filter(
            role=LearningAccount.Role.TEACHER,
            is_active=True,
        ).order_by("full_name", "id")
        self.fields["subject"].queryset = LearningSubject.objects.filter(is_active=True).order_by("name")
        if self.instance.pk:
            self.fields["teacher"].queryset = LearningAccount.objects.filter(
                role=LearningAccount.Role.TEACHER,
            ).order_by("full_name", "id")
            self.fields["subject"].queryset = LearningSubject.objects.all().order_by("name")
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS
        self.fields["slug"].help_text = "اتركه فارغًا ليُنشأ تلقائيًا من عنوان الدورة."
        self.fields["cover_color"].help_text = "لون بطاقة الدورة في الدليل."

    def clean_slug(self):
        value = _normalise_slug(self.cleaned_data.get("slug"), self.cleaned_data.get("title"))
        if not value:
            raise ValidationError("تعذر إنشاء معرف صالح للدورة.")
        query = LearningCourse.objects.filter(slug=value)
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise ValidationError("هذا المعرف مستخدم لدورة أخرى.")
        return value

    def clean_teacher(self):
        teacher = self.cleaned_data["teacher"]
        if teacher.role != LearningAccount.Role.TEACHER:
            raise ValidationError("يجب اختيار حساب مدرّس مستقل.")
        if not teacher.is_active:
            raise ValidationError("لا يمكن إسناد الدورة إلى حساب مدرّس موقوف.")
        return teacher


class LearningTeacherSchoolCourseForm(forms.ModelForm):
    assignment = forms.ModelChoiceField(label="التكليف الرسمي", queryset=None)
    slug = forms.SlugField(label="المعرف", max_length=240, required=False, allow_unicode=True)

    class Meta:
        model = LearningCourse
        fields = ["assignment", "title", "slug", "summary", "cover_color"]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 5}),
            "cover_color": forms.TextInput(attrs={"type": "color"}),
        }

    def __init__(self, *args, teacher=None, **kwargs):
        from teachers.models import TeacherAssignment

        self.erp_teacher = teacher
        super().__init__(*args, **kwargs)
        queryset = TeacherAssignment.objects.none()
        if teacher is not None:
            queryset = teacher.assignments.filter(
                is_active=True, academic_year__is_current=True, section__is_active=True, subject__is_active=True
            ).select_related("academic_year", "section", "section__grade", "subject")
        self.fields["assignment"].queryset = queryset
        if self.instance.pk and self.instance.academic_subject_id:
            self.fields["assignment"].initial = queryset.filter(
                subject_id=self.instance.academic_subject_id,
                section_id=self.instance.academic_section_id,
            ).values_list("pk", flat=True).first()
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS
        self.fields["assignment"].help_text = "لا يمكنك إنشاء محتوى إلا لمادة وشعبة مسندتين لك رسميًا."
        self.fields["slug"].help_text = "اتركه فارغًا ليُنشأ تلقائيًا من عنوان الدورة."

    def clean_slug(self):
        value = _normalise_slug(self.cleaned_data.get("slug"), self.cleaned_data.get("title"))
        if not value:
            raise ValidationError("تعذر إنشاء معرف صالح للدورة.")
        query = LearningCourse.objects.filter(slug=value)
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise ValidationError("هذا المعرف مستخدم لدورة أخرى.")
        return value

    def clean_assignment(self):
        assignment = self.cleaned_data["assignment"]
        if self.erp_teacher is None or assignment.teacher_id != self.erp_teacher.pk:
            raise ValidationError("هذا التكليف لا يخص حساب المعلم الحالي.")
        return assignment


class LearningLessonForm(forms.ModelForm):
    slug = forms.SlugField(label="المعرف", max_length=240, required=False, allow_unicode=True)

    class Meta:
        model = LearningLesson
        fields = ["title", "slug", "content", "video_url", "attachment", "duration_minutes", "order", "is_published"]
        widgets = {
            "content": forms.Textarea(attrs={"rows": 10}),
            "video_url": forms.URLInput(attrs={"dir": "ltr"}),
        }
        labels = {"is_published": "الدرس منشور"}

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.course = course or getattr(self.instance, "course", None)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "learning-check" if name == "is_published" else INPUT_CLASS
        self.fields["slug"].help_text = "اتركه فارغًا ليُنشأ تلقائيًا من عنوان الدرس."

    def clean_slug(self):
        value = _normalise_slug(self.cleaned_data.get("slug"), self.cleaned_data.get("title"))
        if not value:
            raise ValidationError("تعذر إنشاء معرف صالح للدرس.")
        if self.course is not None:
            query = LearningLesson.objects.filter(course=self.course, slug=value)
            if self.instance.pk:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise ValidationError("هذا المعرف مستخدم لدرس آخر داخل الدورة.")
        return value

    def clean_order(self):
        value = self.cleaned_data["order"]
        if self.course is not None:
            query = LearningLesson.objects.filter(course=self.course, order=value)
            if self.instance.pk:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise ValidationError("هذا الترتيب مستخدم لدرس آخر داخل الدورة.")
        return value


class SubscriptionActivationForm(forms.Form):
    code = forms.CharField(label="رمز بطاقة الاشتراك", max_length=64)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.card = None
        self.fields["code"].widget.attrs.update(
            {
                "class": f"{INPUT_CLASS} code-input",
                "autocomplete": "off",
                "placeholder": "مثال: OPAL-2026-XXXX",
            }
        )

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        card = LearningSubscriptionCard.objects.filter(code=code).first()
        if not card or card.status != LearningSubscriptionCard.Status.AVAILABLE:
            raise ValidationError("رمز البطاقة غير صالح أو مستخدم مسبقًا.")
        self.card = card
        return code


class LearningSubscriptionBatchForm(forms.Form):
    duration = forms.ChoiceField(
        label="مدة الاشتراك",
        choices=LearningSubscriptionCard.Duration.choices,
    )
    grants_all_subjects = forms.BooleanField(
        label="تمنح الوصول إلى جميع المواد",
        required=False,
    )
    subjects = forms.ModelMultipleChoiceField(
        label="المواد المشمولة",
        queryset=LearningSubject.objects.none(),
        required=False,
    )
    quantity = forms.IntegerField(label="عدد البطاقات", min_value=1, max_value=100, initial=1)
    prefix = forms.RegexField(
        label="بادئة الرمز",
        regex=r"^[A-Za-z0-9-]{2,16}$",
        required=False,
        initial="OPAL",
        error_messages={"invalid": "استخدم أحرفًا إنجليزية وأرقامًا وشرطة فقط."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subjects"].queryset = LearningSubject.objects.filter(is_active=True).order_by("name")
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "learning-check" if name == "grants_all_subjects" else INPUT_CLASS
        self.fields["subjects"].widget.attrs["size"] = "6"
        self.fields["prefix"].help_text = "مثال: OPAL أو SUMMER-26. سيضاف جزء عشوائي آمن لكل بطاقة."

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("grants_all_subjects") and not cleaned.get("subjects"):
            self.add_error("subjects", "اختر مادة واحدة على الأقل أو فعّل خيار جميع المواد.")
        return cleaned

    @transaction.atomic
    def save(self):
        duration = self.cleaned_data["duration"]
        grants_all = self.cleaned_data.get("grants_all_subjects", False)
        subjects = list(self.cleaned_data.get("subjects") or [])
        quantity = self.cleaned_data["quantity"]
        prefix = (self.cleaned_data.get("prefix") or "OPAL").strip().upper()
        cards = []
        reserved_codes = set()
        for _ in range(quantity):
            code = generate_unique_card_code(prefix=prefix, reserved=reserved_codes)
            card = LearningSubscriptionCard.objects.create(
                code=code,
                duration=duration,
                grants_all_subjects=grants_all,
            )
            if not grants_all:
                card.subjects.set(subjects)
            cards.append(card)
        return cards


class LearningAssessmentForm(forms.ModelForm):
    slug = forms.SlugField(label="المعرف", max_length=240, required=False, allow_unicode=True)

    class Meta:
        model = LearningAssessment
        fields = [
            "title",
            "slug",
            "assessment_type",
            "instructions",
            "max_score",
            "pass_score",
            "max_attempts",
            "order",
            "is_required",
            "is_published",
            "due_at",
        ]
        widgets = {
            "instructions": forms.Textarea(attrs={"rows": 6}),
            "due_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.course = course or getattr(self.instance, "course", None)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = (
                "learning-check" if name in {"is_required", "is_published"} else INPUT_CLASS
            )
        self.fields["slug"].help_text = "اتركه فارغًا ليُنشأ تلقائيًا من عنوان التقييم."
        self.fields["assessment_type"].help_text = "الاختبار يُصحح تلقائيًا، والواجب يحتاج تصحيح المدرّس."

    def clean_slug(self):
        value = _normalise_slug(self.cleaned_data.get("slug"), self.cleaned_data.get("title"))
        if not value:
            raise ValidationError("تعذر إنشاء معرف صالح للتقييم.")
        if self.course is not None:
            query = LearningAssessment.objects.filter(course=self.course, slug=value)
            if self.instance.pk:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise ValidationError("هذا المعرف مستخدم لتقييم آخر داخل الدورة.")
        return value

    def clean_order(self):
        value = self.cleaned_data["order"]
        if self.course is not None:
            query = LearningAssessment.objects.filter(course=self.course, order=value)
            if self.instance.pk:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise ValidationError("هذا الترتيب مستخدم لتقييم آخر داخل الدورة.")
        return value

    def clean(self):
        cleaned = super().clean()
        maximum = cleaned.get("max_score")
        passing = cleaned.get("pass_score")
        if maximum is not None and passing is not None and passing > maximum:
            self.add_error("pass_score", "علامة النجاح لا يمكن أن تتجاوز العلامة القصوى.")
        assessment_type = cleaned.get("assessment_type")
        max_attempts = cleaned.get("max_attempts")
        if assessment_type == LearningAssessment.Type.ASSIGNMENT and max_attempts and max_attempts > 3:
            self.add_error("max_attempts", "الواجب يسمح بثلاث محاولات كحد أقصى.")
        return cleaned


class LearningQuestionForm(forms.ModelForm):
    class Meta:
        model = LearningQuestion
        fields = [
            "text",
            "choice_a",
            "choice_b",
            "choice_c",
            "choice_d",
            "correct_choice",
            "points",
            "order",
        ]
        widgets = {"text": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, assessment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.assessment = assessment or getattr(self.instance, "assessment", None)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS

    def clean_order(self):
        value = self.cleaned_data["order"]
        if self.assessment is not None:
            query = LearningQuestion.objects.filter(assessment=self.assessment, order=value)
            if self.instance.pk:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise ValidationError("هذا الترتيب مستخدم لسؤال آخر داخل الاختبار.")
        return value


class LearningQuizAttemptForm(forms.Form):
    def __init__(self, *args, assessment, **kwargs):
        super().__init__(*args, **kwargs)
        self.assessment = assessment
        self.questions = list(assessment.questions.order_by("order", "id"))
        for question in self.questions:
            self.fields[f"question_{question.pk}"] = forms.ChoiceField(
                label=question.text,
                choices=[
                    (LearningQuestion.Choice.A, question.choice_a),
                    (LearningQuestion.Choice.B, question.choice_b),
                    (LearningQuestion.Choice.C, question.choice_c),
                    (LearningQuestion.Choice.D, question.choice_d),
                ],
                widget=forms.RadioSelect,
            )

    def answers_payload(self):
        return {
            str(question.pk): self.cleaned_data[f"question_{question.pk}"]
            for question in self.questions
        }


class LearningAssignmentSubmissionForm(forms.Form):
    answer_text = forms.CharField(
        label="إجابة الواجب",
        min_length=10,
        widget=forms.Textarea(attrs={"rows": 12, "class": INPUT_CLASS}),
    )


class LearningSubmissionGradeForm(forms.Form):
    score = forms.DecimalField(label="العلامة", min_value=0, decimal_places=2, max_digits=7)
    feedback = forms.CharField(
        label="ملاحظات المصحح",
        required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
    )

    def __init__(self, *args, max_score, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["score"].max_value = max_score
        self.fields["score"].widget.attrs.update({"class": INPUT_CLASS, "max": max_score})
        self.fields["feedback"].widget.attrs["class"] = INPUT_CLASS
        self.fields["score"].help_text = f"العلامة القصوى: {max_score}."


class LearningPasswordResetRequestForm(forms.Form):
    email = forms.EmailField(label="البريد الإلكتروني", max_length=254)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {"class": INPUT_CLASS, "autocomplete": "email"}
        )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class LearningPasswordResetConfirmForm(forms.Form):
    password1 = forms.CharField(
        label="كلمة المرور الجديدة",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="تأكيد كلمة المرور الجديدة",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "autocomplete": "new-password"}),
    )

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "كلمتا المرور غير متطابقتين.")
        if password1:
            try:
                validate_password(password1)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned


class LearningManagerPasswordResetForm(forms.Form):
    confirm = forms.BooleanField(
        label="أؤكد إنشاء كلمة مرور مؤقتة وإبطال جلسات الحساب السابقة",
        widget=forms.CheckboxInput(attrs={"class": "learning-check"}),
    )


class LearningReportFilterForm(forms.Form):
    date_from = forms.DateField(
        label="من تاريخ",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        label="إلى تاريخ",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    subject = forms.ModelChoiceField(
        label="المادة",
        queryset=LearningSubject.objects.none(),
        required=False,
        empty_label="جميع المواد",
    )
    course = forms.ModelChoiceField(
        label="الدورة",
        queryset=LearningCourse.objects.none(),
        required=False,
        empty_label="جميع الدورات",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subject"].queryset = LearningSubject.objects.order_by("name")
        courses = LearningCourse.objects.select_related("subject").order_by("title")
        subject_value = self.data.get("subject") if self.is_bound else self.initial.get("subject")
        if subject_value:
            try:
                courses = courses.filter(subject_id=int(subject_value))
            except (TypeError, ValueError):
                pass
        self.fields["course"].queryset = courses
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS

    def clean(self):
        cleaned = super().clean()
        date_from = cleaned.get("date_from")
        date_to = cleaned.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error("date_to", "تاريخ النهاية يجب أن يكون بعد تاريخ البداية.")
        subject = cleaned.get("subject")
        course = cleaned.get("course")
        if subject and course and course.subject_id != subject.pk:
            self.add_error("course", "الدورة لا تتبع المادة المحددة.")
        return cleaned


class LearningAIQuestionForm(forms.Form):
    course = forms.ModelChoiceField(
        label="الدورة",
        queryset=LearningCourse.objects.none(),
        empty_label="اختر الدورة",
    )
    question = forms.CharField(
        label="سؤالك",
        min_length=3,
        max_length=3000,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "اكتب سؤالًا مرتبطًا بمحتوى الدورة المنشور...",
            }
        ),
    )

    def __init__(self, *args, account, **kwargs):
        super().__init__(*args, **kwargs)
        self.account = account
        self.fields["course"].queryset = (
            LearningCourse.objects.filter(
                enrollments__learner=account,
                status=LearningCourse.Status.PUBLISHED,
            )
            .exclude(enrollments__status="cancelled")
            .select_related("subject", "teacher")
            .distinct()
            .order_by("title")
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS


class LearningTeacherAIForm(forms.Form):
    TOOL_CHOICES = [
        (LearningAIInteraction.Type.TEACHER_SUMMARY, "إنشاء ملخص"),
        (LearningAIInteraction.Type.TEACHER_OUTLINE, "إنشاء خطة درس"),
        (LearningAIInteraction.Type.TEACHER_REVIEW_QUESTIONS, "إنشاء أسئلة مراجعة"),
        (LearningAIInteraction.Type.TEACHER_ASSIGNMENT, "إنشاء مسودة واجب"),
    ]

    course = forms.ModelChoiceField(
        label="الدورة",
        queryset=LearningCourse.objects.none(),
        empty_label="اختر دورة من دوراتك",
    )
    tool = forms.ChoiceField(label="الأداة", choices=TOOL_CHOICES)
    title = forms.CharField(label="عنوان المسودة", max_length=220, required=False)
    prompt = forms.CharField(
        label="الموضوع والتعليمات",
        min_length=3,
        max_length=3000,
        widget=forms.Textarea(
            attrs={
                "rows": 6,
                "placeholder": "حدّد الموضوع والصف والهدف وأي شروط تريد مراعاتها...",
            }
        ),
    )

    def __init__(self, *args, account, **kwargs):
        super().__init__(*args, **kwargs)
        self.account = account
        self.fields["course"].queryset = LearningCourse.objects.filter(
            teacher=account,
        ).select_related("subject").order_by("title")
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS
        self.fields["title"].help_text = "يُستخدم لتنظيم المسودة فقط، ولا تُنشر تلقائيًا."


class LearningAISettingsForm(forms.ModelForm):
    class Meta:
        model = LearningAISettings
        fields = [
            "assistant_enabled",
            "teacher_tools_enabled",
            "external_provider_enabled",
            "local_reference_enabled",
            "learner_daily_limit",
            "teacher_daily_limit",
            "max_context_chars",
            "max_output_chars",
            "policy_text",
        ]
        widgets = {
            "policy_text": forms.Textarea(attrs={"rows": 7}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        checkbox_fields = {
            "assistant_enabled",
            "teacher_tools_enabled",
            "external_provider_enabled",
            "local_reference_enabled",
        }
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "learning-check" if name in checkbox_fields else INPUT_CLASS
        self.fields["external_provider_enabled"].help_text = (
            "لا يعمل المزود الخارجي إلا بعد وضع عنوان الخدمة والمفتاح والنموذج في متغيرات البيئة."
        )
        self.fields["local_reference_enabled"].help_text = (
            "يعرض مقتطفات مرجعية واضحة من الدروس عندما لا يتوفر المزود الخارجي."
        )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("external_provider_enabled") and not cleaned.get("local_reference_enabled"):
            raise ValidationError("يجب تفعيل المزود الخارجي أو المرجع المحلي على الأقل.")
        return cleaned

class LearningSubscriptionPlanForm(forms.ModelForm):
    slug = forms.SlugField(label="المعرف", max_length=180, required=False, allow_unicode=True)

    class Meta:
        model = LearningSubscriptionPlan
        fields = [
            "name",
            "slug",
            "duration",
            "price",
            "currency",
            "grants_all_subjects",
            "subjects",
            "is_active",
            "display_order",
        ]
        widgets = {
            "subjects": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in {"grants_all_subjects", "is_active"}:
                field.widget.attrs["class"] = "learning-check"
            elif name == "subjects":
                field.widget.attrs["class"] = "learning-choice-grid"
            else:
                field.widget.attrs["class"] = INPUT_CLASS
        self.fields["currency"].widget.attrs.update({"maxlength": 3, "dir": "ltr"})
        self.fields["slug"].help_text = "اتركه فارغًا ليُنشأ من اسم الخطة."

    def clean_slug(self):
        value = _normalise_slug(self.cleaned_data.get("slug"), self.cleaned_data.get("name"))
        if not value:
            raise ValidationError("تعذر إنشاء معرف صالح للخطة.")
        query = LearningSubscriptionPlan.objects.filter(slug=value)
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise ValidationError("هذا المعرف مستخدم لخطة أخرى.")
        return value

    def clean_currency(self):
        value = (self.cleaned_data.get("currency") or "JOD").strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise ValidationError("رمز العملة يجب أن يتكون من ثلاثة أحرف مثل JOD.")
        return value

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("grants_all_subjects") and not cleaned.get("subjects"):
            self.add_error("subjects", "اختر مادة واحدة على الأقل أو فعّل جميع المواد.")
        return cleaned


class LearningPaymentCheckoutForm(forms.Form):
    plan = forms.ModelChoiceField(
        label="خطة الاشتراك",
        queryset=LearningSubscriptionPlan.objects.none(),
        empty_label="اختر الخطة",
    )
    confirm = forms.BooleanField(
        label="أوافق على إنشاء طلب الدفع وفق سعر الخطة وسياسة الاسترداد",
        widget=forms.CheckboxInput(attrs={"class": "learning-check"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plan"].queryset = LearningSubscriptionPlan.objects.filter(
            is_active=True
        ).order_by("display_order", "price", "id")
        self.fields["plan"].widget.attrs["class"] = INPUT_CLASS

