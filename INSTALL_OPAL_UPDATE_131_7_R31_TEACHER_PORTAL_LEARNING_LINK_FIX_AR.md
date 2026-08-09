# تركيب OPAL R31

1. ارفع ZIP من مركز تحديثات OPAL وطبقه فوق R30.
2. افتح Bash ونفذ:

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test \
  core.test_update131_7_r31_teacher_portal_learning_link_contract \
  learning_platform.test_update131_7_r29_school_learning_bridge \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput
python manage.py collectstatic --clear --noinput
python manage.py check
```

3. من PythonAnywhere نفذ Web → Reload.
4. من إعدادات المنصة تأكد أن **إتاحة المنصة للمعلمين من بوابة المعلم** مفعلة.
5. ادخل بحساب معلم نشط، ويجب أن تظهر بطاقة **منصة أوبال التعليمية** في بوابة المعلم.
