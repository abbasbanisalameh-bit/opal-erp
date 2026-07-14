# تثبيت تحديث هوية OPAL لصفحات التشغيل المؤسسي

يعدل هذا التحديث الشكل فقط ولا يغير قاعدة البيانات أو منطق العمل.

الملفات المعدلة:
- `static/css/opal_erp.css`
- جميع قوالب `templates/enterprise_ops/`

بعد النسخ نفذ:

```bash
python manage.py check
python manage.py collectstatic --noinput
```

ثم Reload من صفحة Web في PythonAnywhere.
