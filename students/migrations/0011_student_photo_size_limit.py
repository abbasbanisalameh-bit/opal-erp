from django.db import migrations, models
import core.validators


class Migration(migrations.Migration):
    dependencies = [("students", "0010_alter_student_is_demo")]

    operations = [
        migrations.AlterField(
            model_name="student",
            name="photo",
            field=models.ImageField(blank=True, null=True, upload_to="students/photos/", validators=[core.validators.validate_profile_image_size], verbose_name="صورة الطالب"),
        ),
    ]
