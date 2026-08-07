# تطبيق أوبال التعليمي — مصدر Flutter R20

هذا المصدر يتصل فقط بـ`/learning/api/v1/` ولا يستخدم جلسة OPAL ERP. رمز الجهاز يحفظ في `flutter_secure_storage`.

## التشغيل التجريبي

```bash
flutter pub get
flutter run --dart-define=OPAL_API_BASE_URL=https://YOUR-DOMAIN.example/learning/api/v1
```

## البناء

```bash
flutter build apk --release --dart-define=OPAL_API_BASE_URL=https://YOUR-DOMAIN.example/learning/api/v1
flutter build appbundle --release --dart-define=OPAL_API_BASE_URL=https://YOUR-DOMAIN.example/learning/api/v1
flutter build ipa --release --dart-define=OPAL_API_BASE_URL=https://YOUR-DOMAIN.example/learning/api/v1
```

يلزم إعداد أسماء الحزم، الأيقونات، مفاتيح Android، حساب Apple وشهادات التوقيع قبل النشر. لا تضع أي مفتاح خادم أو دفع داخل التطبيق.
