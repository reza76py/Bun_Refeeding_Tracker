"""Demo roles: groups GI, MNG, MBR, ADMIN and one demo user per role.

Idempotent: groups and users are get_or_create'd. An existing user keeps its
password and flags; it is only added to its group. No user is removed.
"""

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations

# username -> group
DEMO_USERS = {"GI": "GI", "MNG": "MNG", "MBR": "MBR", "admin": "ADMIN"}


def create_demo_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)
    for username, group_name in DEMO_USERS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "password": make_password(username),  # demo: password == username
                "is_staff": username == "admin",
            },
        )
        user.groups.add(group)


def remove_demo_roles(apps, schema_editor):
    # Reverse only drops the groups; demo users are left in place.
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=set(DEMO_USERS.values())).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tracker", "0008_cagesession"),
    ]

    operations = [migrations.RunPython(create_demo_roles, remove_demo_roles)]
