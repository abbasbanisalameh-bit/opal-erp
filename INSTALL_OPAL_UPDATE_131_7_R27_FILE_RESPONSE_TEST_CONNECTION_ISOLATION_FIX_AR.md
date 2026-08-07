# تركيب OPAL Update 131.7 R27

## FileResponse Test Connection Isolation Fix

يُركب هذا التحديث فوق R26. وهو إصلاح لاختبار النواة فقط، ولا يغيّر قاعدة البيانات أو حسابات المستخدمين أو وظائف تنزيل النسخ الاحتياطية وحذفها في التشغيل الفعلي.

## السبب الذي يعالجه

كان اختبار `BackupFileActionsTests.test_download_and_delete_version_file` يستدعي:

```python
download_response.close()
```

إغلاق استجابة Django بهذه الطريقة يطلق إشارة `request_finished`، فتُغلق وصلة قاعدة اختبار Django قبل طلب الحذف التالي داخل الاختبار نفسه. لذلك ظهر:

```text
django.db.utils.ProgrammingError: Cannot operate on a closed database
```

R27 يغلق تدفق ملف ZIP وحده عبر `file_to_stream.close()`، من دون إغلاق الاستجابة أو اتصال قاعدة الاختبار.

## بعد التركيب

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
```

لا توجد هجرة جديدة، والمتوقع `No migrations to apply`.

## الاختبار المستهدف

```bash
rm -f /tmp/opal_r26_low_memory_test.sqlite3
python manage.py test \
core.tests_system_updates.BackupFileActionsTests.test_download_and_delete_version_file \
core.test_update131_7_r27_file_response_test_connection_fix_contract \
--settings=config.settings_test_low_memory \
--verbosity 1 --noinput
```

المطلوب `OK`.

## اختبار core

```bash
python manage.py test core \
--settings=config.settings_test_low_memory \
--verbosity 1 --noinput \
> /tmp/core_r27_low_memory.txt 2>&1

tail -n 120 /tmp/core_r27_low_memory.txt
```

لا تنفّذ `collectstatic` أو Reload قبل نجاح الاختبار المستهدف ثم اختبار `core`.
