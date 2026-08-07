# تركيب OPAL Update 113.0

1. افتح **إعدادات النظام ← مركز تحديثات النظام** بحساب المدير الأعلى.
2. ارفع الملف `OPAL_UPDATE_113_CANONICAL_READINESS_GATE_FULL.zip`.
3. انتظر تنفيذ الفحص والترحيلات وتجميع الملفات وإعادة تحميل الموقع تلقائيًا.
4. بعد نجاح التركيب، شغّل فحص الجاهزية الرسمي من Console عند الحاجة:

```bash
python manage.py verify_core_readiness --allow-empty
```

وقبل إدخال البيانات الحقيقية استخدم الفحص الصارم بعد ضبط إعدادات الإنتاج:

```bash
python manage.py verify_core_readiness --strict-warnings --output reports/production-readiness.json
```

لا توجد Migration جديدة ولا يحتاج التحديث إلى `--fake` أو أي تعديل يدوي لقاعدة البيانات.
