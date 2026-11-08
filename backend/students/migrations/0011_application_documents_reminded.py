from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0010_application_decision_notice"),
    ]

    operations = [
        migrations.AddField(
            model_name="admissionapplication",
            name="documents_reminded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
