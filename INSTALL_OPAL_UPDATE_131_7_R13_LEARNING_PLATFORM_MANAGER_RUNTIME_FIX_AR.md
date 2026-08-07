# تركيب OPAL Update 131.7 R13

هذا تحديث إصلاحي عاجل بعد R12. يعالج ظهور صفحة **500** عند فتح لوحة إدارة منصة أوبال التعليمية من حساب مدير OPAL ERP.

## سبب الخطأ

كانت الدالة `manager_dashboard` تستخدم النموذج `LearningAccount` دون استيراده داخل `learning_platform/views.py`، مما يؤدي إلى `NameError` وHTTP 500 عند فتح `/learning/manage/`.

## التركيب من مركز التحديثات

1. ارفع حزمة R13 من مركز التحديثات وثبّتها فوق R12.
2. بعد نجاح التثبيت اضغط Reload لتطبيق الويب.
3. افتح منصة أوبال التعليمية من القائمة الجانبية بحساب المدير.

## أوامر التحقق على PythonAnywhere

```bash
cd /home/Opalschool2016/opal_school
source /home/Opalschool2016/.virtualenvs/opal/bin/activate
python tools/validate_opal_update_131_source.py .
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py test learning_platform core.test_update131_7_r13_learning_platform_manager_runtime_fix_contract
python manage.py collectstatic --clear --noinput
```

## اختبار القبول

- دخول المدير من OPAL ERP ثم فتح `/learning/manage/` يعيد 200 وتظهر لوحة إدارة المنصة.
- لا يُنشأ حساب `LearningAccount` للمدير.
- `/learning/login/` و`/learning/register/` يبقيان مستقلين لبقية مستخدمي المنصة.
- لا توجد هجرة قاعدة بيانات جديدة في R13.
