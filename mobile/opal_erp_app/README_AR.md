# تطبيق نظام أوبال المدرسي — Android

هذا هو تطبيق Flutter الأصلي لنظام **OPAL ERP**، وهو منفصل عن تطبيق **منصة أوبال التعليمية** ويمكن تثبيت التطبيقين معًا على الهاتف.

## الهوية
- الاسم: **نظام أوبال**
- الشعار: شعار مدرسة أوبال الدولية الدائري الرسمي المعتمد من الإدارة.
- API الافتراضي: `https://opalschool2016.pythonanywhere.com/mobile/api/v1`

## الدخول
يدخل المستخدم بنفس اسم المستخدم وكلمة المرور الموجودين أصلًا في OPAL ERP. لا ينشئ التطبيق كلمات مرور مستقلة.

بعد نجاح الدخول يصدر الخادم رمز جلسة يبدأ بـ `oer_`. لا يحفظ الخادم الرمز الخام؛ يحفظ Hash فقط، بينما يخزنه الهاتف في `flutter_secure_storage`.

## الوحدات في R37
تعرض الوحدات المسموحة حسب صلاحية الحساب:
- لوحة التحكم
- الطلاب
- أولياء الأمور
- المعلمون
- الجدول
- الحضور
- الرسوم والدفعات
- الامتحانات والعلامات
- الوثائق
- الإعلانات

R37 هو الإصدار التشغيلي الأول للتطبيق الأصلي، ولذلك وحدات البيانات فيه **قراءة وبحث فقط**. لا ينفذ التطبيق في هذه المرحلة حذفًا أو تعديلًا أو تحصيل دفعات أو إدخال علامات. هذا مقصود لضبط الصلاحيات أولًا قبل توسيع أوامر الكتابة في إصدار لاحق.

## البناء
على GitHub Actions يتم تثبيت Flutter وتجهيز Android ثم تشغيل:

```bash
flutter analyze
flutter test
flutter build apk --release --dart-define="OPAL_ERP_API_BASE_URL=https://opalschool2016.pythonanywhere.com/mobile/api/v1"
flutter build appbundle --release --dart-define="OPAL_ERP_API_BASE_URL=https://opalschool2016.pythonanywhere.com/mobile/api/v1"
```

لتثبيت Workflow داخل المستودع بعد تركيب R37:

```bash
python manage.py install_erp_mobile_android_ci
```
