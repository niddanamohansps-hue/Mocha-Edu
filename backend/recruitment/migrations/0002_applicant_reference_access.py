from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recruitment", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicant",
            name="reference",
            field=models.CharField(blank=True, default="", editable=False, max_length=20),
        ),
        migrations.AddField(
            model_name="applicant",
            name="access_token_hash",
            field=models.CharField(blank=True, default="", editable=False, max_length=64),
        ),
        migrations.AddConstraint(
            model_name="applicant",
            constraint=models.UniqueConstraint(
                condition=models.Q(("reference", ""), _negated=True),
                fields=("reference",),
                name="uniq_applicant_reference",
            ),
        ),
    ]
