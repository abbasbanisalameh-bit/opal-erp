# تركيب OPAL Update 131.7 R2 — سلامة بيانات لوحة المدير

## التركيب

ارفع ملف ZIP الخاص بالتحديث عبر مركز تحديثات النظام. بعد نجاح التحقق والتركيب اضغط «إعادة تحميل الموقع» مرة واحدة.

## الفحوص المطلوبة على PythonAnywhere

```bash
cd /home/Opalschool2016/opal_school

python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test \
  core.test_update131_7_r2_dashboard_truth_contract \
  core.test_update131_7_fixed_manager_dashboard_contract \
  dashboard.tests
python manage.py audit_dashboard_truth
python manage.py collectstatic --clear --noinput
```

النتائج المطلوبة:

- `System check identified no issues`
- `No changes detected`
- `OK`
- `نجحت جميع تدقيقات لوحة المدير`

## حفظ تقرير التدقيق

```bash
python manage.py audit_dashboard_truth --json > /home/Opalschool2016/dashboard_truth_audit.json
```

يمكن فتح الملف من صفحة Files. يحتوي اسم المدرسة والعام ونتيجة كل مؤشر ومصدره والقيمة المتوقعة والقيمة التي تبنيها اللوحة.

## الاختبار المرئي

- عند عدم تسجيل حضور رسمي اليوم يجب أن تعرض اللوحة «لا يوجد سجل حضور معتمد» لا `0%` كأنه نتيجة.
- عند عدم وجود رسوم في العام الحالي يجب أن تعرض «لا توجد رسوم للعام الحالي».
- عند عدم وجود علامات رسمية يجب ألا تظهر نسبة نجاح أو مخطط وهمي.
- يجب أن تطابق أعداد الطلاب والمعلمين والشعب والرسوم والغياب نتائج صفحاتها الرسمية.
- يجب أن تتطابق أسماء آخر عشرة طلاب مع أحدث قيود الالتحاق النشطة.

لا ترفع النسخة إلى GitHub قبل نجاح أمر `audit_dashboard_truth` كاملًا.
