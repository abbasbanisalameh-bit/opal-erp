# تقرير تحقق OPAL Update 131.5 R6 — استعادة السياق المرئي الأصلي

## سبب الخلل
مصمم اللوحة كان ينقل كل عنصر خارج الحاوية الأصلية. بعض تنسيقات OPAL تعتمد على سلاسل مثل:

- `.opal-executive-kpis a.dashboard-card`
- `.opal-satisfaction-pair .opal-satisfaction-score`
- `.opal-live-teachers-grid .opal-card`

بعد النقل لم تعد هذه المحددات تطابق العناصر، فظهرت الروابط والخطوط والأزرار والألوان بصورة مختلفة. محاولات R5 عالجت ثلاثة ألوان بقواعد إضافية، لكنها لم تعالج فقدان **السياق الأصلي**.

## الإصلاح الجذري
- حفظ سلسلة أصناف الحاويات الأصلية لكل عنصر قبل نقله.
- إعادة بنائها داخل الغلاف المتحرك كحاويات سياق غير مرئية.
- تحييد صندوق حاوية السياق فقط، مع إبقاء محددات CSS الأصلية مطابقة.
- إزالة طبقات محاكاة ألوان R5 والعودة إلى قواعد `opal_dashboard_executive.css` الأصلية.
- الإبقاء على السحب والعرض والارتفاع والحواف والإخفاء والحفظ.

## نتائج التحقق
- بوابة المصدر الثابتة: **147 من 147 ناجحة**.
- ملفات Python المحللة: **566 ملفًا دون خطأ تركيب**.
- اختبارات عقود Update 131.5 وSafe Consolidation: **23 من 23 ناجحة**.
- فحص JavaScript بواسطة `node --check`: ناجح.
- لا توجد هجرات جديدة ولا تغييرات بيانات.

## التحقق المطلوب على PythonAnywhere

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.test_update131_5_dashboard_layout_contract
python manage.py collectstatic --clear --noinput
```
