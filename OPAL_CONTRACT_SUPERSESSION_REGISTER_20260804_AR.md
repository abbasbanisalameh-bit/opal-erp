# سجل إحلال عقود الاختبار التاريخية — 2026-08-04

## القرار

وفق المرجع الهندسي الرسمي، لا تُعاد واجهة أو هوية إصدار متقاعدة لإرضاء اختبار تاريخي. جرى تحويل الاختبارات التالية إلى عقود ثابتة تقيس السلوك الحالي المجمّد بدل رموز cache أو أسماء إصدارات قديمة.

| العقود التاريخية | العقد المُحِلّ المعتمد |
|---|---|
| `core/test_update120_unified_ux_contract.py` و`core/test_update121_mobile_experience_contract.py` | منطقة تقدم وحالة واحدة، مع وجود cache-busting فعلي للأصول دون ربطه باسم تحديث قديم. |
| `core/test_update130_production_stability_contract.py` و`core/test_update131_safe_consolidation_contract.py` | تطابق `OPAL_RELEASE_NAME.txt` مع `version_name` في manifest، وبقاء رقم المنتج 131.7، واتساق token الأصول الأساسية دون ربطه بإصدار تاريخي. |
| `core/test_update131_6_subject_ui_contract.py` و`core/test_update131_7_fixed_manager_dashboard_contract.py` و`core/test_update131_7_r3_student360_mobile_containment_contract.py` | هوية الإصدار الحالية في ملفات الجذر هي المصدر الوحيد؛ لا يُشترط اسم R3 أو R4 أو لوحة سابقة. |
| `dashboard/test_update111_contract.py` و`test_update116_contract.py` و`test_update116_1_contract.py` و`test_update66_contract.py` | كل أصل محلي حساس يحمل مفتاح cache غير فارغ؛ لا يُشترط token تاريخي بعينه. |
| `dashboard/test_update117_contract.py` | لوحة الإدارة الثابتة الحالية، وبطاقات التواصل الثلاث قبل غياب اليوم، والرسوم تُنشأ عند وجود canvas دون customizer أو تفاصيل قابلة للطي متقاعدة. |
| `dashboard/test_update118_performance_contract.py` | عدّ الوثائق مقيّد بالعام الأكاديمي الحالي عند طلب المؤشرات الثانوية. |
| `dashboard/test_update63_contract.py` | `opal-fixed-manager-dashboard` هو غلاف اللوحة الرسمي بدل `opal-dashboard-compact-grid` المتقاعد. |

## عقود المتطلبات المحسومة

- مسار إضافة علامة قديم يحوّل إلى `/exams/#marks-review` ولا يعرض نموذج علامة منفردًا.
- لقطات حركة الشعب تحفظ الاسم الموحّد مثل `شعبة أ`.
- `feedback_total` يعد مشاركات رضا المدرسة فقط، و`teacher_evaluation_total` يعد تقييمات المعلمين بصورة مستقلة.
- سلفة المعلم لا تُخصم من شهر يسبق تاريخ الإقرار بها، ولا تُخصم مرتين بعد ربطها براتب مرسل.
- تهيئة العام الجديد تعتمد لقطة الفصل المغلق عند نسخ التكليفات والجدول، حتى لو عُطّلت سجلات العام المصدر بعد الإغلاق.
