# OPAL Update 131.7 R26

## Core Snapshot Test Isolation Fix

- عزل استدعاء `connections.close_all()` داخل اختبارات لقطة أمان SQLite باستخدام mock.
- منع إغلاق اتصال قاعدة اختبار Django وما ينتج عنه من `Cannot operate on a closed database` في الاختبارات اللاحقة.
- اعتماد ملف إعداد اختبار منخفض الذاكرة داخل المصدر.
- لا تغييرات تشغيلية أو هجرات قاعدة بيانات.
