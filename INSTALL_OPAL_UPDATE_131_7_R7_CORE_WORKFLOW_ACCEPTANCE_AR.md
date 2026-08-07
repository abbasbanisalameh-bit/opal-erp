# تثبيت OPAL Update 131.7 R7

هذه الحزمة تراكمية وتشمل R6. بعد أخذ نسخة احتياطية، ارفع الحزمة كاملة إلى جذر المشروع ثم نفّذ:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.tests_canonical_entries core.tests_update83_integrated enterprise_ops.tests_communication dashboard.test_workflow_contract
python manage.py collectstatic --clear --noinput
```

أعد تحميل تطبيق PythonAnywhere، ثم اختبر تهيئة عام جديد، مراجعة العلامات، توليد راتب يتضمن سلفة وغيابًا معتمدًا، دمج شعبتين، ولوحة رضا المستخدمين.

لا توجد هجرة جديدة ولا نموذج طالب أو رصيد مالي موازٍ.
