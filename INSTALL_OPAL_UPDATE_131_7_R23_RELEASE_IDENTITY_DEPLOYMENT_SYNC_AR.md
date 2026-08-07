# تركيب OPAL Update 131.7 R23

## Release Identity Deployment Synchronization

يُركب هذا التحديث فوق:

`OPAL Update 131.7 R22 - Forward-Compatible Release Contract Fix`

## سبب التحديث

أثبت اختبار R22 على PythonAnywhere أن وظائف المنصة وإصلاحات العقود تعمل، لكن بقي اختلاف بين `OPAL_RELEASE_NAME.txt` الذي ظل يعرض R21 و`OPAL_UPDATE_MANIFEST.json` الذي يعرض R22. لذلك فشلت ثلاثة عقود هوية، رغم أن الاختبارات الوظيفية الأخرى نجحت.

## ما يصلحه R23

- إعادة مزامنة ملفات الهوية الثلاثة أثناء الهجرة: `OPAL_VERSION.txt` و`OPAL_RELEASE_NAME.txt` و`OPAL_UPDATE_MANIFEST.json`.
- إجبار مركز التحديثات على نسخ ملفات الهوية الثلاثة صراحة بعد استبدال الكود.
- إيقاف عملية التحديث بأمان إذا لم تتطابق نسخة الإصدار واسم الإصدار وmanifest بعد النسخ.
- إبقاء عقود R11-R22 قابلة للتشغيل بعد الإصدارات اللاحقة.
- لا تغيير على قاعدة بيانات الأعمال أو الحسابات أو الدورات أو الاشتراكات أو المدفوعات أو الصلاحيات.

## بعد التركيب

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate

python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate

cat OPAL_RELEASE_NAME.txt
python - <<'PY'
import json
from pathlib import Path
root = Path('.')
release = (root / 'OPAL_RELEASE_NAME.txt').read_text(encoding='utf-8').strip()
manifest = json.loads((root / 'OPAL_UPDATE_MANIFEST.json').read_text(encoding='utf-8'))
print(release)
print(manifest['version_name'])
print('MATCH=', release == manifest['version_name'])
PY
```

يجب أن يظهر:

```text
OPAL Update 131.7 R23 - Release Identity Deployment Synchronization
MATCH= True
```

ثم شغّل الاختبارات المستهدفة:

```bash
python manage.py test learning_platform \
core.test_update131_7_r20_learning_production_release_contract \
core.test_update131_7_r21_learning_runtime_validation_fix_contract \
core.test_update131_7_r22_forward_compatible_release_contract \
core.test_update131_7_r23_release_identity_deployment_sync_contract
```

بعد ظهور `OK` شغّل المجموعة الكاملة:

```bash
python manage.py test --verbosity 1 > /tmp/r23_full_test.txt 2>&1
tail -n 100 /tmp/r23_full_test.txt
```

لا تنفّذ `collectstatic` أو Reload قبل نجاح الاختبارات المستهدفة.
