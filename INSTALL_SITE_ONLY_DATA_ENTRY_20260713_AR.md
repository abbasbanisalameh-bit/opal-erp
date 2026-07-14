# تركيب تحديث إدخال البيانات من الموقع فقط

هذا التحديث يبني فوق `OPAL_ACADEMIC_STRUCTURE_UPDATE_20260713` ولا يمس قاعدة البيانات أو الميديا.

```bash
cd /home/Opalschool2016
mkdir -p site_only_data_entry_update
unzip -o OPAL_SITE_ONLY_DATA_ENTRY_UPDATE_20260713.zip -d site_only_data_entry_update
rsync -av \
  --exclude='db.sqlite3' --exclude='db.sqlite3-*' \
  --exclude='media/' --exclude='staticfiles/' \
  --exclude='.git/' --exclude='.env' \
  --exclude='venv/' --exclude='.venv/' \
  site_only_data_entry_update/opal_school/ opal_school/
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py migrate --noinput
python manage.py check
python manage.py collectstatic --noinput
python manage.py test
```

ثم اضغط **Reload** من صفحة Web.

## النتيجة

- `/admin/` لم يعد مدخلًا لإدارة بيانات المدرسة.
- العام والصف والرسوم والشعب ومربي الصف من **الشؤون الأكاديمية ← الهيكل الدراسي** فقط.
- الفروع من **إعدادات النظام ← إدارة الفروع**.
- فئات الرسوم من **الرسوم المدرسية ← فئات الرسوم**.
- الأدوار من **إعدادات النظام ← إدارة الأدوار** لمدير النظام فقط.
- قوالب الوثائق من **مركز الوثائق ← إدارة قوالب الوثائق**.

توجد قاعدة التزام موثقة في `docs/OPAL_DATA_ENTRY_COMMITMENT_AR.md`، وتشمل استثناء OpenEMIS: يدمج الاستيراد بيانات الطالب مع `students.Student` الرسمي ولا ينشئ سجلًا مكررًا عند وجود تطابق موثوق.
