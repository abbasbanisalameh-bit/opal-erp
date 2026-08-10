# تقرير تحقق R37

## فحوص المصدر المنفذة في بيئة إعداد الحزمة
- نجحت بوابة المصدر الثابتة: **355/355 PASS**، وتم تحليل **679 ملف Python** دون خطأ نحوي.
- نجح Python bytecode compilation للملفات Python الجديدة والمعدلة المتعلقة بالتطبيق.
- اجتاز `mobile/opal_erp_app/lib/main.dart` فحص توازن الأقواس البنيوي دون عدم تطابق.
- التطبيق يستخدم HTTPS افتراضيًا إلى `/mobile/api/v1`.
- الشعار المستخدم داخل التطبيق مشتق مباشرة من الشعار الدائري الرسمي الذي اعتمده المستخدم، مع قص المساحة المحيطة فقط لاستخدامه كأصل تطبيق.
- Package تطبيق النظام منفصل عن تطبيق المنصة؛ أداة التجهيز تستخدم `com.opalschool2016` مع project name `opal_erp_app`.
- لا تحتوي الحزمة المقصودة على قاعدة بيانات أو `.env` أو `media` أو مفاتيح توقيع.

## عقد الأمان
- رمز الجلسة يبدأ بـ `oer_`.
- قاعدة البيانات تخزن Hash للرمز ولا تخزن الرمز الخام.
- حساب غير مخول لا يحصل على جلسة تطبيق النظام.
- الصلاحيات والوحدات تحدد على الخادم، وليس من التطبيق فقط.
- endpoints التشغيلية في R37 تستخدم GET للقراءة؛ تسجيل الدخول والخروج فقط يستخدمان POST.

## التحقق المطلوب على PythonAnywhere

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test core.test_update131_7_r37_erp_mobile_app_contract --settings=config.settings_test_low_memory --verbosity 1 --noinput
```

المتوقع: **6 tests / OK**.

## التحقق المطلوب على GitHub
بعد تثبيت Workflow ورفع الكود يجب أن يمر:

```text
Flutter packages
Analyze
Test
Build APK and AAB
Upload OPAL ERP Android artifacts
```

لا تدّعي هذه الحزمة أن APK النهائي قد بُني داخل PythonAnywhere؛ البناء الفعلي يتم في GitHub Actions.
