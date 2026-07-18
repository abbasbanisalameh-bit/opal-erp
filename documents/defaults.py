DEFAULT_DOCUMENT_TEMPLATES = [
    {
        "code": "student-proof", "audience": "student", "document_type": "student_certificate",
        "name": "إثبات طالب", "title": "إثبات طالب",
        "body": "لمن يهمه الأمر\n\nتشير سجلات {school_name} إلى أن الطالب/ة {student_name}، الرقم الوطني {national_id}، أحد طلبتها منذ تاريخ {registration_date}، وقد التحق/ت بالمدرسة في الصف {first_grade}، وهو/هي حاليًا على مقاعد الدراسة في الصف {current_grade} للعام الدراسي {academic_year}.\n\nأُعطي هذا الإثبات بناءً على طلب ولي الأمر دون أدنى مسؤولية على المدرسة تجاه الغير.",
    },
    {
        "code": "candidate-acceptance", "audience": "candidate", "document_type": "acceptance_letter",
        "name": "كتاب قبول", "title": "كتاب قبول",
        "body": "لمن يهمه الأمر\n\nبناءً على طلب ولي أمر الطالب/ة {candidate_name}، تفيد {school_name} بموافقتها على قبول الطالب/ة مرشحًا للالتحاق بالصف {candidate_grade} للعام الدراسي {academic_year}، على أن يستكمل ولي الأمر متطلبات التسجيل والوثائق والرسوم المعتمدة.\n\nلا يُعد هذا الكتاب تسجيلًا نهائيًا أو قيدًا دراسيًا ما لم تُستكمل إجراءات التسجيل الرسمية في النظام.",
    },
    {
        "code": "student-transfer", "audience": "student", "document_type": "transfer_letter",
        "name": "كتاب انتقال", "title": "كتاب انتقال",
        "body": "لمن يهمه الأمر\n\nبناءً على طلب ولي أمر الطالب/ة {student_name}، الرقم الوطني {national_id}، توافق {school_name} على انتقاله/ا من الصف {current_grade} إلى مدرسة {target_school} للالتحاق بالصف {target_grade}، وذلك بعد استكمال المتطلبات الإدارية والمالية المعتمدة.",
    },
    {
        "code": "student-report-card", "audience": "student", "document_type": "report_card",
        "name": "كشف العلامات", "title": "كشف علامات الطالب",
        "body": "كشف رسمي لعلامات الطالب/ة {student_name} للعام الدراسي {academic_year}. يبين الجدول علامة كل امتحان في كل مادة والمجموع النهائي من مئة.",
    },
    {
        "code": "student-conduct", "audience": "student", "document_type": "student_conduct",
        "name": "شهادة حسن سيرة وسلوك", "title": "شهادة حسن سيرة وسلوك",
        "body": "تشهد {school_name} بأن الطالب/ة {student_name} كان/ت على مقاعد الدراسة لديها في الصف {current_grade}، وأنه/ا تمتع/ت بسيرة وسلوك حسنَين خلال فترة دراسته/ا، وقد أُعطيت هذه الشهادة بناءً على طلب ولي الأمر.",
    },
    {
        "code": "student-clearance", "audience": "student", "document_type": "clearance",
        "name": "براءة ذمة طالب", "title": "براءة ذمة",
        "body": "تشهد {school_name} بأن الطالب/ة {student_name} قد استكمل/ت الالتزامات المسجلة عليه/ا حتى تاريخ إصدار هذه الوثيقة، وفق سجلات المدرسة المالية والإدارية.",
    },
    {
        "code": "teacher-experience", "audience": "teacher", "document_type": "teacher_experience",
        "name": "شهادة خبرة", "title": "شهادة خبرة",
        "body": "لمن يهمه الأمر\n\nتشهد {school_name} بأن المعلم/ة {teacher_name}، الرقم الوطني {teacher_national_id}، عمل/ت لديها بوظيفة معلم/ة {specialization} من تاريخ {hire_date} حتى {teacher_end_date}. وقد أظهر/ت خلال مدة عمله/ا كفاءة والتزامًا مهنيًا، وأُعطيت هذه الشهادة بناءً على طلبه/ا.",
    },
    {
        "code": "teacher-appreciation", "audience": "teacher", "document_type": "teacher_appreciation",
        "name": "شهادة تقدير", "title": "شهادة شكر وتقدير",
        "body": "تتقدم {school_name} بخالص الشكر والتقدير إلى المعلم/ة {teacher_name} تقديرًا لجهوده/ا المتميزة وإسهامه/ا في خدمة الطلبة والعملية التعليمية، مع تمنياتنا له/ا بدوام النجاح والتوفيق.",
    },
    {
        "code": "teacher-recommendation", "audience": "teacher", "document_type": "teacher_recommendation",
        "name": "كتاب توصية", "title": "كتاب توصية",
        "body": "لمن يهمه الأمر\n\nيسر {school_name} أن توصي بالمعلم/ة {teacher_name}، الذي/التي عمل/ت لديها منذ {hire_date}. وقد اتسم/ت بالكفاءة المهنية والالتزام وحسن التعامل، ونوصي به/ا للمهام التعليمية التي تتناسب مع تخصصه/ا {specialization}.",
    },
    {
        "code": "teacher-salary", "audience": "teacher", "document_type": "teacher_salary",
        "name": "تعريف راتب", "title": "تعريف راتب",
        "body": "تشهد {school_name} بأن المعلم/ة {teacher_name} يعمل/ت لديها منذ {hire_date}، ويتقاضى/ت راتبًا شهريًا مسجلًا مقداره {monthly_salary} دينارًا أردنيًا. أُعطي هذا الكتاب بناءً على طلبه/ا دون أدنى مسؤولية على المدرسة تجاه الغير.",
    },
    {
        "code": "guardian-statement", "audience": "guardian", "document_type": "guardian_statement",
        "name": "كشف حساب ولي الأمر", "title": "كشف حساب ولي الأمر",
        "body": "يبين هذا الكشف الالتزامات المالية المسجلة على حساب ولي الأمر {guardian_name} عن أبنائه/ا: {children_names}، خلال العام الدراسي {academic_year}.\n\nإجمالي المبالغ المترتبة: {statement_total} د.أ\nإجمالي المدفوع: {statement_paid} د.أ\nإجمالي المتبقي: {statement_remaining} د.أ",
    },
]
