# OPAL Update 131.7 R27

## FileResponse Test Connection Isolation Fix

- أصلح خطأ `Cannot operate on a closed database` في اختبار تنزيل وحذف ملفات النسخ الاحتياطية.
- استبدل إغلاق `FileResponse` كاملًا بإغلاق تدفق ملف ZIP فقط.
- أبقى طلب التنزيل وطلب الحذف مستقلين دون إطلاق `request_finished` داخل الاختبار.
- لا تغييرات على قاعدة الإنتاج أو بيانات المستخدمين أو وظائف النظام التشغيلية.
- لا توجد هجرة قاعدة بيانات.
