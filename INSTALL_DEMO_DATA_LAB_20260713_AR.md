# تركيب مختبر البيانات التجريبية الآمن

الحزمة لا تحتوي قاعدة بيانات أو ميديا أو `staticfiles`، وتبني فوق تحديث توحيد الطالب والمعلم وولي الأمر.

```bash
cd /home/Opalschool2016
mkdir -p demo_data_lab_update
unzip -o OPAL_SAFE_DEMO_DATA_LAB_UPDATE_20260713.zip -d demo_data_lab_update
rsync -av \
  --exclude='db.sqlite3' --exclude='db.sqlite3-*' \
  --exclude='media/' --exclude='staticfiles/' \
  --exclude='.git/' --exclude='.env' \
  --exclude='venv/' --exclude='.venv/' \
  demo_data_lab_update/opal_school/ opal_school/

cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py migrate --noinput
python manage.py check
python manage.py collectstatic --noinput
python manage.py test
```

ثم اضغط **Reload** من صفحة Web في PythonAnywhere.

## التشغيل من الموقع

اذهب إلى **إعدادات النظام ← مختبر البيانات التجريبية**. الزران يظهران لمدير النظام الأعلى فقط:

- **إضافة بيانات تجريبية**: يضيف أو يستكمل 100 طالب و20 معلمًا.
- **تصفير البيانات التجريبية**: يحذف السجلات الموسومة كتجريبية فقط.

## التشغيل من Bash Console

لإنشاء البيانات وربط السجلات بالمستخدم الإداري `abbas`:

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py seed_demo_school --students 100 --teachers 20 --user abbas
```

لحذف البيانات التجريبية فقط:

```bash
python manage.py reset_demo_school --yes
```

الأمر الأخير لا يحذف الطلاب أو المعلمين الحقيقيين، ولا يحذف إعدادات المدرسة والصفوف والشعب.

## البيانات التي يتم تجهيزها

- 100 طالب، 50 أسرة وحساب ولي أمر، قيد أكاديمي ورسوم وفاتورة ودفعة وإيصال لكل طالب.
- حضور خمسة أيام، علامات خمس مواد، ووثيقة وإثبات طالب لكل طالب.
- 20 معلمًا مع حسابات دخول ورواتب شهرية ووثيقتين لكل معلم.
- تكليفات تدريسية، مربي صف، خمس مواد لكل صف، جدول أسبوعي من 250 حصة.
