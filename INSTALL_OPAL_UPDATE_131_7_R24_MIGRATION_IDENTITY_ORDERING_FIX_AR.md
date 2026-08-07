# تركيب OPAL Update 131.7 R24

## Migration Identity Ordering Fix

يُركب هذا التحديث فوق R23. يعالج فشل اختبارات الهوية الناتج عن إعادة تشغيل هجرة R21 التاريخية عند إنشاء قاعدة بيانات الاختبار؛ كانت الهجرة القديمة تكتب manifest باسم R21 بعد أن يكون الكود الحالي R23.

## نطاق الإصلاح

- منع هجرة `learning_platform.0007` من تخفيض manifest إذا وجدت إصدارًا أحدث.
- إضافة هجرة `core.0013` تعتمد صراحة على هجرة R21 ثم تعيد تثبيت هوية R24 في النهاية.
- لا تغييرات على بيانات المستخدمين أو الدورات أو الاشتراكات أو الصلاحيات.

## بعد التركيب

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test learning_platform core.test_update131_7_r20_learning_production_release_contract core.test_update131_7_r21_learning_runtime_validation_fix_contract core.test_update131_7_r22_forward_compatible_release_contract core.test_update131_7_r23_release_identity_deployment_sync_contract core.test_update131_7_r24_migration_identity_ordering_fix_contract
```

النتيجة المطلوبة: `OK`. بعد ذلك شغّل الاختبارات الكاملة ثم `collectstatic` وReload.
