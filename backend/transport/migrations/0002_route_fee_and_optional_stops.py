"""Stops become optional and the route carries a default fee.

Adds the route's fee and start/end labels, makes a stop's own fee optional, and gives a seat and a bill a
route of their own (filled in from the stop they already have). The next migration then makes the route
required and the stop optional; the two are separate because PostgreSQL will not alter a table that still
has pending changes from a data update in the same transaction.
"""
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def fill_route_from_stop(apps, schema_editor):
    for name in ("StudentTransport", "TransportBill"):
        model = apps.get_model("transport", name)
        for row in model.objects.select_related("stop"):
            row.route_id = row.stop.route_id
            row.save(update_fields=["route"])


class Migration(migrations.Migration):

    dependencies = [
        ("transport", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="route",
            name="start_point",
            field=models.CharField(blank=True, help_text="Where the morning run begins, if not at a stop.", max_length=100),
        ),
        migrations.AddField(
            model_name="route",
            name="end_point",
            field=models.CharField(blank=True, help_text="Where the morning run ends, usually the school.", max_length=100),
        ),
        migrations.AddField(
            model_name="route",
            name="monthly_fee",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                help_text="The default monthly fee for a student on this route. A stop with its own fee overrides it.",
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AddConstraint(
            model_name="route",
            constraint=models.CheckConstraint(
                condition=models.Q(("monthly_fee__gte", 0)), name="transport_route_fee_not_negative"
            ),
        ),
        migrations.RemoveConstraint(model_name="routestop", name="transport_stop_fee_not_negative"),
        migrations.AlterField(
            model_name="routestop",
            name="monthly_fee",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Leave empty to use the route's fee.",
                max_digits=10,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AddConstraint(
            model_name="routestop",
            constraint=models.CheckConstraint(
                condition=models.Q(("monthly_fee__isnull", True), ("monthly_fee__gte", 0), _connector="OR"),
                name="transport_stop_fee_not_negative",
            ),
        ),
        migrations.AddField(
            model_name="studenttransport",
            name="mode",
            field=models.CharField(
                choices=[("both", "Both ways"), ("pickup", "Pick-up only"), ("dropoff", "Drop-off only")],
                default="both",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="studenttransport",
            name="pickup_note",
            field=models.CharField(blank=True, help_text="For a route without stops, e.g. 'near the temple'.", max_length=255),
        ),
        migrations.AddField(
            model_name="studenttransport",
            name="route",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT, related_name="seats", to="transport.route"
            ),
        ),
        migrations.AddField(
            model_name="transportbill",
            name="route",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT, related_name="bills", to="transport.route"
            ),
        ),
        migrations.RunPython(fill_route_from_stop, migrations.RunPython.noop),
    ]
