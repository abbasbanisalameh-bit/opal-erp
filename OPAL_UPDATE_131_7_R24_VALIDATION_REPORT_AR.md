# تقرير تحقق OPAL Update 131.7 R24

## الهوية

- الإصدار: `131.7`
- اسم الإصدار: `OPAL Update 131.7 R24 - Migration Identity Ordering Fix`
- خط الأساس: `OPAL Update 131.7 R23 - Release Identity Deployment Synchronization`
- نوع الحزمة: `code_only`
- الهجرة الجديدة: `core/0013_r24_migration_identity_ordering_fix.py`

## سبب الإصلاح

عند إنشاء قاعدة بيانات اختبار جديدة، كانت هجرة R21 التاريخية `learning_platform.0007` تعيد كتابة `OPAL_UPDATE_MANIFEST.json` باسم R21 بعد تثبيت كود أحدث. لذلك كانت اختبارات R20-R23 ترى `OPAL_RELEASE_NAME.txt` باسم الإصدار الحالي وmanifest باسم R21، فتفشل عقود الهوية رغم سلامة وظائف المنصة.

## الإصلاحات

- منع هجرة R21 من تخفيض manifest إذا كان الملف الحالي يحمل `package_revision` أحدث.
- إضافة هجرة R24 تعتمد صراحة على هجرة R21 ثم تثبت ملفات الهوية الثلاثة في النهاية.
- إضافة عقد اختبار يمنع تكرار المشكلة في قواعد الاختبار والبيئات الجديدة.
- لا تغييرات على بيانات الحسابات أو الدورات أو الاشتراكات أو الصلاحيات.

## التحقق الساكن

- تحليل تركيب جميع ملفات Python: ناجح؛ `632` ملف Python.
- بوابة المصدر: `321/321` ناجحة دون أخطاء أو تحذيرات.
- فحص هوية الإصدار وmanifest: ناجح.
- فحص ترتيب الهجرات وحماية R21 من التخفيض: ناجح.
- فحص الأرشيف النهائي: ناجح؛ `1308` ملفًا، دون قاعدة بيانات أو وسائط أو بيئة افتراضية أو أسرار.

## التحقق المطلوب على PythonAnywhere

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test learning_platform core.test_update131_7_r20_learning_production_release_contract core.test_update131_7_r21_learning_runtime_validation_fix_contract core.test_update131_7_r22_forward_compatible_release_contract core.test_update131_7_r23_release_identity_deployment_sync_contract core.test_update131_7_r24_migration_identity_ordering_fix_contract
```

لا يُعتمد R24 قبل ظهور `OK` ثم نجاح الاختبارات الكاملة.
