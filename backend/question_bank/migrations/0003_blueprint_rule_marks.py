from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("question_bank", "0002_question_papers"),
    ]

    operations = [
        migrations.AddField(
            model_name="blueprintrule",
            name="marks",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Marks of each question this rule picks. Empty means any marks.",
                max_digits=5,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0.5"))],
            ),
        ),
        migrations.AddConstraint(
            model_name="blueprintrule",
            constraint=models.CheckConstraint(
                condition=models.Q(("marks__isnull", True), ("marks__gt", 0), _connector="OR"),
                name="qb_rule_marks_positive",
            ),
        ),
    ]
