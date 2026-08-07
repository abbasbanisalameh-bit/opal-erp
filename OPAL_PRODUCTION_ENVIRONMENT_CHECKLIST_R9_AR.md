# قائمة بيئة الإنتاج — OPAL 131.7 R9

## متغيرات PythonAnywhere الإلزامية

- `OPAL_SECRET_KEY`: مفتاح إنتاجي عشوائي طويل، ولا تستخدم قيمة التحقق أو القيمة الافتراضية.
- `OPAL_DEBUG=False`
- `OPAL_ALLOWED_HOSTS=opalschool2016.pythonanywhere.com`
- `OPAL_CSRF_TRUSTED_ORIGINS=https://opalschool2016.pythonanywhere.com`
- `OPAL_SECURE_SSL_REDIRECT=True`
- `OPAL_HSTS_SECONDS=31536000` بعد التأكد من أن HTTPS يعمل بصورة صحيحة.
- `OPAL_TIME_ZONE=Asia/Amman`

## بوابة ما قبل إعادة التحميل

```bash
cat OPAL_VERSION.txt
cat OPAL_RELEASE_NAME.txt
python -m json.tool OPAL_UPDATE_MANIFEST.json
python tools/validate_opal_update_131_source.py .
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py test
python manage.py collectstatic --clear --noinput
```

يجب أن تكون الهوية `OPAL Update 131.7 R9 - Production Readiness Closeout`، وأن تنتهي الاختبارات بصفر فشل وصفر خطأ.

## النسخ والاستعادة

قبل التركيب احفظ نسخًا منفصلة من الكود وقاعدة البيانات و`media/` وملف إعداد البيئة. لا تضع أيًا منها داخل ZIP التحديث. نفّذ `audit_backup_recovery` على نسخة أو مسار آمن، ثم أعد تحميل التطبيق ونفّذ فحص الدخول والتسجيل والدفع والحضور والعلامات والوثائق والانتقال السنوي.
