from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0014_examroomreport"),
    ]

    operations = [
        migrations.AddField(
            model_name="examinationsettings",
            name="report_card_style",
            field=models.CharField(
                choices=[("standard", "Standard"), ("cbse", "CBSE style"), ("state", "State board style")],
                default="standard",
                max_length=10,
            ),
        ),
    ]
