"""One shared workspace for all roles: Store.is_shared, set on the existing
store with the most aisles (ties -> lowest id) so entered data is kept. With
no store yet, services.get_shared_store() creates one on first use."""

from django.db import migrations, models
from django.db.models import Count


def pick_shared_store(apps, schema_editor):
    Store = apps.get_model("tracker", "Store")
    if Store.objects.filter(is_shared=True).exists():
        return
    store = (
        Store.objects.annotate(n_aisles=Count("aisles"))
        .order_by("-n_aisles", "id")
        .first()
    )
    if store is not None:
        Store.objects.filter(pk=store.pk).update(is_shared=True)


class Migration(migrations.Migration):
    dependencies = [("tracker", "0009_demo_roles")]

    operations = [
        migrations.AddField(
            model_name="store",
            name="is_shared",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(pick_shared_store, migrations.RunPython.noop),
    ]
