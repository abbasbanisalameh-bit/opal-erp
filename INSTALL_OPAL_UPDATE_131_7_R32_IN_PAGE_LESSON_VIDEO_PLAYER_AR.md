# تركيب OPAL R32 — تشغيل فيديو الدرس داخل المنصة

هذا التحديث يبني فوق R31، ولا يتضمن أي هجرة قاعدة بيانات.

## ما يتغير
- إزالة رابط **فتح الفيديو** الذي كان يفتح تبويبًا جديدًا.
- عرض الفيديو مباشرة داخل صفحة الدرس في عارض خاص بالمنصة.
- دعم روابط YouTube العادية وروابط youtu.be وShorts وLive عبر مشغل YouTube المضمن.
- دعم Vimeo عبر المشغل المضمن.
- دعم روابط ملفات MP4/WebM/Ogg/M4V بالمشغل الأصلي للمتصفح.
- الروابط الأخرى تعرض داخل إطار محمي داخل الصفحة عندما يسمح الموقع المصدر بالتضمين.

## التركيب والتحقق على PythonAnywhere

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate

python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate

python manage.py test \
  core.test_update131_7_r32_in_page_lesson_video_player_contract \
  learning_platform.tests \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput

python manage.py collectstatic --clear --noinput
python manage.py check
```

بعد نجاح الاختبارات: **Web → Reload**.

## اختبار يدوي
1. افتح درسًا يحتوي رابط YouTube أو Vimeo.
2. يجب أن يظهر الفيديو داخل بطاقة الدرس نفسها.
3. يجب ألا يظهر زر يفتح الفيديو في نافذة جديدة.
4. جرّب على الهاتف وتأكد أن المشغل يظل داخل صفحة منصة أوبال.

> ملاحظة: بعض المواقع تمنع تقنيًا عرض صفحاتها داخل iframe عبر سياسات X-Frame-Options/CSP. في هذه الحالة استخدم رابط YouTube/Vimeo أو رابط فيديو مباشر يدعم التضمين.
