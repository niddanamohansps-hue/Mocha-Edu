from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0009_compliance_blank_defaults"),
    ]

    operations = [
        migrations.AddField(
            model_name="admissionapplication",
            name="decision_notice_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
