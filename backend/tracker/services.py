"""
Thin service helpers that connect the ORM to the pure calculation module.

Kept separate from views and serializers so the "what assumptions apply"
and "snapshot for this day" rules live in one place.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Max

from tracker.calculations import Assumptions
from tracker.models import AssumptionSet, Store

User = get_user_model()


def next_assumption_version(owner) -> int:
    current = (
        AssumptionSet.objects.filter(owner=owner).aggregate(m=Max("version"))["m"] or 0
    )
    return current + 1


def active_assumption_set(owner) -> AssumptionSet:
    """The newest assumption version for this owner, creating a default
    baseline (the brief's A-G values) the first time."""
    latest = AssumptionSet.objects.filter(owner=owner).order_by("-version").first()
    if latest is not None:
        return latest
    defaults = Assumptions()  # brief baseline
    return AssumptionSet.objects.create(
        owner=owner,
        version=1,
        cages_min=2,
        cages_max=5,
        default_lines_per_cage=defaults.default_lines_per_cage,
        units_per_line=defaults.units_per_line,
        find_sec=defaults.find_sec,
        unpack_sec=defaults.unpack_sec,
        seconds_per_unit=defaults.seconds_per_unit,
        other_sec=defaults.other_sec,
        provenance="assumed",
        notes="Initial baseline (provisional, not a verified standard).",
    )


@transaction.atomic
def create_assumption_version(owner, **fields) -> AssumptionSet:
    """Create a new immutable assumption version from the given field values,
    filling any omitted field from the current active version."""
    base = active_assumption_set(owner)
    data = base.snapshot()
    data.update({"cages_min": base.cages_min, "cages_max": base.cages_max})
    for key in (
        "cages_min",
        "cages_max",
        "default_lines_per_cage",
        "units_per_line",
        "find_sec",
        "unpack_sec",
        "seconds_per_unit",
        "other_sec",
    ):
        if fields.get(key) is not None:
            data[key] = int(fields[key])
    return AssumptionSet.objects.create(
        owner=owner,
        version=next_assumption_version(owner),
        cages_min=data["cages_min"],
        cages_max=data["cages_max"],
        default_lines_per_cage=data["default_lines_per_cage"],
        units_per_line=data["units_per_line"],
        find_sec=data["find_sec"],
        unpack_sec=data["unpack_sec"],
        seconds_per_unit=data["seconds_per_unit"],
        other_sec=data["other_sec"],
        provenance=fields.get("provenance", "user_estimate"),
        notes=fields.get("notes", ""),
    )


def default_store(owner) -> Store:
    store = Store.objects.filter(owner=owner).order_by("id").first()
    if store is not None:
        return store
    return Store.objects.create(owner=owner, name="My Bunnings store")
