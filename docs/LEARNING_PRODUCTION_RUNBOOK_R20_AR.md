# دليل إطلاق منصة أوبال التعليمية — R20

## قرار الاعتماد

لا تُفتح المنصة للجمهور قبل نجاح:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test learning_platform core.test_update131_7_r20_learning_production_release_contract
python manage.py test
python manage.py verify_learning_production_readiness --strict
python manage.py collectstatic --clear --noinput
```

ثم اختبار قبول يدوي للمدير والمدرس والمتعلم وAPI والدفع والبريد.

## متغيرات البريد

راجع دليل R18. يجب تفعيل `OPAL_LEARNING_EMAIL_ENABLED=True` ووضع SMTP في البيئة فقط.

## متغيرات الدفع

```text
OPAL_LEARNING_PAYMENT_ENABLED=True
OPAL_LEARNING_PAYMENT_PROVIDER=<provider-name>
OPAL_LEARNING_PAYMENT_CHECKOUT_URL=https://provider.example/checkout-sessions
OPAL_LEARNING_PAYMENT_API_KEY=<secret>
OPAL_LEARNING_PAYMENT_WEBHOOK_SECRET=<secret>
OPAL_LEARNING_PAYMENT_CURRENCY=JOD
OPAL_LEARNING_PAYMENT_TIMEOUT=20
```

وضع التحصيل اليدوي للتشغيل الداخلي:

```text
OPAL_LEARNING_PAYMENT_ENABLED=True
OPAL_LEARNING_PAYMENT_PROVIDER=manual
OPAL_LEARNING_MANUAL_PAYMENT_ALLOWED=True
```

لا يُعد هذا دفعًا إلكترونيًا عامًا؛ يجب مطابقة المرجع يدويًا قبل الضغط على «اعتماد الدفع».

## الحماية

```text
OPAL_LEARNING_REQUIRE_EMAIL_VERIFICATION=True
OPAL_LEARNING_LOGIN_MAX_ATTEMPTS=5
OPAL_LEARNING_LOGIN_LOCK_MINUTES=15
OPAL_LEARNING_LOGIN_RATE_LIMIT=10
OPAL_LEARNING_API_RATE_LIMIT=120
OPAL_LEARNING_API_TOKEN_DAYS=30
```

## النسخ

```bash
python manage.py backup_learning_platform
python manage.py verify_learning_backup /path/to/opal_learning_backup_YYYYMMDD_HHMMSS.zip
```

يُنشئ أمر التحقق علامة `.verified.json` تستخدمها بوابة الجاهزية. هذه علامة تحقق بنيوي فقط؛ اختبر استعادة `learning_platform.json` أو صورة SQLite في بيئة معزولة، ثم سجل نتيجة الاستعادة يدويًا قبل الإطلاق.

## الإطلاق المرحلي

1. حسابات تجريبية فقط.
2. 5–20 مستخدمًا حقيقيًا بموافقة واضحة.
3. مراقبة Error log وأخطاء `database is locked`.
4. الانتقال إلى PostgreSQL قبل الإطلاق الواسع عند ظهور ضغط تزامن.
5. تفعيل بوابة الدفع الخارجية بعد اختبار sandbox والتوقيع والـwebhook.
6. اعتماد سياسة الخصوصية والاسترداد والاحتفاظ بالبيانات.


## تطبيق Flutter المرفق

يوجد المصدر في `mobile/opal_learning_app`. شغله أولًا على بيئة Sandbox:

```bash
cd mobile/opal_learning_app
flutter pub get
flutter run --dart-define=OPAL_API_BASE_URL=https://YOUR-DOMAIN/learning/api/v1
```

لا تنشر APK/AAB/IPA قبل مراجعة اسم الحزمة، الأيقونات، سياسة الخصوصية، التخزين الآمن، واختبارات الأجهزة الفعلية.
