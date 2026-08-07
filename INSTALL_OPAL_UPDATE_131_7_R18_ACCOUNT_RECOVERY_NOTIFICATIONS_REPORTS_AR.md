# دليل تركيب OPAL Update 131.7 R18

## قبل التركيب

1. تأكد أن R17 مركب وأن الاختبارات والواجبات والشهادات تعمل.
2. خذ نسخة ZIP من كود المشروع، ونسخة قاعدة البيانات إذا بدأت بإدخال بيانات حقيقية.
3. ارفع حزمة R18 وثبّتها من مركز التحديثات.

## الأوامر المطلوبة بعد التركيب

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate

python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test learning_platform core.test_update131_7_r18_recovery_notifications_reports_contract
python manage.py collectstatic --clear --noinput
```

بعد نجاح الأوامر اضغط **Reload** من صفحة Web في PythonAnywhere.

## إعداد البريد الإلكتروني

الاستعادة الذاتية تعمل بالبريد فقط بعد إضافة متغيرات SMTP في إعدادات بيئة PythonAnywhere. إرسال البريد معطل افتراضيًا. مثال الأسماء المطلوبة دون وضع كلمات السر داخل الكود:

```text
OPAL_LEARNING_EMAIL_ENABLED=True
OPAL_LEARNING_EMAIL_HOST=<smtp-host>
OPAL_LEARNING_EMAIL_PORT=587
OPAL_LEARNING_EMAIL_USER=<smtp-user>
OPAL_LEARNING_EMAIL_PASSWORD=<smtp-password>
OPAL_LEARNING_EMAIL_USE_TLS=True
OPAL_LEARNING_EMAIL_USE_SSL=False
OPAL_LEARNING_DEFAULT_FROM_EMAIL=<verified-sender>
OPAL_LEARNING_PASSWORD_RESET_MINUTES=60
```

إذا لم تهيئ SMTP، افتح: **المنصة → الحسابات والمدرسون → طلبات الاستعادة**، ثم أنشئ كلمة مرور مؤقتة للمستخدم.

## اختبار القبول

### استعادة الحساب

1. من صفحة دخول المنصة اضغط «نسيت كلمة المرور؟».
2. أرسل بريد حساب متعلم تجريبي.
3. تأكد من ظهور الطلب في مركز الاستعادة، وحالة الإرسال «تم الإرسال» عند تهيئة SMTP.
4. افتح الرابط، عيّن كلمة مرور جديدة، ثم تأكد أن كلمة المرور القديمة وجميع الجلسات القديمة لم تعد صالحة.
5. جرّب حسابًا آخر من الإدارة، وأنشئ كلمة مرور مؤقتة وتأكد أنها تظهر مرة واحدة فقط.

### الإشعارات

1. فعّل بطاقة اشتراك لمتعلم وسجله في دورة.
2. أرسل واجبًا وتأكد من وصول إشعار للمدرس.
3. صحح الواجب وتأكد من وصول إشعار للمتعلم.
4. أكمل الدورة وتأكد من إشعار الشهادة.
5. افتح مركز الإشعارات، اقرأ إشعارًا، ثم استخدم «تعليم الكل كمقروء».

### التقارير

1. افتح «التقارير التشغيلية» بحساب مدير OPAL.
2. غيّر الفترة والمادة والدورة وتأكد من تغير المؤشرات والجداول.
3. تحقق من ظهور الاشتراكات القريبة من الانتهاء والواجبات المنتظرة.
4. صدّر CSV وافتحه وتأكد من العربية والبيانات المرشحة.

## التراجع

إذا فشلت الهجرة أو الاختبارات، لا تُدخل بيانات جديدة. استعد نسخة الكود السابقة وقاعدة البيانات الاحتياطية، ثم أرسل آخر Traceback كامل.
