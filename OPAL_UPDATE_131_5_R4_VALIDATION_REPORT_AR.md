# تقرير تحقق OPAL Update 131.5 R4 — الإصلاح الجذري للعقود

## سبب الإصلاح
حزمة R3 فشلت قبل الاعتماد لأن عقد Update 125 القديم كان يفرض ظهور اختصار `enterprise_ops:workflow_list` في لوحة المدير، بينما R3 أخفاه بناءً على طلب المستخدم. كذلك كان فحص أمان تخطيط اللوحة يبحث عن صياغة حرفية `"cols": _safe_choice`، رغم أن الكود الآمن خزّن النتيجة في متغير `cols`.

## المعالجة الجذرية
- توحيد سياسة الاختصار المتقاعد في عقد المدخل الموحد: لا يظهر في القوالب، مع بقاء المسار والخدمة والبيانات.
- استبدال فحص الصياغة الحرفية بفحص سلوكي يمرر حمولة خبيثة فعلية إلى `normalize_dashboard_layout`.
- إضافة بوابتي اتساق إلى أداة بناء المصدر لمنع إصدار حزمة متناقضة مستقبلًا.
- تحديث الاختبارات القديمة التي كانت تفرض ظهور الاختصار.

## نتائج التحقق المحلي
- فحص المصدر: **147 من 147 ناجحة**.
- تحليل تركيب Python: **566 ملفًا دون أخطاء**.
- اختبار عقد Update 131.5: **10 من 10 ناجحة**.
- تنفيذ تدقيق المدخل الموحد على الشجرة النهائية: **ناجح، صفر قضايا**.
- تنفيذ تدقيق أمان تخطيط اللوحة سلوكيًا: **ناجح، صفر قضايا**.
- فحص JavaScript بواسطة `node --check`: **ناجح**.

## حدود بيئة البناء
Django غير مثبت في بيئة البناء هذه، لذلك لا أدعي تشغيل `python manage.py check` محليًا. صُممت الحزمة لتشغيله داخل مركز تحديثات PythonAnywhere، ويجب كذلك تنفيذ أوامر التحقق بعد التركيب.

## مقتطف الاختبارات
```text
test_all_dashboard_blocks_are_customizable (core.test_update131_5_dashboard_layout_contract.Update1315DashboardLayoutContractTests.test_all_dashboard_blocks_are_customizable) ... ok
test_contracts_match_the_retired_dashboard_shortcut_policy (core.test_update131_5_dashboard_layout_contract.Update1315DashboardLayoutContractTests.test_contracts_match_the_retired_dashboard_shortcut_policy) ... ok
test_dashboard_post_saves_and_resets_per_user (core.test_update131_5_dashboard_layout_contract.Update1315DashboardLayoutContractTests.test_dashboard_post_saves_and_resets_per_user) ... ok
test_mobile_falls_back_to_one_safe_column (core.test_update131_5_dashboard_layout_contract.Update1315DashboardLayoutContractTests.test_mobile_falls_back_to_one_safe_column) ... ok
test_one_central_tool_controls_one_many_or_all (core.test_update131_5_dashboard_layout_contract.Update1315DashboardLayoutContractTests.test_one_central_tool_controls_one_many_or_all) ... ok
test_profile_persists_layout_without_parallel_model (core.test_update131_5_dashboard_layout_contract.Update1315DashboardLayoutContractTests.test_profile_persists_layout_without_parallel_model) ... ok
test_release_identity (core.test_update131_5_dashboard_layout_contract.Update1315DashboardLayoutContractTests.test_release_identity) ... ok
test_requested_visual_fragments_are_removed_without_removing_live_lists (core.test_update131_5_dashboard_layout_contract.Update1315DashboardLayoutContractTests.test_requested_visual_fragments_are_removed_without_removing_live_lists) ... ok
test_schema_two_discards_retired_complex_layout (core.test_update131_5_dashboard_layout_contract.Update1315DashboardLayoutContractTests.test_schema_two_discards_retired_complex_layout) ... ok
test_server_validates_widget_ids_and_choices (core.test_update131_5_dashboard_layout_contract.Update1315DashboardLayoutContractTests.test_server_validates_widget_ids_and_choices) ... ok

----------------------------------------------------------------------
Ran 10 tests in 0.001s

OK
```

## مقتطف التدقيق السلوكي
```text
single_entry {'ok': True, 'checks': {'role_gateways': True, 'global_navigation': True, 'canonical_visible_entries': True}, 'issue_count': 0, 'issues': []}
dashboard_layout {'ok': True, 'issues': []}
```
