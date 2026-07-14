# تركيب OPAL ERP V9.0 — Executive Dashboard

هذه الحزمة لا تحتوي على قاعدة بيانات أو ملفات media، ولا تنشئ migrations جديدة.

بعد فك الحزمة ونسخها إلى المشروع، نفّذ:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

ثم أعد تحميل تطبيق الويب واختبر الصفحة الرئيسية بحساب المدير، وتصدير CSV.
