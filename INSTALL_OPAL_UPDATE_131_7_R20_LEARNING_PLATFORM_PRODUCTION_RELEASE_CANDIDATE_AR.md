# تركيب OPAL Update 131.7 R20

## Learning Platform Production Release Candidate

يُركب هذا التحديث فوق:

`OPAL Update 131.7 R19 - Grounded AI Assistant and Teacher Tools`

## ما يجمعه R20 في حزمة واحدة

- توثيق البريد وقبول الشروط والخصوصية.
- قفل مؤقت بعد محاولات الدخول الفاشلة وحدود طلبات مشتركة بين العمال.
- رموز API للأجهزة مخزنة كبصمة ومنتهية الصلاحية وقابلة للإلغاء.
- API v1 للدورات والدروس والتقدم والتقييمات والإشعارات والشهادات والمساعد.
- PWA آمنة قابلة للتثبيت، ولا تخزن صفحات الحساب أو الدفع في Cache.
- مصدر تطبيق Flutter أولي وظيفي داخل `mobile/opal_learning_app`، دون مفاتيح توقيع أو أسرار.
- خطط اشتراك بأسعار وعملات.
- أوامر دفع idempotent، تحصيل يدوي داخلي، ومحول بوابة خارجية مع webhook HMAC موقع.
- مركز جاهزية تشغيل داخل لوحة المدير ونقطة Health.
- أوامر نسخة احتياطية وتحقق من سلامتها.
- دعم PostgreSQL عبر متغيرات البيئة مع استمرار SQLite افتراضيًا.
- شروط استخدام وسياسة خصوصية أولية ودلائل تشغيل وAPI.

## قبل التركيب

1. تأكد أن R19 مركب وأن هجرته `0005` مطبقة.
2. خذ ZIP للكود ونسخة قاعدة البيانات الحالية.
3. لا تدخل بيانات جديدة أثناء التركيب والهجرة.
4. ثبّت الحزمة من مركز تحديثات OPAL.

## الأوامر الإلزامية بعد التركيب

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate

pip install -r requirements.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test learning_platform core.test_update131_7_r20_learning_production_release_contract
python manage.py test
python -m pip freeze > requirements-lock-r20.txt
python manage.py collectstatic --clear --noinput
```

ثم اضغط **Reload** من صفحة Web.

## فحص الجاهزية

افتح:

`منصة أوبال التعليمية ← جاهزية التشغيل`

وشغّل:

```bash
python manage.py verify_learning_production_readiness
```

بعد إعداد الإنتاج شغّل البوابة الصارمة:

```bash
python manage.py verify_learning_production_readiness --strict
```

لن تنجح البوابة الصارمة على SQLite أو مع قفل الإطلاق العام أو بدون SMTP وبوابة دفع خارجية.

## إعداد التشغيل الداخلي المؤقت

```text
OPAL_LEARNING_PAYMENT_ENABLED=True
OPAL_LEARNING_PAYMENT_PROVIDER=manual
OPAL_LEARNING_MANUAL_PAYMENT_ALLOWED=True
OPAL_LEARNING_PUBLIC_LAUNCH=False
```

هذا يسمح بإنشاء الطلب واعتماده يدويًا بعد تحصيله خارج النظام، لكنه لا يعني إطلاق دفع إلكتروني عام.

## إعداد الإطلاق العام

هيئ SMTP وفق دليل R18، ثم بوابة الدفع:

```text
OPAL_LEARNING_PAYMENT_ENABLED=True
OPAL_LEARNING_PAYMENT_PROVIDER=<provider-name>
OPAL_LEARNING_PAYMENT_CHECKOUT_URL=https://<provider>/checkout-sessions
OPAL_LEARNING_PAYMENT_API_KEY=<secret>
OPAL_LEARNING_PAYMENT_WEBHOOK_SECRET=<secret>
OPAL_LEARNING_PAYMENT_CURRENCY=JOD
OPAL_LEARNING_PUBLIC_LAUNCH=True
```

لا تضع أي مفتاح في الكود أو قاعدة البيانات.

## اختبار القبول الإلزامي

1. إنشاء خطة اشتراك بسعر وعملة معتمدين، ثم تسجيل متعلم جديد وقبول الشروط.
2. وصول بريد التوثيق واستخدامه مرة واحدة، وإجبار الحسابات القديمة على قبول السياسات بنفسها عند فتح الإطلاق العام.
3. فشل الدخول المتكرر ثم القفل المؤقت واستعادة الحساب.
4. إنشاء خطة وطلب دفع تجريبي في sandbox.
5. وصول webhook صحيح وتفعيل اشتراك واحد فقط حتى عند تكرار الحدث.
6. تسجيل المتعلم في دورة وإكمال درس واختبار وواجب وشهادة.
7. دخول API من جهاز تجريبي ثم إلغاء الرمز وتأكد من HTTP 401.
8. تثبيت PWA على هاتف Android وفتحها بعد إعادة التشغيل.
9. إنشاء نسخة:

```bash
python manage.py backup_learning_platform
python manage.py verify_learning_backup /path/to/backup.zip
```

ثم نفّذ استعادة فعلية للنسخة في قاعدة معزولة؛ علامة التحقق البنيوي لا تستبدل اختبار الاستعادة.

10. فحص Error log وعدم وجود HTTP 500 أو أخطاء قاعدة مقفلة.

## حدود لا تستطيع حزمة الخادم تنفيذها وحدها

- اختيار مزود دفع متاح قانونيًا وتوقيع عقده والحصول على بيانات sandbox/production.
- إنشاء حسابات Apple/Google ومفاتيح توقيع التطبيق وبناء النسخ النهائية ونشرها في المتاجر؛ مصدر Flutter فقط مرفق بالحزمة.
- اعتماد النص القانوني النهائي للخصوصية والاسترداد من مالك المنصة.
- إنشاء PostgreSQL خارجي ونقل بيانات الإنتاج إليه.

R20 يوفر الكود والعقود والبوابات اللازمة، لكن لا يجوز وصف المنصة بأنها جاهزة فعليًا قبل توفير هذه المدخلات ونجاح الاختبارات على الخادم.
