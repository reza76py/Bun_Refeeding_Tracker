"""AisleCage.created_at: when the cage was added on Plan. Existing cages get
the time this migration runs."""

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tracker", "0010_store_is_shared")]

    operations = [
        migrations.AddField(
            model_name="aislecage",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
    ]
