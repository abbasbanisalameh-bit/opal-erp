from django.shortcuts import render

# Create your views here.

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from .models import Branch, School
from .forms import BranchForm, SchoolSettingsForm
from enterprise_ops.permissions import management_required

def can_manage_system(user):
    return user.is_superuser or user.is_staff

@login_required
@user_passes_test(can_manage_system)
def system_settings(request):
    school = School.objects.filter(is_active=True).first() or School.objects.create(name="OPAL School")
    if request.method == "POST":
        action = request.POST.get("action", "settings")
        if action in {"seed_system", "reset_all"}:
            if not request.user.is_superuser:
                messages.error(request, "إدخال البيانات الشاملة وتصفيرها متاحان لمدير النظام الأعلى فقط.")
                return redirect("core:system_settings")
            from .system_data import reset_all_operational_data, seed_system_data
            if action == "seed_system":
                result = seed_system_data(user=request.user)
                messages.success(
                    request,
                    f"تم إدخال بيانات شاملة: {result['students']} طالب، {result['teachers']} معلم، "
                    f"{result['families']} ولي أمر، {result['marks']} علامة، {result['documents']} وثيقة، "
                    f"و{result['receipts']} إيصال. كلمة مرور الحسابات المنشأة: {result['password']}",
                )
            elif request.POST.get("confirmation", "").strip() == "تصفير شامل":
                result = reset_all_operational_data(keep_user=request.user)
                messages.success(
                    request,
                    f"تم تصفير جميع البيانات التشغيلية: {result['students']} طالب، {result['teachers']} معلم، "
                    f"{result['families']} ولي أمر، {result['documents']} وثيقة، و{result['receipts']} إيصال.",
                )
            else:
                messages.error(request, "تعذر التصفير: اكتب عبارة «تصفير شامل» كما هي.")
            return redirect("core:system_settings")
        form = SchoolSettingsForm(request.POST, request.FILES, instance=school)
        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث إعدادات النظام بنجاح.")
            return redirect("core:system_settings")
    else:
        form = SchoolSettingsForm(instance=school)
    return render(request, "core/system_settings.html", {"form": form, "school": school})


@login_required
@user_passes_test(can_manage_system)
def branch_list(request):
    school = School.objects.filter(is_active=True).first() or School.objects.first()
    if school is None:
        messages.error(request, "أدخل بيانات المدرسة أولًا.")
        return redirect("core:system_settings")
    form = BranchForm(request.POST or None, school=school)
    if request.method == "POST" and form.is_valid():
        branch = form.save(commit=False)
        branch.school = school
        if branch.is_main:
            Branch.objects.filter(school=school).update(is_main=False)
        branch.save()
        messages.success(request, "تم حفظ الفرع من واجهة النظام.")
        return redirect("core:branch_list")
    return render(request, "core/branch_list.html", {"school": school, "form": form, "branches": school.branches.all()})


@login_required
@user_passes_test(can_manage_system)
def branch_update(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    form = BranchForm(request.POST or None, instance=branch, school=branch.school)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        if item.is_main:
            Branch.objects.filter(school=branch.school).exclude(pk=branch.pk).update(is_main=False)
        item.save()
        messages.success(request, "تم تعديل الفرع.")
        return redirect("core:branch_list")
    return render(request, "core/branch_form.html", {"form": form, "title": "تعديل الفرع"})


def admin_disabled(request):
    from django.http import HttpResponseNotFound
    return HttpResponseNotFound("لوحة Django Admin غير مستخدمة في OPAL ERP. أدخل البيانات من واجهة النظام.")


@login_required
@user_passes_test(lambda user: user.is_superuser)
def integrity_center(request):
    from .data_integrity import run_integrity_audit
    from .models import DataIntegrityRun

    if request.method == "POST":
        action = request.POST.get("action")
        if action in {"scan", "fix_safe"}:
            run = run_integrity_audit(fix_safe=(action == "fix_safe"), user=request.user)
            if action == "fix_safe":
                messages.success(request, f"اكتمل الإصلاح الآمن: عولجت {run.fixed_count} مشكلة، وبقيت {run.critical_count} حرجة للمراجعة.")
            else:
                messages.success(request, f"اكتمل الفحص: {run.total_issues} مشكلة، منها {run.critical_count} حرجة.")
            return redirect(f"{request.path}?run={run.pk}")

    runs = DataIntegrityRun.objects.select_related("created_by")[:20]
    run_id = request.GET.get("run")
    selected_run = DataIntegrityRun.objects.filter(pk=run_id).first() if run_id else runs.first()
    issues = selected_run.issues.all() if selected_run else []
    severity = request.GET.get("severity", "")
    if severity and selected_run:
        issues = issues.filter(severity=severity)
    return render(request, "core/integrity_center.html", {
        "runs": runs, "selected_run": selected_run, "issues": issues,
        "selected_severity": severity,
    })


@management_required
def operations_center(request):
    """Role-aware map of canonical operations and read-only integration diagnostics."""
    from django.urls import NoReverseMatch, reverse

    from .operation_audit import build_operation_audit
    from .workflow_catalog import get_operations_for_user, group_operations

    operations = get_operations_for_user(request.user)
    audit_context = build_operation_audit()
    for issue in audit_context["integration_issues"]:
        try:
            issue["url"] = reverse(issue["route"])
        except NoReverseMatch:
            issue["url"] = ""

    strengths = [
        "نموذج الطالب الرسمي واحد فقط: students.Student، وبطاقة الطالب 360 تجمع القيد والأسرة والرسوم والحضور والعلامات والوثائق والجدول.",
        "التسجيل الذكي ينشئ الطالب والقيد والرسم والدفعة الأولى والإيصال وملف ولي الأمر ويجهز مزامنة OpenEMIS في عملية مترابطة.",
        "تكليف المعلم هو الرابط الرسمي بين المعلم والعام والشعبة والمادة، ويُستخدم في الجدول والعلامات والحضور والواجبات.",
        "الرسوم المدرسية مبسطة حول الرسوم والدفعات والإيصالات والمتبقي والإخوة، مع حذف آمن وسجل عمليات.",
        "بوابتا المعلم وولي الأمر مقيدتان بصلاحيات ومسارات منفصلة، مع إشعارات وتقارير وسجل عمليات مناسب للدور.",
        "النظام يحتوي مراكز مستقلة لسلامة البيانات والتحديثات والصلاحيات والتقارير والتكامل الوزاري.",
    ]
    weaknesses = [
        "بعض البيانات القديمة قد تكون موجودة دون الروابط الرسمية الجديدة؛ لذلك تعرض هذه الصفحة فحوص التكامل وعدد الحالات المطلوب إصلاحها.",
        "الاختبارات الكاملة كبيرة وتحتاج تشغيلًا ضمن بيئة أطول زمنًا أو تقسيمها إلى مجموعات في مسار النشر.",
        "تكامل OpenEMIS ما زال تأسيسيًا حتى توفر واجهة الوزارة والحقول النهائية، ولا يجوز اعتباره مصدر البيانات الداخلي.",
        "لا توجد بعد منظومة مخزون ورواتب وموارد بشرية مكتملة، وهي خارج النطاق الأساسي الحالي ويجب ألا تعطل إكمال وظائف المدرسة الأساسية.",
        "توحيد الواجهة كان موجودًا جزئيًا، لكن البحث العلوي لم يكن ينفذ عملية فعلية؛ أصبح الآن دليل عمليات قابلًا للبحث.",
    ]
    completion_requirements = [
        "معالجة جميع حالات التكامل الظاهرة في الفحوص حتى تصل النسبة إلى 100% قبل إدخال البيانات الحقيقية.",
        "إكمال تغطية الاختبارات الآلية لمسارات التسجيل، الدفع، الإغلاق، الترفيع، نشر العلامات، الحضور، الوثائق والإشعارات.",
        "اعتماد دورة تشغيل سنوية موثقة: إنشاء العام والفصلين، الهيكل، التكليفات، الجدول، التسجيل، التشغيل اليومي، النتائج، ثم الإغلاق والترفيع.",
        "تنفيذ تجربة قبول تشغيلية بأدوار حقيقية: مدير، مسؤول رسوم، سكرتير، معلم وولي أمر، وتسجيل الملاحظات قبل الإطلاق.",
        "تجهيز خطة الانتقال إلى PostgreSQL قبل زيادة عدد المدارس أو الفروع أو المستخدمين المتزامنين.",
        "إكمال الربط الوزاري فقط بعد استلام مواصفات API الرسمية وبيانات الاعتماد من الوزارة.",
    ]

    flow_definitions = [
        {
            "title": "تهيئة العام الدراسي",
            "icon": "calendar-range-fill",
            "description": "تهيئة المرجع الأكاديمي الذي تعتمد عليه بقية الوحدات.",
            "steps": [
                ("إعدادات المدرسة", "core:system_settings"), ("الفروع", "core:branch_list"),
                ("العام الدراسي", "academics:academic_year_list"), ("الفصل الحالي", "academics:semester_list"),
                ("الصفوف والشعب", "academics:academic_structure"), ("المواد", "academics:subject_list"),
                ("الخطة الدراسية", "curriculum:curriculum_list"),
            ],
        },
        {
            "title": "المعلم والجدول",
            "icon": "person-workspace",
            "description": "ملف المعلم ثم الحساب والتكليف، وبعدها إنشاء الجدول دون تعارض.",
            "steps": [
                ("ملف المعلم", "teachers:dashboard"), ("التكليفات", "teachers:dashboard"),
                ("إعداد الحصص", "timetable:schedule_settings"), ("المنشئ الذكي", "timetable:smart_builder"),
                ("الجدول النهائي", "timetable:dashboard"),
            ],
        },
        {
            "title": "التسجيل والملف الموحد",
            "icon": "person-plus-fill",
            "description": "إنشاء الطالب والقيد والأسرة والرسم والإيصال ثم المتابعة من بطاقة 360.",
            "steps": [
                ("المرشحون", "admissions:candidate_list"), ("التسجيل الذكي", "admissions:direct_registration"),
                ("سجل الطلبة", "admissions:admission_list"), ("قائمة الطلاب", "students:student_list"),
                ("ملفات الأسر", "parent_portal:family_management"),
            ],
        },
        {
            "title": "الرسوم المدرسية",
            "icon": "cash-stack",
            "description": "إعداد الرسوم، إصدارها، تحصيلها، ثم التقارير والإغلاق من مسارات غير مكررة.",
            "steps": [
                ("فئات الرسوم", "accounting:fee_category_list"), ("رسوم الطلاب", "accounting:invoice_list"),
                ("التسديد الموحد", "admissions:fee_payment_create"), ("أرشيف التسديد", "admissions:fee_payment_archive"),
                ("الأقساط", "accounting:installment_list"), ("الخصومات", "accounting:discount_list"),
                ("الكشف الشهري", "accounting:monthly_report"), ("الإغلاق المالي", "accounting:financial_year_close"),
            ],
        },
        {
            "title": "التشغيل اليومي والنتائج",
            "icon": "clipboard2-check-fill",
            "description": "الحضور والواجبات والامتحانات والعلامات ثم النشر لولي الأمر.",
            "steps": [
                ("الحضور", "attendance_v2:dashboard"), ("بوابة المعلم", "teachers:portal_dashboard"),
                ("الامتحانات", "exams:exam_list"), ("العلامات", "exams:mark_list"),
                ("تحليل النتائج", "exams:exam_dashboard"), ("بوابة ولي الأمر", "parent_portal:dashboard"),
            ],
        },
        {
            "title": "التواصل والرقابة",
            "icon": "bell-fill",
            "description": "استقبال الملاحظات، قياس الرضا، إرسال التنبيهات، ثم التتبع والتقارير.",
            "steps": [
                ("الشكاوى والتقييمات", "enterprise_ops:feedback_list"), ("التعاميم", "enterprise_ops:broadcast_list"),
                ("الإعلانات", "announcements:list"), ("الإشعارات", "enterprise_ops:notification_list"),
                ("التقارير", "enterprise_ops:report_center"), ("سجل العمليات", "enterprise_ops:audit_log"),
            ],
        },
    ]
    operation_flows = []
    for flow in flow_definitions:
        resolved_steps = []
        for label, route in flow["steps"]:
            try:
                resolved_steps.append({"label": label, "url": reverse(route)})
            except NoReverseMatch:
                continue
        operation_flows.append({**flow, "steps": resolved_steps})

    return render(request, "core/operations_center.html", {
        "operation_groups": group_operations(operations),
        "operation_count": len(operations),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "completion_requirements": completion_requirements,
        "operation_flows": operation_flows,
        **audit_context,
    })
