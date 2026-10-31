from django.db import migrations, models


class Migration(migrations.Migration):
    """New students no longer get a guessed General category or Hindi mother tongue.

    Only the defaults change. Existing rows keep whatever they hold, because a stored "GEN" or "Hindi"
    cannot be told apart from one somebody actually entered.
    """

    dependencies = [
        ("students", "0008_student_aadhaar_last_4_student_aadhaar_verified_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="student",
            name="caste_category",
            field=models.CharField(
                blank=True,
                choices=[("GEN", "General"), ("OBC", "OBC"), ("SC", "SC"), ("ST", "ST"), ("EWS", "EWS")],
                default="",
                help_text="Left blank until recorded, so exports never report a guessed category",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="student",
            name="mother_tongue",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
    ]
