"""
Data model for the Shelf Replenishment Workload Tracker (Release 1 MVP).

Key design decisions driven by the brief:

* Every record is owned by a user; querysets are filtered by the requester so
  one user can never read another's data.
* AssumptionSet rows are immutable version snapshots. "Editing" assumptions
  creates a new version; old versions are never mutated.
* A WorkDay stores an immutable JSON snapshot of the exact assumptions used for
  its forecast, so saving newer assumptions later never changes a past day.
* Forecast seconds (snapshots) are stored distinctly from measured actuals.
  The two are never conflated.

All durations are stored as integer seconds.
"""

from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from tracker.calculations import Assumptions, estimated_cage_seconds

USER = settings.AUTH_USER_MODEL

# Shared validator bounds (non-negative, with sane upper limits).
SEC_VALIDATORS = [MinValueValidator(0), MaxValueValidator(86_400)]          # <= 24h
SMALL_SEC_VALIDATORS = [MinValueValidator(0), MaxValueValidator(36_000)]    # <= 10h per step
COUNT_VALIDATORS = [MinValueValidator(0), MaxValueValidator(100_000)]


def seconds_per_line_field():
    """Optional time to restock one line, entered in Settings per cage/bay."""
    return models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(3_600)],
    )


def _row_seconds(lines: int, seconds_per_line):
    return None if seconds_per_line is None else lines * seconds_per_line


class Provenance(models.TextChoices):
    ASSUMED = "assumed", "Assumed"
    USER_ESTIMATE = "user_estimate", "User estimate"
    MEASURED = "measured", "Measured"


class CageStatus(models.TextChoices):
    PLANNED = "planned", "Planned"
    IN_PROGRESS = "in_progress", "In progress"
    COMPLETE = "complete", "Complete"
    PARTIAL = "partial", "Partial"
    BLOCKED = "blocked", "Blocked"


class Store(models.Model):
    owner = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="stores")
    name = models.CharField(max_length=120, default="My Bunnings store")
    timezone = models.CharField(max_length=64, default="Australia/Brisbane")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class AisleDetailMode(models.TextChoices):
    CAGES = "cages", "Cages"
    BAYS = "bays", "Bays"


class Aisle(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="aisles")
    label = models.CharField(max_length=40)  # e.g. "Aisle 9"
    active = models.BooleanField(default=True)
    # Whole-aisle catalogue lines for "big picture" planning, used only when
    # the aisle has no bay details. Bays always win when present.
    aisle_total_lines = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1_000_000)]
    )
    # How this aisle's lines are entered in Settings: per cage or per bay.
    detail_mode = models.CharField(
        max_length=8, choices=AisleDetailMode.choices, default=AisleDetailMode.CAGES
    )

    class Meta:
        ordering = ["store_id", "label"]
        constraints = [
            models.UniqueConstraint(
                fields=["store", "label"], name="unique_aisle_label_per_store"
            )
        ]

    def __str__(self) -> str:
        return self.label

    @property
    def catalogue_lines(self) -> int:
        """Catalogue lines for the aisle:
        1. sum of the entries for its ``detail_mode`` (cages or bays), if any;
        2. otherwise sum of the other kind, if any (older data);
        3. otherwise the (legacy) whole-aisle total.
        Uses ``.all()`` so prefetches are honoured."""
        rows = self.counted_rows()
        if rows:
            return sum(r.row_lines for r in rows)
        return self.aisle_total_lines

    def counted_rows(self) -> list:
        """The cages or bays that count towards this aisle: those of its
        ``detail_mode`` if any exist, otherwise those of the other kind."""
        cages = list(self.cages.all())
        bays = list(self.bays.all())
        order = (bays, cages) if self.detail_mode == AisleDetailMode.BAYS else (cages, bays)
        for rows in order:
            if rows:
                return rows
        return []

    @property
    def estimated_seconds(self):
        """Sum of lines x seconds-per-line over counted rows that have a time.
        None when no counted row has a seconds-per-line yet."""
        times = [r.estimated_seconds for r in self.counted_rows()]
        times = [t for t in times if t is not None]
        return sum(times) if times else None

    @property
    def rows_missing_time(self) -> int:
        return sum(1 for r in self.counted_rows() if r.estimated_seconds is None)


class Bay(models.Model):
    aisle = models.ForeignKey(Aisle, on_delete=models.CASCADE, related_name="bays")
    bay_number = models.PositiveIntegerField()
    # Assumed distinct stocked product lines (area size) — NOT units, NOT daily
    # replenishment demand.
    estimated_catalogue_lines = models.PositiveIntegerField(
        default=0, validators=COUNT_VALIDATORS
    )
    seconds_per_line = seconds_per_line_field()

    class Meta:
        ordering = ["aisle_id", "bay_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["aisle", "bay_number"], name="unique_bay_number_per_aisle"
            )
        ]

    def __str__(self) -> str:
        return f"{self.aisle.label} / Bay {self.bay_number}"

    @property
    def row_lines(self) -> int:
        return self.estimated_catalogue_lines

    @property
    def estimated_seconds(self):
        return _row_seconds(self.estimated_catalogue_lines, self.seconds_per_line)


class AisleCage(models.Model):
    """A cage set up in Settings for an aisle (e.g. "A10"), with its own line
    count. This is a standing catalogue setup, separate from the per-day
    ``CageLog`` records on the Daily Log."""

    aisle = models.ForeignKey(Aisle, on_delete=models.CASCADE, related_name="cages")
    code = models.CharField(max_length=20)  # e.g. "A10", "B11"
    lines = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1_000_000)]
    )
    seconds_per_line = seconds_per_line_field()
    # Quick entry: the cage's total time in minutes. When set, it is the
    # cage's time and lines x seconds-per-line is not used.
    minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1_440)],
    )

    class Meta:
        ordering = ["aisle_id", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["aisle", "code"], name="unique_cage_code_per_aisle"
            )
        ]

    def __str__(self) -> str:
        return f"{self.aisle.label} / Cage {self.code}"

    @property
    def row_lines(self) -> int:
        return self.lines

    @property
    def estimated_seconds(self):
        if self.minutes is not None:
            return self.minutes * 60
        return _row_seconds(self.lines, self.seconds_per_line)


class CageFeed(models.Model):
    """How much of a Plan cage (0-100 %) was fed onto the shelf on a date."""

    cage = models.ForeignKey(AisleCage, on_delete=models.CASCADE, related_name="feeds")
    feed_date = models.DateField()
    percent = models.PositiveSmallIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    class Meta:
        ordering = ["feed_date", "cage_id"]
        unique_together = [("cage", "feed_date")]

    def __str__(self) -> str:
        return f"{self.cage} on {self.feed_date}: {self.percent}%"



class CageSession(models.Model):
    """One real refeeding session of a Plan cage (Clock page). A cage keeps
    every session as history (training data); it may span several days. The
    "open" session is the cage's latest row with no end_at."""

    cage = models.ForeignKey(AisleCage, on_delete=models.CASCADE, related_name="sessions")
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_at", "id"]
        indexes = [models.Index(fields=["cage", "end_at"])]

    def __str__(self) -> str:
        return f"{self.cage} {self.start_at:%Y-%m-%d %H:%M}"

    @property
    def duration_seconds(self):
        if self.start_at is None or self.end_at is None:
            return None
        return int((self.end_at - self.start_at).total_seconds())


class AssumptionSet(models.Model):
    """An immutable, versioned set of planning assumptions for one user."""

    owner = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="assumption_sets")
    version = models.PositiveIntegerField()
    effective_at = models.DateTimeField(auto_now_add=True)

    # A: rough daily cage range.
    cages_min = models.PositiveIntegerField(default=2, validators=COUNT_VALIDATORS)
    cages_max = models.PositiveIntegerField(default=5, validators=COUNT_VALIDATORS)
    # B/C: forecast inputs.
    default_lines_per_cage = models.PositiveIntegerField(default=100, validators=COUNT_VALIDATORS)
    units_per_line = models.PositiveIntegerField(default=5, validators=COUNT_VALIDATORS)
    # D/E/F/G: time components.
    find_sec = models.PositiveIntegerField(default=30, validators=SMALL_SEC_VALIDATORS)
    unpack_sec = models.PositiveIntegerField(default=10, validators=SMALL_SEC_VALIDATORS)
    seconds_per_unit = models.PositiveIntegerField(default=1, validators=SMALL_SEC_VALIDATORS)
    other_sec = models.PositiveIntegerField(default=0, validators=SMALL_SEC_VALIDATORS)

    provenance = models.CharField(
        max_length=16, choices=Provenance.choices, default=Provenance.ASSUMED
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "version"], name="unique_assumption_version_per_owner"
            )
        ]

    def __str__(self) -> str:
        return f"Assumptions v{self.version} ({self.owner_id})"

    def snapshot(self) -> dict:
        """The subset of fields that define a forecast, for immutable storage."""
        return {
            "version": self.version,
            "find_sec": self.find_sec,
            "unpack_sec": self.unpack_sec,
            "seconds_per_unit": self.seconds_per_unit,
            "units_per_line": self.units_per_line,
            "other_sec": self.other_sec,
            "default_lines_per_cage": self.default_lines_per_cage,
        }


class WorkDay(models.Model):
    owner = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="work_days")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="work_days")
    work_date = models.DateField()

    # The assumption version used, plus an immutable snapshot of its values so
    # the day's forecast is reproducible and unaffected by later versions.
    assumption_set = models.ForeignKey(
        AssumptionSet, on_delete=models.PROTECT, related_name="work_days"
    )
    assumption_snapshot = models.JSONField()

    # Optional context for the "estimated workload gap" flag.
    shift_minutes = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(1440)]
    )
    # Day-level interruptions (customer service etc.), kept separate from active
    # replenishment time. Detailed per-event logging is Release 2.
    interrupted_minutes = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(1440)]
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-work_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "store", "work_date"],
                name="unique_workday_per_owner_store_date",
            )
        ]

    def __str__(self) -> str:
        return f"{self.work_date} @ {self.store_id}"


class CageLog(models.Model):
    work_day = models.ForeignKey(WorkDay, on_delete=models.CASCADE, related_name="cages")
    aisle = models.ForeignKey(
        Aisle, on_delete=models.SET_NULL, null=True, blank=True, related_name="cage_logs"
    )
    reference = models.CharField(max_length=60, blank=True, default="")

    # Forecast inputs (None => fall back to the work day's assumption snapshot).
    line_count = models.PositiveIntegerField(null=True, blank=True, validators=COUNT_VALIDATORS)
    units_per_line = models.PositiveIntegerField(
        null=True, blank=True, validators=COUNT_VALIDATORS
    )

    # Immutable forecast snapshot for this cage (seconds), computed on save.
    estimated_seconds = models.PositiveIntegerField(default=0, validators=SEC_VALIDATORS)

    # Measured actual active replenishment time (seconds). Never derived from
    # the forecast; entered by the user.
    actual_active_seconds = models.PositiveIntegerField(
        null=True, blank=True, validators=SEC_VALIDATORS
    )

    status = models.CharField(
        max_length=16, choices=CageStatus.choices, default=CageStatus.PLANNED
    )
    # For partial cages: how many lines were actually completed.
    completed_line_count = models.PositiveIntegerField(
        null=True, blank=True, validators=COUNT_VALIDATORS
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"Cage {self.id} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        # Recompute the forecast snapshot from the work day's immutable
        # assumption snapshot and this cage's own overrides. A None override
        # falls back to the snapshot default; an explicit 0 is respected.
        assumptions = Assumptions.from_mapping(self.work_day.assumption_snapshot)
        self.estimated_seconds = estimated_cage_seconds(
            assumptions,
            lines_in_cage=self.line_count,
            units_per_line=self.units_per_line,
        )
        super().save(*args, **kwargs)

    @property
    def is_fully_replenished(self) -> bool:
        return self.status == CageStatus.COMPLETE
