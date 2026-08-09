# تطبيق أوبال التعليمي — Mobile R34

تطبيق Flutter أصلي لمنصة أوبال التعليمية، ويتصل فقط بواجهات `/learning/api/v1/`.

## ما يدعمه R34

- دخول ولي الأمر **بنفس اسم المستخدم وكلمة مرور OPAL ERP** ثم اختيار الابن إذا كان لديه أكثر من ابن.
- دخول المعلم **بنفس حساب OPAL ERP** عندما تسمح إعدادات المدرسة بدخول المعلمين للمنصة.
- استمرار دعم حسابات المنصة المستقلة بالبريد الإلكتروني وكلمة المرور.
- حفظ رموز الدخول في `flutter_secure_storage` فقط.
- الدورات والدروس والتقدم والاختبارات والواجبات والإشعارات والشهادات.
- تشغيل فيديو الدرس داخل التطبيق نفسه عبر WebView (YouTube/Vimeo/روابط الفيديو المباشرة).
- إدخال بطاقة اشتراك عشوائية من داخل التطبيق وتفعيلها.
- تبديل الابن من داخل التطبيق دون خلط هوية التعلم بين الإخوة.

> حسابات المدرسة المدارة لا تملك كلمة مرور مستقلة داخل `LearningAccount`؛ المصادقة المدرسية تتم دائمًا عبر حساب OPAL ERP ثم يصدر الخادم Token تعليميًا محدودًا للابن/المعلم.

## إنشاء مجلدي Android وiOS لأول مرة

هذا المستودع يحتفظ بمصدر التطبيق الخفيف ولا يثبت Flutter SDK على خادم PythonAnywhere. على جهاز تطوير مثبت عليه Flutter:

```bash
cd mobile/opal_learning_app
flutter create --platforms=android,ios .
flutter pub get
flutter analyze
flutter test
```

ثم التشغيل:

```bash
flutter run --dart-define=OPAL_API_BASE_URL=https://YOUR-DOMAIN/learning/api/v1
```

وبناء Android:

```bash
flutter build apk --release --dart-define=OPAL_API_BASE_URL=https://YOUR-DOMAIN/learning/api/v1
flutter build appbundle --release --dart-define=OPAL_API_BASE_URL=https://YOUR-DOMAIN/learning/api/v1
```

يلزم إعداد package id، الأيقونات، مفاتيح Android، وحساب/شهادات Apple قبل النشر في المتاجر. لا تضع أي مفتاح خادم أو دفع داخل التطبيق.
