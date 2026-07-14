# تركيب مركز سلامة البيانات

الحزمة لا تحتوي قاعدة بيانات أو ميديا أو `staticfiles`، وتبني فوق تحديث مختبر البيانات التجريبية.

```bash
cd /home/Opalschool2016
mkdir -p data_integrity_update
unzip -o OPAL_DATA_INTEGRITY_CENTER_UPDATE_20260713.zip -d data_integrity_update
rsync -av \
  --exclude='db.sqlite3' --exclude='db.sqlite3-*' \
  --exclude='media/' --exclude='staticfiles/' \
  --exclude='.git/' --exclude='.env' \
  --exclude='venv/' --exclude='.venv/' \
  data_integrity_update/opal_school/ opal_school/

cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py migrate --noinput
python manage.py check
python manage.py collectstatic --noinput
python manage.py test
```

ثم اضغط **Reload** من صفحة Web. يظهر زر **مركز سلامة البيانات** في إعدادات النظام لمدير النظام الأعلى.

## أوامر الكونسول

فحص فقط دون تعديل:

```bash
python manage.py audit_data_integrity --user abbas
```

فحص وتنفيذ الإصلاحات المؤكدة فقط:

```bash
python manage.py audit_data_integrity --fix-safe --user abbas
```

تقرير JSON:

```bash
python manage.py audit_data_integrity --format json > integrity_report.json
```

إرجاع رمز خطأ إذا بقيت مشكلات حرجة، ومفيد للنشر الآلي:

```bash
python manage.py audit_data_integrity --fail-on-critical
```

## ما يُصلح تلقائيًا

- مزامنة نسخة الصف والشعبة في ملف الطالب من القيد النشط الرسمي.
- مزامنة حالة ملف الطالب عند وجود قيد نشط واحد مؤكد.
- استعادة رابط الأسرة عندما توجد بيانات ولي أمر كافية ولا يوجد رابط نشط.
- مزامنة حالة حساب دخول المعلم مع حالة ملفه.
- مزامنة حالة الفاتورة مع الدفعات الفعلية.
- قفل الامتحان المعتمد أو المنشور.

## ما لا يُصلح أو يدمج تلقائيًا

- تكرار الرقم الوطني أو الوزاري للطلاب.
- تكرار أسر بالهاتف أو الرقم الوطني.
- وجود أكثر من قيد أو أسرة نشطة للطالب.
- تكليفات أو جداول متعارضة تحتاج قرارًا بشريًا.
- دفعات زائدة، علامات غير صحيحة، أو سجلات إلغاء ناقصة.

تُحفظ كل نتيجة في سجل تاريخي مع المنفذ والتاريخ وحالة المعالجة.
