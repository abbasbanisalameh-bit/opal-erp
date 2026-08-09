# OPAL Update 131.7 R35.1 — Flutter RadioGroup Analyze Hotfix

## الإصلاح
- استبدال إدارة اختيار إجابات الاختبار القديمة داخل `RadioListTile` بـ `RadioGroup<String>` الحديث.
- إزالة `groupValue` و`onChanged` المهملين من `RadioListTile`.
- الحفاظ على نفس سلوك حفظ إجابة كل سؤال في `answers[questionId]`.
- رفع نسخة تطبيق Flutter إلى `1.1.1+36`.

## الأثر
- لا تعديل على قاعدة البيانات.
- لا تعديل على API أو SSO أو بطاقات الاشتراك أو البصمة.
- الهدف الوحيد هو اجتياز `flutter analyze` على Flutter stable الحديث ومواصلة بناء APK/AAB.
