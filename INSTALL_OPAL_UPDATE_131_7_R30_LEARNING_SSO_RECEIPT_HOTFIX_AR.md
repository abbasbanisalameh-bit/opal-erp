# تركيب OPAL Update 131.7 R30

## الهدف
إصلاح حالات الفشل الثلاث التي ظهرت في اختبارات R29 على PythonAnywhere:
1. ولي الأمر كان يعاد إلى `/parent/` قبل الوصول إلى `/learning/dashboard/`.
2. المعلم كان يعاد إلى `/teachers/portal/` قبل الوصول إلى `/learning/dashboard/`.
3. واجهة إيصالات ولي الأمر كانت تحتوي كلمة «طباعة» في النص الوصفي رغم عدم وجود رابط طباعة له.

## التغييرات
- السماح لمسار `/learning/` داخل `ParentPortalAccessMiddleware` و`TeacherPortalAccessMiddleware`.
- لا يمنح ذلك صلاحيات إدارية؛ صلاحيات منصة التعلم تبقى مطبقة داخل المنصة حسب `LearningAccount` والدور والجلسة التعليمية.
- تعديل النص الوصفي لسجل إيصالات ولي الأمر ليكون قراءة فقط دون ذكر الطباعة.
- لا توجد migration جديدة ولا تغييرات قاعدة بيانات.

## أوامر ما بعد التركيب
```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test \
  core.test_update131_7_r29_relational_demo_contract \
  core.test_update131_7_r30_learning_sso_receipt_hotfix_contract \
  learning_platform.test_update131_7_r29_school_learning_bridge \
  parent_portal.test_update131_7_r29_receipt_policy \
  parent_portal.tests_receipt_history \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput
```

بعد ظهور `OK` شغّل اختبار إنشاء البيانات التجريبية الكامل قبل الضغط على الزر في قاعدة التشغيل:
```bash
python manage.py test \
  core.tests.SystemDataCenterTests.test_seed_is_comprehensive_and_reset_removes_all_operational_data \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput
```
