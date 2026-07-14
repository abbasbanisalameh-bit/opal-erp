# تركيب تحديث توحيد إدخال الطالب والمعلم وولي الأمر

هذا التحديث يبني فوق النسخة الحالية، ولا يحتوي قاعدة بيانات أو ميديا أو `staticfiles`.

## قبل التركيب

خذ نسخة احتياطية من `db.sqlite3` ومجلد `media`، ثم ارفع ملف ZIP إلى:

```text
/home/Opalschool2016/
```

## أوامر التركيب

```bash
cd /home/Opalschool2016
mkdir -p canonical_people_update
unzip -o OPAL_CANONICAL_PEOPLE_ENTRY_UPDATE_20260713.zip -d canonical_people_update
rsync -av \
  --exclude='db.sqlite3' --exclude='db.sqlite3-*' \
  --exclude='media/' --exclude='staticfiles/' \
  --exclude='.git/' --exclude='.env' \
  --exclude='venv/' --exclude='.venv/' \
  canonical_people_update/opal_school/ opal_school/

cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py migrate --noinput
python manage.py check
python manage.py collectstatic --noinput
python manage.py test
```

بعد نجاح الأوامر اضغط **Reload** من صفحة Web في PythonAnywhere.

## المداخل الرسمية بعد التحديث

- الطالب الجديد: `إدارة الطلاب ← تسجيل طالب`، وينتهي إلى `/admissions/register/` مهما كان الرابط القديم المستخدم.
- صف الطالب وشعبته وحالته: شاشة دورة حياة الطالب والقيد الأكاديمي فقط.
- المعلم: `إدارة المعلمين ← إضافة معلم` فقط، ثم إنشاء حسابه من ملف المعلم.
- ولي الأمر: يُنشأ مع تسجيل الطالب، وتُعدّل هويته من `إدارة أولياء الأمور ← ملف الأسرة ← تعديل بيانات ولي الأمر`.
- Django Admin يظل معطلًا كمدخل تشغيلي.

## ملاحظات السلامة

- لا تحذف الهجرة `admissions/0004_studentregistration_guardian_national_id.py`.
- التحديث لا يحذف البيانات القديمة، ولا يغير أرقام الطلاب أو المعلمين.
- رابط أرشفة الطالب القديم يحول إلى دورة الحياة ولا يغير الحالة مباشرة.
- بيانات الصف والشعبة في ملف الطالب أصبحت للعرض المتوافق؛ المصدر التشغيلي هو `Enrollment` النشط.
