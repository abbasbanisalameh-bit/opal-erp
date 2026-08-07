# تثبيت OPAL Update 131.7 R6

1. أنشئ نسخة احتياطية من الكود وقاعدة البيانات وملفات الوسائط.
2. ارفع الحزمة كاملة إلى جذر المشروع؛ لا تنسخ ملفات منفردة.
3. فعّل البيئة الافتراضية ثم نفّذ:

   ```bash
   python manage.py check
   python manage.py makemigrations --check --dry-run
   python manage.py test core.test_update131_7_r6_runtime_stabilization_contract core.tests_operation_flow openemis_integration.tests core.tests_system_updates
   python manage.py collectstatic --clear --noinput
   ```

4. أعد تحميل تطبيق PythonAnywhere، ثم افتح مركز العمليات ولوحة الإدارة وكرر استيراد عينة OpenEMIS مرتين للتأكد من عدم إنشاء شعبة مكررة.

لا تتضمن الحزمة قاعدة بيانات أو وسائط أو بيئة افتراضية، ولا تتطلب هجرة جديدة.
