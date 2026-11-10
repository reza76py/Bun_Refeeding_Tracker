"""Let a cage code be reused once the old cage is finished: drop the DB-level
unique (aisle, code). Active cages stay unique via the serializer."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("tracker", "0011_aislecage_created_at")]

    operations = [
        migrations.RemoveConstraint(
            model_name="aislecage",
            name="unique_cage_code_per_aisle",
        ),
    ]
