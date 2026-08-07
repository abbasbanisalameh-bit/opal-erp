from django.db import migrations


class Migration(migrations.Migration):
    # documents.0006 historically added a temporary FK to the admission
    # candidate model and documents.0007 removes it.  The deletion must run
    # afterwards so a clean installation never resolves a deleted model.
    dependencies = [
        ("admissions", "0012_remove_candidate_admissions"),
        ("documents", "0007_remove_candidate_documents"),
    ]

    operations = [
        migrations.DeleteModel(name="AdmissionApplication"),
    ]
