from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0008_whatsapp_outbox"),
    ]

    operations = [
        migrations.AlterField(
            model_name="alertlog",
            name="kind",
            field=models.CharField(
                choices=[
                    ("fee_due_soon", "Fee due soon"),
                    ("fee_overdue", "Fee overdue"),
                    ("absence", "Absence"),
                    ("payment_receipt", "Payment receipt"),
                    ("exam_date_sheet", "Exam date sheet"),
                ],
                max_length=30,
            ),
        ),
    ]
