# تثبيت OPAL Update 131.7 R8

هذه حزمة تراكمية تشمل R6 وR7. بعد النسخ الاحتياطي، ارفع الحزمة كاملة ثم نفّذ:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py collectstatic --clear --noinput
```

لا تعِد ملفات JavaScript أو قوالب customizer قديمة من نسخة سابقة؛ سجل الإحلال المرفق يوضح العقود المتقاعدة ومصادرها البديلة.

لا تتطلب الحزمة أي هجرة قاعدة بيانات.
