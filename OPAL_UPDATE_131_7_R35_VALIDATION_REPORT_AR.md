# تقرير تحقق OPAL Update 131.7 R35

## النطاق

R35 يكمل مشروع Flutter الموجود في R34 ليصبح قابلاً لبناء Android بصورة متكررة وآمنة، مع الحفاظ على SSO المدرسي، تبديل الأبناء، فيديو الدرس داخل التطبيق، وبطاقات الاشتراك.

## نتائج التحقق في بيئة البناء

- ملفات Python المفحوصة نحويًا: **667**.
- أخطاء Python النحوية: **0**.
- عقد دخول ولي الأمر/المعلم عبر `auth/school-login/`: **PASS**.
- فصل هوية الأبناء عبر `MobileProfile`: **PASS**.
- تشغيل الفيديو داخل التطبيق عبر `WebViewWidget`: **PASS**.
- تفعيل بطاقة الاشتراك من التطبيق: **PASS**.
- عنوان API الافتراضي HTTPS للإنتاج: **PASS**.
- إزالة `example.invalid` من إعداد التطبيق الافتراضي: **PASS**.
- وجود قالب GitHub Actions لبناء APK/AAB: **PASS**.
- وجود أمر Django لتثبيت Workflow في `.github/workflows`: **PASS**.
- توازن بنية ملف Dart (أقواس/كتل): **PASS**.
- محاكاة إنشاء Android scaffold ثم حماية `AndroidManifest.xml`: **PASS**، بما في ذلك Internet permission و`usesCleartextTraffic=false` وعنوان التطبيق.

## ما لم يمكن تشغيله في بيئة البناء

لا يوجد Flutter SDK أو Dart SDK في بيئة البناء الحالية، لذلك لم يتم تنفيذ `flutter analyze` أو `flutter test` أو إنتاج APK فعلي هنا. R35 يضيف GitHub Actions ليجري هذه الفحوص ويبني APK/AAB في بيئة Flutter حقيقية. كما يجب تشغيل اختبار Django الخاص بـR35 على PythonAnywhere بعد التركيب.

## قاعدة البيانات

- لا توجد Migration جديدة.
- لا توجد تعديلات على `students.Student` أو بيانات الطلاب/الأسر/المعلمين.
- لا توجد تعديلات على بوابة البصمة R34.
- شرط النسخة الاحتياطية في جاهزية منصة التعلم لم يتغير.

## ملاحظة `.github`

محرك تحديث OPAL يحمي `.github` ويستبعده من الاستبدال المباشر. لذلك Workflow محفوظ داخل الحزمة في `mobile/opal_learning_app/ci/opal-android-build.yml`، وبعد التركيب يثبت بالأمر:

```bash
python manage.py install_mobile_android_ci
```
