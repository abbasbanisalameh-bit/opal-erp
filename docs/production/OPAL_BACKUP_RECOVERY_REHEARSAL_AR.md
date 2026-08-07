# OPAL ERP — النسخ الاحتياطي وبروفة الاستعادة قبل التشغيل

## الهدف
إثبات أن نسخة قاعدة البيانات قابلة للإنشاء والقراءة والاستعادة في مكان معزول قبل إدخال البيانات الحقيقية.

## قواعد الأمان
- لا تتم الاستعادة فوق قاعدة البيانات الحية.
- لا يتم حذف أي سجل.
- تحفظ النسخة خارج مجلد المشروع افتراضيًا داخل `opal_private_backups/recovery_rehearsal`.
- يجب حفظ الكود على GitHub قبل التشغيل الفعلي.
- عند استخدام قاعدة غير SQLite، تستخدم أداة مزود قاعدة البيانات وتجرى الاستعادة في قاعدة منفصلة.

## التنفيذ
```bash
python manage.py audit_backup_recovery \
  --output docs/production/backup_recovery_report.json
```

للفحص الصارم:
```bash
python manage.py audit_backup_recovery \
  --strict \
  --output docs/production/backup_recovery_report.json
```

يمكن تحديد مجلد خاص:
```bash
python manage.py audit_backup_recovery \
  --backup-dir /home/USER/opal_private_backups/recovery_rehearsal
```

## الاعتماد
لا يبدأ إدخال البيانات الحقيقية قبل نجاح فحص الجاهزية رقم 76 ونجاح بروفة النسخ والاستعادة رقم 77، مع حفظ نسخة الكود في GitHub.
