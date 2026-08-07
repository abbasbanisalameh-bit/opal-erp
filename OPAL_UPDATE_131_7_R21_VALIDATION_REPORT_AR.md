# تقرير تحقق OPAL Update 131.7 R21

## الهوية

- الإصدار: `131.7`
- اسم الإصدار: `OPAL Update 131.7 R21 - Learning Platform Runtime Validation Fixes`
- خط الأساس: `OPAL Update 131.7 R20 - Learning Platform Production Release Candidate`
- مراجعة الحزمة: `24`
- نوع الحزمة: `code_only`
- الهجرة الجديدة: `learning_platform/0007_r21_runtime_validation_fixes.py`

## المشكلات المثبتة من PythonAnywhere

1. اختبار `test_learner_assistant_rejects_course_outside_enrollment` فشل لأنه بحث عن ترجمة حرفية لرسالة Django، مع أن النموذج رفض الدورة خارج تسجيل المتعلم فعلًا.
2. عقد `test_mobile_api_uses_expiring_hashed_tokens_and_role_scope` بحث عن النص العام `Authorization` بينما التنفيذ يستخدم مفتاح Django الصحيح `HTTP_AUTHORIZATION`.
3. عقد `test_r20_release_identity_is_coherent` تعطل لأن محرك مركز التحديثات في R20 استبعد `OPAL_UPDATE_MANIFEST.json` أثناء نسخ المشروع.

## الإصلاحات

- استبدال فحص نص الترجمة بفحص بنيوي لأخطاء حقل الدورة وqueryset المسموح.
- تحديث عقد API ليتحقق من `request.META.get("HTTP_AUTHORIZATION")` ومن صيغة Bearer.
- إزالة استثناء manifest من `_replace_project_code` للتحديثات اللاحقة.
- إضافة هجرة إصلاحية تعيد إنشاء manifest أثناء تركيب R21، لأن عملية التركيب نفسها تبدأ بمحرك R20 القديم.

## التحقق الساكن المنفذ

- تحليل تركيب جميع ملفات Python: ناجح.
- بوابة مصدر OPAL: `287/287` ناجحة.
- عدد ملفات Python المحللة: `626`.
- فحوص R21 المباشرة: ناجحة بالكامل.
- لم يتم تغيير نماذج البيانات التشغيلية أو صلاحيات الحسابات أو منطق الاشتراكات.

## التحقق المطلوب على PythonAnywhere

بيئة البناء لا تحتوي Django، لذلك يجب تشغيل:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test learning_platform core.test_update131_7_r20_learning_production_release_contract core.test_update131_7_r21_learning_runtime_validation_fix_contract
```

بعد نجاح الاختبارات المستهدفة شغّل مجموعة الاختبارات الكاملة.
