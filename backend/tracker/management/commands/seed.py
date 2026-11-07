"""
Seed a user with the brief's starting data: a store, aisles 9 and 10 with
bays 1-18 at the assumed catalogue counts, and the baseline assumption set.

Idempotent — safe to run repeatedly. No work days or cages are created, so no
fabricated history ends up in reports or charts.

    python manage.py seed                       # demo user: demo / demo12345
    python manage.py seed --username reza --password "s3cret" --email r@x.com
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from tracker.calculations import (
    Assumptions,
    catalogue_total,
    default_bays_aisle9,
    default_bays_aisle10,
)
from tracker.models import Aisle, AssumptionSet, Bay, Store

User = get_user_model()


class Command(BaseCommand):
    help = "Seed a user with the baseline store, aisles 9 & 10, bays and assumptions."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="demo")
        parser.add_argument("--password", default="demo12345")
        parser.add_argument("--email", default="demo@example.com")
        parser.add_argument("--store", default="Bunnings (configurable)")

    @transaction.atomic
    def handle(self, *args, **opts):
        user, created = User.objects.get_or_create(
            username=opts["username"], defaults={"email": opts["email"]}
        )
        if created:
            user.set_password(opts["password"])
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created user '{user.username}'."))
        else:
            self.stdout.write(f"User '{user.username}' already exists.")

        store, _ = Store.objects.get_or_create(
            owner=user, name=opts["store"], defaults={"timezone": "Australia/Brisbane"}
        )

        plan = {
            "Aisle 9": default_bays_aisle9(),
            "Aisle 10": default_bays_aisle10(),
        }
        for label, bays in plan.items():
            aisle, _ = Aisle.objects.get_or_create(
                store=store, label=label, defaults={"detail_mode": "bays"}
            )
            for bay_number, lines in bays:
                Bay.objects.update_or_create(
                    aisle=aisle,
                    bay_number=bay_number,
                    defaults={"estimated_catalogue_lines": lines},
                )

        a = Assumptions()  # baseline A-G
        if not AssumptionSet.objects.filter(owner=user).exists():
            AssumptionSet.objects.create(
                owner=user,
                version=1,
                cages_min=2,
                cages_max=5,
                default_lines_per_cage=a.default_lines_per_cage,
                units_per_line=a.units_per_line,
                find_sec=a.find_sec,
                unpack_sec=a.unpack_sec,
                seconds_per_unit=a.seconds_per_unit,
                other_sec=a.other_sec,
                provenance="assumed",
                notes="Initial baseline (provisional, not a verified standard).",
            )

        combined = catalogue_total(default_bays_aisle9() + default_bays_aisle10())
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded store '{store.name}' with aisles 9 & 10 "
                f"(combined catalogue {combined} lines) and baseline assumptions."
            )
        )
