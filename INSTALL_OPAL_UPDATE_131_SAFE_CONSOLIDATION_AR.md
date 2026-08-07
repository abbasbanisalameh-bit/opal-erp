# تعليمات تثبيت OPAL Update 131.0 على PythonAnywhere

## تحذير مهم

هذا الإصدار يحتوي هجرة بنيوية تحذف جدول `curriculum_curriculum` بعد نقل الاعتماد إلى `academics_subject`. لا تنفذ `migrate` قبل أخذ نسخة قابلة للاستعادة من قاعدة البيانات والكود. بعد تنفيذ الحذف، الرجوع يكون باستعادة النسخة الاحتياطية، وليس بعكس الهجرة.

البيانات الحالية لدى المشروع تجريبية، لكن خطوات الحماية تبقى إلزامية لأنها تختبر سلامة البنية وطريقة النشر الفعلية.

## 1. تثبيت خط الأساس

من Bash Console:

```bash
cd /home/Opalschool2016/opal_school
git status --short
git branch --show-current
git rev-parse HEAD
```

يجب التأكد أن النسخة الحالية هي خط الأساس المعتمد قبل استبدال الملفات. المصدر المثبت لهذا الإصدار هو الفرع `opal-stable-baseline-20260714` والـCommit `6d1139c500c1` بحسب مركز تحديثات النظام.

## 2. أخذ نسخة أمان

```bash
cd /home/Opalschool2016/opal_school
STAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p /home/Opalschool2016/opal_private_backups/update_131_$STAMP
cp db.sqlite3 /home/Opalschool2016/opal_private_backups/update_131_$STAMP/db.sqlite3
cd /home/Opalschool2016
zip -qr /home/Opalschool2016/opal_private_backups/update_131_$STAMP/code_before_update_131.zip opal_school \
  -x 'opal_school/.venv/*' 'opal_school/media/*' 'opal_school/__pycache__/*' 'opal_school/*/__pycache__/*'
```

تحقق من وجود النسختين:

```bash
ls -lh /home/Opalschool2016/opal_private_backups/update_131_$STAMP/
```

## 3. رفع الحزمة وفكها في مجلد مرحلي

ارفع ملف `OPAL_Update_131_0_SAFE_CONSOLIDATION_20260729.zip` إلى `/home/Opalschool2016/`، ثم:

```bash
cd /home/Opalschool2016
rm -rf opal_update_131_stage
mkdir opal_update_131_stage
unzip -q OPAL_Update_131_0_SAFE_CONSOLIDATION_20260729.zip -d opal_update_131_stage
```

تحقق من أن `manage.py` وهوية الإصدار داخل المجلد المرحلي:

```bash
ls -l /home/Opalschool2016/opal_update_131_stage/manage.py
cat /home/Opalschool2016/opal_update_131_stage/OPAL_VERSION.txt
cat /home/Opalschool2016/opal_update_131_stage/OPAL_RELEASE_NAME.txt
```

يجب أن يظهر الإصدار `131.0` والاسم `OPAL Update 131.0 - Safe Consolidation & Production Readiness`.

## 4. فحص الحزمة قبل الاستبدال

تحقق أولًا من سلامة ملف ZIP قبل الاعتماد عليه:

```bash
cd /home/Opalschool2016/opal_update_131_stage
python3 tools/verify_opal_update_131_archive.py /home/Opalschool2016/OPAL_Update_131_0_SAFE_CONSOLIDATION_20260729.zip
```

ثم نفذ بوابة المصدر التي لا تحتاج Django:

```bash
python3 tools/validate_opal_update_131_source.py
```

ثم فحص قاعدة الإنتاج قراءة فقط:

```bash
python3 tools/opal_update_131_preflight.py /home/Opalschool2016/opal_school/db.sqlite3
```

يجب أن تكون النتيجة `PASS` أو `"ok": true`. عند ظهور أي خطأ لا تكمل التثبيت.

## 5. استبدال الكود مع إبقاء ملفات التشغيل المحلية

الطريقة الآمنة هي مزامنة الكود مع استثناء قاعدة البيانات والوسائط والأسرار والبيئة الافتراضية:

```bash
rsync -a --delete \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='db.sqlite3' \
  --exclude='media/' \
  --exclude='.env' \
  /home/Opalschool2016/opal_update_131_stage/ \
  /home/Opalschool2016/opal_school/
```

لا تستخدم `cp -r` فوق المشروع إذا كان سيحذف أو يستبدل `db.sqlite3` أو `.env` أو `media`.

## 6. تفعيل البيئة الافتراضية

استخدم البيئة نفسها المرتبطة بتطبيق PythonAnywhere. مثال:

```bash
cd /home/Opalschool2016/opal_school
source /home/Opalschool2016/.virtualenvs/opal/bin/activate
```

إذا كان اسم البيئة مختلفًا، استخدم المسار الموجود في تبويب **Web** تحت Virtualenv.

## 7. فحوص Django قبل الهجرة

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
```

المطلوب:

- `check` بلا أخطاء.
- `makemigrations --check --dry-run` لا يطلب هجرات جديدة.
- خطة الهجرة تعرض هجرات Update 131 بالترتيب المعتمد.

## 8. تنفيذ الهجرات

```bash
python manage.py migrate --noinput
```

لا تقطع العملية أثناء عمل SQLite. عند أي خطأ لا تحاول تعديل الجداول يدويًا؛ استعد نسخة قاعدة البيانات والكود ثم راجع تقرير الخطأ.

## 9. فحوص ما بعد الهجرة

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core academics curriculum timetable exams teachers dashboard parent_portal
python manage.py collectstatic --noinput
```

إن كان تشغيل مجموعة الاختبارات كاملة يحتاج وقتًا كبيرًا، لا تتجاوز على الأقل:

```bash
python manage.py test \
  core.test_update127_smart_timetable_contract \
  core.test_update129_horizontal_timetable_contract \
  core.test_update131_safe_consolidation_contract \
  academics curriculum timetable exams teachers dashboard
```

## 10. إعادة تحميل الموقع

من تبويب **Web** اضغط **Reload** بعد نجاح جميع الأوامر السابقة فقط.

## 11. قائمة القبول التشغيلي

بعد إعادة التحميل افحص يدويًا:

1. مركز تحديثات النظام يعرض `OPAL Update 131.0`.
2. شاشة المواد تعرض العام والصف والحصص الأسبوعية واللون والحالة من `Subject` فقط.
3. لا تظهر شاشة Curriculum مستقلة في القوائم.
4. فتح رابط Curriculum قديم يحول إلى المواد ولا يعرض صفحة موازية.
5. شاشة الجدول تعرض العام الحالي، والمرشحات الأربعة فقط.
6. وقت الحصة يظهر في رأس العمود ولا يتكرر داخل بطاقات الحصص.
7. اسم الشعبة يظهر مثل «الصف الأول شعبة أ» مرة واحدة.
8. المنشئ الذكي يعمل داخل شاشة الجدول، والمعاينة لا تغير الجدول قبل الاعتماد.
9. اعتماد المنشئ الذكي لا يحذف الحصص اليدوية.
10. الاستراحات تظهر من إعدادات الأحداث.
11. عند اختيار معلم، تظهر «فراغ» فقط في الحصص غير المشغولة حقيقة.
12. سجل دوام المعلمين لا يطلب إدخال حضور يومي.
13. تسجيل غياب ينشئ احتياجات إشغال للحصص المتأثرة.
14. التأخر والمغادرة يؤثران في الحصص الزمنية فقط.
15. ولي الأمر يرى «معلم غائب» أو «المعلم غير متاح» دون السبب.
16. تعيين بديل يظهر اسم البديل في الجدول والحالة الحية.
17. `/exams/` يعرض السجل والتحليل المعياري، ولا توجد صفحات علامات أو تحليل موازية.
18. ترتيب الأوائل يعرض جميع المتعادلين.
19. طباعة الجدول تظهر A4 أفقيًا دون القائمة الجانبية أو الأزرار.
20. لا يظهر خطأ 500 في لوحة المدير أو المعلم أو ولي الأمر أو ملف الطالب 360.

## 12. خطة الرجوع عند الفشل

1. أوقف أي تعديل يدوي على النظام.
2. استعد مجلد الكود من `code_before_update_131.zip`.
3. استعد `db.sqlite3` من نسخة ما قبل التحديث.
4. أعد `collectstatic` للنسخة القديمة.
5. أعد تحميل تطبيق Web.
6. لا تستخدم `migrate <old migration>` لعكس دمج المواد؛ الهجرة صممت عمدًا لتتطلب استعادة نسخة الأمان.

## 13. التزام Update 132

التحويلات القديمة موسومة `LEGACY / DEPRECATED` وموعد حذفها `OPAL Update 132.0`. يحظر ربط أي زر أو قالب أو خدمة جديدة بها. في الإصدار التالي يجب فحص سجلات الوصول ثم حذف المسارات والدوال التحويلية نهائيًا.
