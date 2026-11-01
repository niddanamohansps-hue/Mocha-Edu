from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("examinations", "0007_examination_date_sheet"),
    ]

    operations = [
        migrations.AddField(
            model_name="examination",
            name="marks_due_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
