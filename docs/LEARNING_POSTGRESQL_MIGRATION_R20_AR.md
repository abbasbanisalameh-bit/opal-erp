# انتقال OPAL إلى PostgreSQL قبل الإطلاق الواسع

R20 لا ينقل قاعدة البيانات تلقائيًا لأن العملية تحتاج قاعدة مستهدفة ونسخة رجوع ونافذة توقف. الكود يدعم PostgreSQL عند تهيئة البيئة.

## المتغيرات

```text
OPAL_DB_ENGINE=postgresql
OPAL_DB_NAME=<database>
OPAL_DB_USER=<user>
OPAL_DB_PASSWORD=<secret>
OPAL_DB_HOST=<host>
OPAL_DB_PORT=5432
OPAL_DB_SSL_REQUIRED=True
OPAL_DB_CONN_MAX_AGE=60
```

## مسار آمن مختصر

1. أوقف إدخال البيانات وحدد نافذة صيانة.
2. خذ نسخة SQLite ونسخة `dumpdata` واختبر فتحهما.
3. أنشئ PostgreSQL بترميز UTF-8 ومستخدم محدود الصلاحيات.
4. ثبّت `psycopg[binary]` من `requirements.txt`.
5. نفّذ الهجرات على القاعدة الجديدة.
6. انقل البيانات بأداة موثوقة أو `dumpdata/loaddata` بعد اختبار العلاقات والتسلسلات.
7. شغّل `check` والاختبارات وقبول التسجيل والدفع والشهادات.
8. لا تحذف SQLite قبل اكتمال المراجعة ووجود نسخة رجوع.

لا تستخدم `migrate --fake` ولا تبدّل قاعدة الإنتاج دون اختبار استعادة كامل.
