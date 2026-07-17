# تركيب تحديث إغلاق النواة والجاهزية للتشغيل

**الإصدار:** `OPAL_FINAL_CORE_COMPLETION_AND_PRODUCTION_READINESS_20260717_V1`

## قبل التركيب

1. احفظ نسخة كود من **إعدادات النظام ← مركز تحديثات النظام**.
2. احفظ نسخة منفصلة من `db.sqlite3` وملفات `media`.
3. تأكد أن تحديث `OPAL_LOGIN_PERFORMANCE_STABILITY_20260717_V1` هو النسخة العاملة.
4. لا تستبدل قاعدة البيانات أو `media` بما داخل الحزمة؛ الحزمة مصدر كود فقط.

## التركيب من مركز التحديثات

1. ارفع ملف `OPAL_FINAL_CORE_COMPLETION_PRODUCTION_READINESS_CURRENT_READY_20260717.zip`.
2. اضغط **رفع التحديث والتحقق منه**.
3. اختر الإصدار ثم اضغط **استعادة**.
4. ينتظر المركز نجاح `check` ثم `migrate` ثم `collectstatic`.
5. من صفحة **Web** في PythonAnywhere اضغط **Reload**.

## إعدادات الإنتاج المطلوبة

اضبط القيم التالية في بيئة تشغيل PythonAnywhere قبل الاعتماد الفعلي:

```text
OPAL_SECRET_KEY=<مفتاح عشوائي طويل وسري>
OPAL_DEBUG=False
OPAL_ALLOWED_HOSTS=opalschool2016.pythonanywhere.com
OPAL_CSRF_TRUSTED_ORIGINS=https://opalschool2016.pythonanywhere.com
OPAL_SECURE_SSL_REDIRECT=True
OPAL_HSTS_SECONDS=0
```

ابدأ بقيمة `OPAL_HSTS_SECONDS=0`. بعد التحقق من أن النطاق يعمل دائمًا عبر HTTPS
ولا توجد روابط أو نطاقات فرعية تعتمد HTTP، يمكن رفعها إلى `31536000`.

## أوامر التحقق

من مجلد المشروع وبعد تفعيل البيئة الافتراضية:

```bash
python manage.py check
python manage.py migrate --noinput
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
python manage.py test
```

لنسخة جديدة أو خالية:

```bash
python manage.py verify_core_readiness --allow-empty
```

بعد إعداد بيانات المدرسة والحساب الإداري والعام الحالي:

```bash
python manage.py verify_core_readiness
```

ولمنع الاعتماد عند وجود أي تحذير:

```bash
python manage.py verify_core_readiness --strict-warnings
```

## اختبار دورة العام

1. أنشئ العام الجديد من **الأكاديميات ← الأعوام ← إضافة عام جديد**.
2. جهز صفوفه وشعبه ورسومه ثم اضغط **تفعيل**.
3. من **حركات الطلاب** نفذ الترفيع أو التخريج الجماعي للعام القديم.
4. أغلق جميع امتحانات العام القديم وتأكد أنها مقفلة.
5. افتح **فحص وإغلاق** أمام العام القديم، عالج الموانع ثم أكد الإغلاق.
6. افتح حساب ولي أمر وتأكد أن نتائج العام المغلق ما زالت ظاهرة.
7. تأكد أن تحصيل فاتورة قديمة غير مكتملة ما زال ممكنًا.

## الاسترجاع

ترحيل الإغلاق يضيف حقولًا فقط. للاسترجاع الكامل أعد نسخة الكود وقاعدة البيانات
اللّتين حُفظتا قبل التركيب، ثم شغّل `collectstatic` واضغط **Reload**.
