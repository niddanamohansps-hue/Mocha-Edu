from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("families", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="parent",
            name="whatsapp_opt_in",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="parent",
            name="whatsapp_opt_in_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
