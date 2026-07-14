# تركيب تحديث OPAL ERP SAFE CONSOLIDATION

## 1. نسخة احتياطية للكود الحالي

```bash
cd /home/Opalschool2016/opal_school
cp -a opal_school opal_school_before_safe_consolidation
```

## 2. فك الحزمة ونسخ الكود دون قاعدة البيانات أو الميديا

```bash
mkdir -p /home/Opalschool2016/opal_safe_update
unzip -o /home/Opalschool2016/OPAL_ERP_SAFE_CONSOLIDATION_20260713.zip \
  -d /home/Opalschool2016/opal_safe_update

rsync -av --delete \
  --exclude='db.sqlite3' --exclude='db.sqlite3-*' \
  --exclude='media/' --exclude='staticfiles/' \
  --exclude='.git/' --exclude='.env' \
  --exclude='venv/' --exclude='.venv/' \
  /home/Opalschool2016/opal_safe_update/opal_school/ \
  /home/Opalschool2016/opal_school/opal_school/
```

خيار `--delete` مقصود لإزالة الملفات القديمة التي أثبت التدقيق أنها غير
مستخدمة، ولا يمس قاعدة البيانات أو الميديا أو Git بسبب الاستثناءات أعلاه.

## 3. إعداد بيئة موقع المدرسة

```text
OPAL_SECRET_KEY=<مفتاح طويل وعشوائي>
OPAL_DEBUG=False
OPAL_ENABLE_OPENEMIS=False
OPAL_ENABLE_DEVELOPMENT_CENTER=False
```

## 4. الفحص والترحيل

```bash
cd /home/Opalschool2016/opal_school/opal_school
source /home/Opalschool2016/opal_school/venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py test
python manage.py verify_core_readiness --allow-empty
```

الترحيلات تنقل علاقات `ParentProfile` القديمة إلى `Family/FamilyStudent`،
وتنقل الإشعارات إلى `enterprise_ops.Notification`، كما تحول أرصدة الطالب
القديمة إلى فواتير ودفعات قبل حذف الحقول القديمة.

## 5. إعادة تحميل الموقع

من صفحة **Web** في PythonAnywhere اضغط **Reload**، ثم اختبر تسجيل طالب، حساب
الأسرة، السجل المالي، دفعة الإخوة، الحضور، الامتحانات، والوثائق.

## تشغيل مركز التطوير في موقع منفصل

استخدم ملف WSGI مستقلًا يشير إلى:

```python
from config.wsgi_development import application
```

ثم نفذ لهذا الموقع فقط:

```bash
OPAL_ENABLE_DEVELOPMENT_CENTER=True python manage.py migrate --noinput
OPAL_ENABLE_DEVELOPMENT_CENTER=True python manage.py seed_development_center
```

لا تضف متغير تفعيل مركز التطوير إلى موقع المدرسة الإنتاجي.
