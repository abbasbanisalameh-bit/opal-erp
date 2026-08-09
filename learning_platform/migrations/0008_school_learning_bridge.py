from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0018_alter_subject_canonical_key_alter_subject_grade"),
        ("core", "0014_productiondataresetrun"),
        ("learning_platform", "0007_r21_runtime_validation_fixes"),
        ("students", "0011_student_photo_size_limit"),
        ("teachers", "0014_subject_plan_single_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="learningaccount",
            name="is_school_managed",
            field=models.BooleanField(db_index=True, default=False, verbose_name="حساب مدرسي مرتبط بـ OPAL ERP"),
        ),
        migrations.AddField(
            model_name="learningcourse",
            name="academic_section",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="learning_courses", to="academics.section", verbose_name="الشعبة المدرسية المرتبطة"),
        ),
        migrations.AddField(
            model_name="learningcourse",
            name="academic_subject",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="learning_courses", to="academics.subject", verbose_name="المادة المدرسية المرتبطة"),
        ),
        migrations.AddField(
            model_name="learninglesson",
            name="attachment",
            field=models.FileField(blank=True, upload_to="learning_lessons/", verbose_name="مرفق الدرس"),
        ),
        migrations.CreateModel(
            name="LearningAccessSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("parent_default_enabled", models.BooleanField(default=False, verbose_name="إتاحة المنصة لأولياء الأمور افتراضيًا")),
                ("teacher_sso_enabled", models.BooleanField(default=True, verbose_name="إتاحة المنصة للمعلمين")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="learning_access_settings", to="core.school")),
            ],
            options={"verbose_name": "إعداد وصول منصة أوبال التعليمية", "verbose_name_plural": "إعدادات وصول منصة أوبال التعليمية"},
        ),
        migrations.CreateModel(
            name="LearningGradeAccessOverride",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(verbose_name="متاح للصف")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("grade", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="learning_access_override", to="academics.grade")),
                ("settings", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="grade_overrides", to="learning_platform.learningaccesssettings")),
            ],
            options={"ordering": ["grade__order", "grade__name"]},
        ),
        migrations.CreateModel(
            name="LearningStudentAccessOverride",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(verbose_name="متاح للطالب")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("settings", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="student_overrides", to="learning_platform.learningaccesssettings")),
                ("student", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="learning_access_override", to="students.student")),
            ],
            options={"ordering": ["student__full_name", "student_id"]},
        ),
        migrations.CreateModel(
            name="LearningStudentProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="school_student_profile", to="learning_platform.learningaccount")),
                ("student", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="learning_profile", to="students.student")),
            ],
        ),
        migrations.CreateModel(
            name="LearningTeacherProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="school_teacher_profile", to="learning_platform.learningaccount")),
                ("teacher", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="learning_profile", to="teachers.teacher")),
            ],
        ),
    ]
