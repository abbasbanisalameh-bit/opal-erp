# تركيب OPAL Update 131.7 R26

## Core Snapshot Test Isolation Fix

يُركب هذا التحديث فوق R25. وهو إصلاح لاختبارات النواة فقط، ولا يغيّر بيانات المستخدمين أو الطلبة أو الدورات أو الاشتراكات أو الصلاحيات.

## ما يعالجه

- يمنع اختبارات نقطة أمان SQLite من إغلاق اتصال قاعدة اختبار Django المشتركة.
- يعالج الخطأ الذي ظهر بعد نجاح معظم اختبارات `core`:

```text
ProgrammingError: Cannot operate on a closed database
```

- يضيف `config/settings_test_low_memory.py` رسميًا إلى المشروع حتى لا يحتاج إلى إنشائه يدويًا بعد كل تحديث.
- لا توجد هجرة قاعدة بيانات جديدة.

## بعد التركيب

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
```

## اختبار الإصلاح المستهدف

```bash
rm -f /tmp/opal_r26_low_memory_test.sqlite3
python manage.py test \
core.tests_system_updates.DatabaseSafetySnapshotTests \
core.test_update131_7_r26_core_snapshot_test_isolation_contract \
--settings=config.settings_test_low_memory \
--verbosity 1 --noinput
```

## اختبار core كاملًا

```bash
python manage.py test core \
--settings=config.settings_test_low_memory \
--verbosity 1 --noinput \
> /tmp/core_r26_low_memory.txt 2>&1

tail -n 120 /tmp/core_r26_low_memory.txt
```

النتيجة المطلوبة هي `OK`. لا تنفّذ `collectstatic` أو Reload قبل نجاح الاختبار المستهدف ثم اختبار `core` كاملًا.
