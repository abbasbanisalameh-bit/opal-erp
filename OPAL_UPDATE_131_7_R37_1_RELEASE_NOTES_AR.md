# R37.1 — Native ERP Android Baseline Fix

- يبني R37 فوق R36.1 بدل R36.
- يحافظ على `const CardThemeData` الذي اجتاز Flutter Analyze.
- يبقي تطبيق نظام OPAL ERP المستقل وواجهات `/mobile/api/v1/`.
- يبقي شعار المدرسة المعتمد لتطبيق النظام.
- يحسن `install_erp_mobile_android_ci` لإعادة Workflow تطبيق النظام وWorkflow منصة أوبال بعد التحديث.
- لا يغير بيانات المدرسة الحالية، ولا نموذج الطالب الرسمي.
