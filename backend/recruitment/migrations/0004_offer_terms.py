from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recruitment", "0003_interviewpanelist"),
    ]

    operations = [
        migrations.AddField(model_name="applicant", name="offered_designation", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(
            model_name="applicant",
            name="offered_salary",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(model_name="applicant", name="offered_joining_date", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="applicant", name="offer_valid_until", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="applicant", name="offer_notes", field=models.TextField(blank=True)),
        migrations.AddField(model_name="applicant", name="offer_sent_at", field=models.DateTimeField(blank=True, null=True)),
    ]
