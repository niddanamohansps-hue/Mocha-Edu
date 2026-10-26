"""Every seat and bill now has a route; the stop becomes optional (a route may have no stops)."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transport", "0002_route_fee_and_optional_stops"),
    ]

    operations = [
        migrations.AlterField(
            model_name="studenttransport",
            name="route",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="seats", to="transport.route"
            ),
        ),
        migrations.AlterField(
            model_name="studenttransport",
            name="stop",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assignments",
                to="transport.routestop",
            ),
        ),
        migrations.AlterField(
            model_name="transportbill",
            name="route",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="bills", to="transport.route"
            ),
        ),
        migrations.AlterField(
            model_name="transportbill",
            name="stop",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="bills",
                to="transport.routestop",
            ),
        ),
    ]
