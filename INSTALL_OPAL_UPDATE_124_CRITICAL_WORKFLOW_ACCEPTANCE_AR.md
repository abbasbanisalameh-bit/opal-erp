# تركيب OPAL Update 124

يُركّب هذا الملف من **مركز تحديثات OPAL** فوق Update 123.

ينفذ مركز التحديث تلقائيًا:

- `python manage.py check`
- `python manage.py migrate`
- `collectstatic --noinput`
- إعادة تحميل الموقع

لا توجد Migration جديدة ولا حاجة إلى حذف أو تصفير البيانات.

## الفحص بعد التركيب

من Bash Console داخل مجلد المشروع شغّل:

```bash
python manage.py audit_critical_workflows
```

- **الأخطاء** تعني وجود تناقض فعلي يجب إصلاحه قبل البيانات الحقيقية.
- **التحذيرات** غالبًا تخص سجلات قديمة أُوقفت قبل اعتماد دورة إنهاء الخدمة الرسمية.
- الأمر للقراءة فقط ولا يعدل أي سجل.

ثم شغّل البوابة العامة:

```bash
python manage.py audit_final_stability
```
