# واجهة تطبيق الموبايل — منصة أوبال التعليمية API v1

المسار الأساسي: `/learning/api/v1/`

## المصادقة

يرسل التطبيق طلب `POST` إلى `auth/login/` بصيغة JSON:

```json
{"email":"learner@example.com","password":"...","device_name":"Android — Samsung"}
```

تُعاد قيمة `token` مرة واحدة، ثم ترسل في كل طلب:

```text
Authorization: Bearer olp_...
```

الرمز مخزن في قاعدة البيانات كبصمة فقط، وينتهي وفق `OPAL_LEARNING_API_TOKEN_DAYS`. تسجيل الخروج من `auth/logout/` يلغي الرمز الحالي.

## المسارات

- `GET me/`
- `GET courses/`
- `GET courses/<slug>/`
- `POST courses/<slug>/enroll/`
- `GET courses/<course_slug>/lessons/<lesson_slug>/`
- `POST courses/<course_slug>/lessons/<lesson_slug>/complete/`
- `GET courses/<course_slug>/assessments/<assessment_slug>/` — الأسئلة والخيارات دون الإجابة الصحيحة
- `POST courses/<course_slug>/assessments/<assessment_slug>/submit/`
- `GET notifications/`
- `POST notifications/<id>/read/`
- `GET certificates/`
- `GET subscription-plans/`
- `POST assistant/`

## تسليم الاختبار

```json
{"answers":{"12":"a","13":"c"}}
```

## تسليم الواجب

```json
{"answer_text":"نص الإجابة..."}
```

## أخطاء API

```json
{"ok":false,"error":{"code":"invalid_token","message":"..."}}
```

الأكواد المهمة: `authentication_required`, `invalid_token`, `rate_limited`, `account_locked`, `legal_acceptance_required`, `email_not_verified`, `subscription_required`, `submission_rejected`.

## متطلبات التطبيق الأصلي

- تخزين الرمز داخل Android Keystore / iOS Keychain فقط.
- عدم تخزين كلمة المرور.
- إلغاء الرمز عند تسجيل الخروج.
- احترام HTTP 401 و423 و429.
- استخدام HTTPS فقط.
- لا يُسمح للتطبيق بالاتصال بقاعدة البيانات مباشرة.

## مصدر Flutter المرفق

المصدر موجود في `mobile/opal_learning_app`. يقرأ عنوان API من `--dart-define=OPAL_API_BASE_URL=...` ويحفظ الرمز في `flutter_secure_storage`. لم يُبنَ أو يوقّع داخل بيئة إنشاء حزمة Django.

## حدود R20

R20 يوفر API مستقرة وواجهة ويب تقدمية قابلة للتثبيت على الهاتف. بناء ملف Android/iOS موقّع ونشره في المتاجر يحتاج مفاتيح توقيع وحسابات متاجر وسياسات خصوصية نهائية، ولا يمكن تضمين تلك الأسرار داخل حزمة تحديث الخادم.
