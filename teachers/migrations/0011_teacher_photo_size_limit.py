from django.db import migrations, models
import core.validators


class Migration(migrations.Migration):
    dependencies = [("teachers", "0010_payroll_advances")]

    operations = [
        migrations.AlterField(
            model_name="teacher",
            name="photo",
            field=models.ImageField(blank=True, null=True, upload_to="teachers/", validators=[core.validators.validate_profile_image_size]),
        ),
    ]
