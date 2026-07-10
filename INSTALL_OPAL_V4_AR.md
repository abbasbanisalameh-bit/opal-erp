# تثبيت OPAL ERP V4 على PythonAnywhere

## 1. نسخة احتياطية

من Bash Console:

```bash
cd /home/Opalschool2016/opal_school
cp -a opal_school opal_school_backup_before_v4
```

## 2. رفع وفك النسخة

ارفع ملف الإصدار إلى `/home/Opalschool2016/`، ثم فكّه في مجلد جديد أولًا. لا تستبدل النسخة العاملة قبل أخذ النسخة الاحتياطية.

## 3. متغيرات البيئة

في ملف WSGI أو إعدادات البيئة أضف قبل تحميل Django:

```python
import os
os.environ["OPAL_SECRET_KEY"] = "ضع-هنا-مفتاحا-طويلا-وعشوائيا"
os.environ["OPAL_DEBUG"] = "False"
```

يمكن إنشاء مفتاح جديد داخل البيئة الافتراضية:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

لا تضع المفتاح داخل GitHub.

## 4. أوامر التحقق

```bash
cd /home/Opalschool2016/opal_school/opal_school
source /home/Opalschool2016/opal_school/venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py test admissions.tests -v 2
```

## 5. إعادة تحميل الموقع

من تبويب Web في PythonAnywhere اضغط Reload.

## 6. التراجع عند الحاجة

```bash
cd /home/Opalschool2016/opal_school
mv opal_school opal_school_v4_failed
mv opal_school_backup_before_v4 opal_school
```

ثم اضغط Reload من تبويب Web.
