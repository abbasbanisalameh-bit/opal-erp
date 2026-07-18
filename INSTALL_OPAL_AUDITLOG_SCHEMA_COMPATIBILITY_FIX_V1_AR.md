# تثبيت OPAL_AUDITLOG_SCHEMA_COMPATIBILITY_FIX_V1

1. من مركز تحديثات النظام ارفع ملف ZIP.
2. اختر استعادة/تثبيت التحديث.
3. انتظر نجاح:
   - python manage.py check
   - python manage.py migrate
   - python manage.py collectstatic --noinput
4. أعد تحميل تطبيق الويب من PythonAnywhere.
5. اختبر صفحة التشغيل المؤسسي وصفحة الإعدادات.

## فحص يدوي بعد التركيب
```bash
cd /home/Opalschool2016/opal_school
python manage.py check
python manage.py showmigrations core
python manage.py shell -c "from core.models import AuditLog; x=AuditLog.objects.create(action='view',model_name='post_install_check',description='اختبار بعد التحديث'); print(x.pk, repr(x.request_id), x.result); x.delete()"
```

لا ينفذ التحديث حذفًا للبيانات ولا يعكس ترحيلات التحديث السابق.
