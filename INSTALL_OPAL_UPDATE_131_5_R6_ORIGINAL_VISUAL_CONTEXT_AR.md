# تثبيت OPAL Update 131.5 R6 — استعادة الشكل الأصلي للوحة المدير

يعيد التحديث الشكل والألوان والخطوط والأزرار الأصلية للعناصر كما كانت قبل نقلها، مع الإبقاء على السحب وتغيير العرض والارتفاع والحواف والإخفاء.

بعد التركيب وإعادة تحميل الموقع نفّذ:

```bash
cd /home/Opalschool2016/opal_school
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.test_update131_5_dashboard_layout_contract
python manage.py collectstatic --clear --noinput
```

اختبر بطاقات المؤشرات، وأزرار الشكاوى والتعاميم والإعلانات، ثم غيّر حجم عنصر وانقله واحفظه. لا توجد هجرات جديدة ولا تغييرات بيانات.
