# تركيب تحديث الهيكل الدراسي OPAL ERP

هذا التحديث يبني فوق النسخة الحالية فقط. لا يستبدل قاعدة البيانات أو الميديا ولا يحذف بيانات المدرسة.

## 1. فك ملف التحديث ونسخ الكود

```bash
cd /home/Opalschool2016
mkdir -p academic_structure_update
unzip -o OPAL_ACADEMIC_STRUCTURE_UPDATE_20260713.zip -d academic_structure_update
rsync -av \
  --exclude='db.sqlite3' --exclude='db.sqlite3-*' \
  --exclude='media/' --exclude='staticfiles/' \
  --exclude='.git/' --exclude='.env' \
  --exclude='venv/' --exclude='.venv/' \
  academic_structure_update/opal_school/ opal_school/
```

## 2. تشغيل الهجرة والفحص

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py migrate --noinput
python manage.py check
python manage.py collectstatic --noinput
python manage.py test
```

## 3. إعادة تحميل الموقع

من صفحة **Web** في PythonAnywhere اضغط **Reload**.

## طريقة الاستخدام

1. افتح **الشؤون الأكاديمية ← الهيكل الدراسي**.
2. أضف العام الدراسي مرة واحدة واجعله العام الحالي.
3. من شاشة الهيكل اختر العام، ثم أضف الصف والرسوم وعدد الشعب.
4. اترك عدد الشعب `1` إذا كان الصف شعبة واحدة؛ أو اختر العدد المطلوب لتنشأ الشعب تلقائيًا.
5. الروضة اختيارية: فعّل مربع **صف روضة** فقط عند إضافة صفوفها.
6. أضف المعلمين لاحقًا، ثم افتح **الشعب** واختر مربي الصف لكل شعبة.
7. عند تسجيل طالب تظهر فقط الصفوف المهيأة للعام الحالي، وتُحسب رسوم الصف تلقائيًا.

لا يُسمح بحذف صف أو شعبة مرتبطة برسوم أو شعب أو طلاب أو مواد؛ أوقفها بدلًا من الحذف للحفاظ على تاريخ النظام.
