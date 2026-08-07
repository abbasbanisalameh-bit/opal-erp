# تركيب OPAL Update 131.7 R11

يضيف هذا التحديث **منصة أوبال التعليمية** داخل مشروع Django نفسه وتحت المسار `/learning/`، مع تسجيل ودخول وجلسة وقوالب وملفات ثابتة مستقلة عن OPAL ERP. لا تحتوي الحزمة قاعدة بيانات أو وسائط أو أسرار، لكنها تحتوي هجرة جديدة لإنشاء جداول المنصة التعليمية.

## قبل التركيب

1. احفظ نسخة من الكود وقاعدة البيانات و`media/` وملف إعداد البيئة.
2. ثبّت الحزمة كاملة مع إبقاء `db.sqlite3` و`media/` و`.env` والبيئة الافتراضية خارج الاستبدال.
3. لا تنسخ التطبيق وحده؛ فالتحديث يتضمن تسجيل التطبيق والمسار والاختبارات ووثائق الإصدار.

## أوامر التركيب

```bash
cd /home/Opalschool2016/opal_school
source /home/Opalschool2016/.virtualenvs/opal/bin/activate
python tools/validate_opal_update_131_source.py .
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py test learning_platform core.test_update131_7_r11_integrated_learning_platform_contract
python manage.py collectstatic --clear --noinput
```

بعد نجاح الأوامر اضغط **Reload** من تبويب Web في PythonAnywhere، ثم افتح:

```text
https://YOUR-DOMAIN/learning/
```

التسجيل التعليمي من `/learning/register/`، والدخول التعليمي من `/learning/login/`. لا يستخدم أي منهما تسجيل OPAL ERP في `/accounts/login/`.

## الرجوع

احتفظ بنسخة قاعدة البيانات قبل الهجرة. عند الرجوع استعد نسخة الكود وقاعدة البيانات معًا، ثم نفذ `collectstatic --clear --noinput` وأعد تحميل الموقع.
