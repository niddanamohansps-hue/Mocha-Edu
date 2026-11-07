from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0009_examinationsettings_show_rank_to_families"),
    ]

    operations = [
        migrations.AlterField(
            model_name="exammarkchange",
            name="kind",
            field=models.CharField(
                choices=[
                    ("entry", "Entered"),
                    ("correction", "Corrected"),
                    ("import", "Imported"),
                    ("grace", "Grace marks"),
                    ("recheck", "Recheck"),
                    ("moderation", "Moderation"),
                ],
                max_length=12,
            ),
        ),
    ]
