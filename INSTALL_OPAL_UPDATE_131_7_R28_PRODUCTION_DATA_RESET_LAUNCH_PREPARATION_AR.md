# دليل تركيب OPAL Update 131.7 R28

## قبل التركيب

- خط الأساس المطلوب: `OPAL Update 131.7 R27 - FileResponse Test Connection Isolation Fix`.
- تأكد أن الكود الحالي محفوظ على GitHub.
- لا تدخل بيانات جديدة أثناء تركيب التحديث أو تنفيذ التهيئة.
- التحديث لا ينفذ الحذف عند التركيب؛ الحذف يبدأ فقط من صفحة المعاينة وبالتأكيد الصريح.

## بعد التركيب

افتح Bash في PythonAnywhere ونفّذ:

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate

python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test \
  core.test_update131_7_r28_production_data_reset \
  core.test_update131_7_r28_production_launch_preparation_contract \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput
python manage.py collectstatic --clear --noinput
```

الهجرة الجديدة المتوقعة:

```text
core.0014_productiondataresetrun
```

ثم من صفحة **Web** اضغط **Reload**.

## تنفيذ التنظيف

1. ادخل بحساب مدير النظام الأعلى.
2. افتح: **إعدادات النظام ← تهيئة التشغيل الفعلي**.
3. راجع جميع أعداد السجلات التي ستُحذف، وما سيبقى محفوظًا.
4. فعّل خانة الإقرار.
5. اكتب العبارة حرفيًا:

```text
تهيئة التشغيل الفعلي
```

6. نفّذ العملية وانتظر فتح التقرير النهائي.
7. تأكد أن كل قيم «المتبقي» تساوي صفرًا.

## اختبار القبول بعد التنفيذ

- دخول المدير الحالي يعمل.
- بيانات المدرسة والفروع ظاهرة.
- الأدوار ومصفوفة الصلاحيات موجودة.
- لا يوجد طلاب أو أولياء أمور أو معلمون أو معاملات مالية.
- لا توجد حسابات أو دورات أو اشتراكات في منصة التعلم.
- يمكن إنشاء العام الدراسي والصفوف والشعب والمواد الجديدة.

## التراجع

R28 لا ينشئ نسخة قاعدة بيانات تلقائيًا. إذا نُفذ الحذف فلا يمكن استعادة البيانات المحذوفة من داخل النظام. التراجع عن الكود وحده لا يعيد سجلات قاعدة البيانات.
