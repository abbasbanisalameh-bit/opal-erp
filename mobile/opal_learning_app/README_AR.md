# تطبيق أوبال Android — R35

تطبيق Flutter لمنصة أوبال التعليمية، يستخدم نفس حساب OPAL لولي الأمر والمعلم، ويصدر لكل ابن هوية تعلم مستقلة عند دخول ولي الأمر.

## الوظائف الحالية

- دخول ولي الأمر بنفس حساب OPAL واختيار الابن/التبديل بين الأبناء.
- دخول المعلم بنفس حساب OPAL عندما تسمح إعدادات المدرسة.
- دعم حسابات منصة التعلم المستقلة بالبريد الإلكتروني.
- حفظ رموز الدخول في `flutter_secure_storage`.
- الدورات والدروس والتقدم والاختبارات والواجبات والإشعارات والشهادات.
- فيديو الدرس داخل التطبيق عبر WebView (YouTube/Vimeo/الفيديو المباشر).
- تفعيل بطاقات الاشتراك العشوائية داخل التطبيق.
- الاتصال الافتراضي الآمن بـ:
  `https://opalschool2016.pythonanywhere.com/learning/api/v1`
- يمكن تغيير عنوان API أثناء البناء عبر `OPAL_API_BASE_URL` بدون تضمين أي سر داخل التطبيق.

## لماذا لا يُبنى APK على PythonAnywhere؟

PythonAnywhere لا يحتوي Flutter/Dart في البيئة الحالية. لذلك R35 يوفر مسارين للبناء:

### 1) GitHub Actions — الموصى به

بعد رفع R35 إلى GitHub، افتح:

`GitHub → Actions → OPAL Android Build → Run workflow`

ينتج Artifact باسم `opal-android-release` يحتوي:

- `app-release.apk` للتثبيت والاختبار.
- `app-release.aab` كأساس للنشر في Google Play.
- `android-release-sha256.txt` للتحقق من الملفات.

يمكن ضبط Repository Variable باسم `OPAL_API_BASE_URL`. إذا لم تضبطه، يستخدم التطبيق عنوان PythonAnywhere الحالي أعلاه.

### 2) جهاز تطوير عليه Flutter

```bash
cd mobile/opal_learning_app
bash tool/prepare_android.sh
bash tool/build_android_release.sh
```

أو:

```bash
OPAL_API_BASE_URL=https://YOUR-DOMAIN/learning/api/v1 bash tool/build_android_release.sh
```

## التوقيع

البناء الافتراضي مناسب للتثبيت والاختبار. مفتاح توقيع المتجر **لا يُحفظ داخل المستودع**. قبل النشر في Google Play يجب إنشاء مفتاح توقيع إنتاجي وحفظه في GitHub Secrets/بيئة بناء آمنة، ثم إعداد Play App Signing.

## أمان التطبيق

- لا توجد كلمات مرور أو مفاتيح API خادمية داخل المصدر.
- الاتصال الافتراضي HTTPS فقط.
- Android يمنع cleartext HTTP في إعداد R35.
- Tokens تحفظ في التخزين الآمن للجهاز.
- فصل هوية كل ابن يتم من الخادم ولا يعتمد على قيمة يختارها التطبيق يدويًا.
