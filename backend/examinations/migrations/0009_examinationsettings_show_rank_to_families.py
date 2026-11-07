from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0008_examination_marks_due_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="examinationsettings",
            name="show_rank_to_families",
            field=models.BooleanField(default=False),
        ),
    ]
