# تقرير تحقق R36.1

## سبب الإصلاح
أظهر GitHub Actions ست ملاحظات `prefer_const_constructors` في `mobile/opal_learning_app/lib/main.dart` عند الأسطر المحيطة بكتلة `cardTheme`، ثم أنهى `flutter analyze` برمز خروج 1.

## التعديل
تم تغيير:

```dart
cardTheme: CardThemeData(
```

إلى:

```dart
cardTheme: const CardThemeData(
```

وبذلك تصبح المنشئات الداخلية ضمن سياق ثابت أيضًا.

## سلامة النطاق
- لا تغيير على قاعدة البيانات.
- لا Migration جديدة.
- لا تغيير على API أو SSO أو الصلاحيات.
- لا تغيير على شعار R36 أو ألوانه أو الرسائل الترحيبية.
- لا تغيير على رقم التطبيق؛ يبقى `1.3.0+39`.
