# تركيب OPAL ERP V7.1 Patch

1. فك الضغط في مجلد مؤقت.
2. انسخ محتويات الحزمة إلى جذر مشروع Django مع الحفاظ على قاعدة البيانات وmedia و.env.
3. نفّذ:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

4. أعد تحميل الموقع من صفحة Web في PythonAnywhere.
5. اختبر صفحة Student 360 لطالب لديه تسجيل وفواتير وحضور وعلامات.
