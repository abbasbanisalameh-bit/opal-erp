# Generated manually for OPAL ERP Smart Registration foundation

from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("admissions", "0001_initial"),
        ("accounting", "0004_alter_studentinvoice_student"),
        ("academics", "0008_alter_studentdocument_student_and_more"),
        ("core", "0002_sequence"),
        ("students", "0005_student_is_active_student_medical_notes"),
    ]

    operations = [
        migrations.CreateModel(
            name="RegistrationSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("first_payment_percent", models.DecimalField(decimal_places=2, default=20, max_digits=5, verbose_name="نسبة الدفعة الأولى")),
                ("cash_discount_percent", models.DecimalField(decimal_places=2, default=10, max_digits=5, verbose_name="خصم الكاش")),
                ("sibling_discount_percent", models.DecimalField(decimal_places=2, default=5, max_digits=5, verbose_name="خصم الإخوة")),
                ("quran_25_percent", models.DecimalField(decimal_places=2, default=25, max_digits=5, verbose_name="خصم حفظ القرآن 25")),
                ("quran_50_percent", models.DecimalField(decimal_places=2, default=50, max_digits=5, verbose_name="خصم حفظ القرآن 50")),
                ("quran_75_percent", models.DecimalField(decimal_places=2, default=75, max_digits=5, verbose_name="خصم حفظ القرآن 75")),
                ("quran_100_percent", models.DecimalField(decimal_places=2, default=100, max_digits=5, verbose_name="خصم حفظ القرآن 100")),
                ("enable_cash_discount", models.BooleanField(default=True, verbose_name="تفعيل خصم الكاش")),
                ("enable_sibling_discount", models.BooleanField(default=True, verbose_name="تفعيل خصم الإخوة")),
                ("enable_quran_discount", models.BooleanField(default=True, verbose_name="تفعيل خصم القرآن")),
                ("enable_admin_discount", models.BooleanField(default=True, verbose_name="تفعيل خصم الإدارة")),
                ("sibling_discount_once_per_family", models.BooleanField(default=True, verbose_name="خصم الإخوة مرة واحدة للعائلة")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="registration_settings", to="core.school")),
            ],
            options={"verbose_name": "إعدادات التسجيل والخصومات", "verbose_name_plural": "إعدادات التسجيل والخصومات"},
        ),
        migrations.CreateModel(
            name="TransportRoute",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150, verbose_name="اسم الجولة")),
                ("full_fee", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="رسوم ذهاب وعودة")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعالة")),
                ("notes", models.TextField(blank=True, verbose_name="ملاحظات")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transport_routes", to="core.school")),
            ],
            options={"verbose_name": "جولة مواصلات", "verbose_name_plural": "جولات المواصلات", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="GradeFee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tuition_fee", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="رسوم الصف")),
                ("is_active", models.BooleanField(default=True, verbose_name="فعالة")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("academic_year", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="grade_fees", to="core.academicyear")),
                ("grade", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fee_settings", to="academics.grade")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="grade_fees", to="core.school")),
            ],
            options={"verbose_name": "رسوم صف", "verbose_name_plural": "رسوم الصفوف", "ordering": ["grade__order", "grade__name"]},
        ),
        migrations.CreateModel(
            name="StudentRegistration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("registration_number", models.CharField(max_length=50, unique=True, verbose_name="رقم التسجيل")),
                ("first_name", models.CharField(max_length=100, verbose_name="الاسم الأول")),
                ("father_name", models.CharField(blank=True, max_length=100, verbose_name="اسم الأب")),
                ("grandfather_name", models.CharField(blank=True, max_length=100, verbose_name="اسم الجد")),
                ("family_name", models.CharField(blank=True, max_length=100, verbose_name="اسم العائلة")),
                ("full_name", models.CharField(max_length=250, verbose_name="الاسم الكامل")),
                ("national_id", models.CharField(blank=True, max_length=50, verbose_name="الرقم الوطني")),
                ("gender", models.CharField(blank=True, max_length=20, verbose_name="الجنس")),
                ("birth_date", models.DateField(blank=True, null=True, verbose_name="تاريخ الميلاد")),
                ("address", models.TextField(blank=True, verbose_name="العنوان")),
                ("phone", models.CharField(blank=True, max_length=30, verbose_name="هاتف ولي الأمر")),
                ("guardian_name", models.CharField(blank=True, max_length=200, verbose_name="اسم ولي الأمر")),
                ("mother_name", models.CharField(blank=True, max_length=200, verbose_name="اسم الأم")),
                ("photo", models.ImageField(blank=True, null=True, upload_to="students/photos/", verbose_name="صورة الطالب")),
                ("transport_type", models.CharField(choices=[("none", "غير مشترك"), ("go", "ذهاب فقط"), ("return", "عودة فقط"), ("both", "ذهاب وعودة")], default="none", max_length=20, verbose_name="نوع المواصلات")),
                ("discount_type", models.CharField(choices=[("none", "بدون خصم"), ("quran_100", "حفظ القرآن 100%"), ("quran_75", "حفظ القرآن 75%"), ("quran_50", "حفظ القرآن 50%"), ("quran_25", "حفظ القرآن 25%"), ("cash", "خصم الكاش"), ("sibling", "خصم الإخوة"), ("admin", "خصم الإدارة")], default="none", max_length=20, verbose_name="نوع الخصم")),
                ("admin_discount_value", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="خصم الإدارة")),
                ("tuition_fee", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="رسوم الصف")),
                ("transport_fee", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="رسوم المواصلات")),
                ("discount_value", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="قيمة الخصم")),
                ("net_total", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="صافي الرسوم")),
                ("first_payment", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="الدفعة الأولى")),
                ("remaining_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="المتبقي")),
                ("notes", models.TextField(blank=True, verbose_name="ملاحظات")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("academic_year", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="core.academicyear")),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="core.branch")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("grade", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.grade")),
                ("invoice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="accounting.studentinvoice")),
                ("payment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="accounting.studentpayment")),
                ("receipt", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="accounting.receipt")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="student_registrations", to="core.school")),
                ("section", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.section")),
                ("sibling_student", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sibling_discount_registrations", to="students.student")),
                ("student", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="registrations", to="students.student")),
                ("transport_route", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="admissions.transportroute")),
            ],
            options={"verbose_name": "تسجيل طالب", "verbose_name_plural": "تسجيل الطلاب", "ordering": ["-created_at"]},
        ),
    ]
