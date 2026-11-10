"""DRF serializers. Read serializers expose computed/snapshot fields as
read-only; write serializers validate user input (non-negative, bounded)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from tracker.models import (
    Aisle,
    AisleCage,
    AssumptionSet,
    Bay,
    CageLog,
    CageStatus,
    Store,
    WorkDay,
)
from tracker.roles import role_and_pages

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    pages = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "role", "pages"]

    def get_role(self, user):
        return role_and_pages(user)[0]

    def get_pages(self, user):
        return role_and_pages(user)[1]


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["id", "name", "timezone"]


class BaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Bay
        fields = [
            "id",
            "aisle",
            "bay_number",
            "estimated_catalogue_lines",
            "seconds_per_line",
            "estimated_seconds",
        ]
        read_only_fields = ["aisle", "estimated_seconds"]

    def validate_bay_number(self, value):
        # The aisle is never in the body: it comes from the instance (update)
        # or from the URL via serializer context (create).
        aisle = self.instance.aisle if self.instance else self.context.get("aisle")
        if aisle is not None:
            clash = Bay.objects.filter(aisle=aisle, bay_number=value)
            if self.instance:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError(
                    f"Bay {value} already exists in {aisle.label}."
                )
        return value


class BayCreateSerializer(BaySerializer):
    """Create a bay under /api/aisles/{aisle_id}/bays/ — aisle from the URL."""

    class Meta(BaySerializer.Meta):
        pass


class AisleCageSerializer(serializers.ModelSerializer):
    """Settings cage for an aisle. The aisle comes from the URL (create) or
    the instance (update), never from the body."""

    class Meta:
        model = AisleCage
        fields = [
            "id",
            "aisle",
            "code",
            "lines",
            "seconds_per_line",
            "minutes",
            "estimated_seconds",
        ]
        read_only_fields = ["aisle", "estimated_seconds"]

    def validate_code(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Cage number cannot be blank.")
        aisle = self.instance.aisle if self.instance else self.context.get("aisle")
        if aisle is not None:
            clash = AisleCage.objects.filter(aisle=aisle, code__iexact=value)
            if self.instance:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError(
                    f"Cage {value} already exists in {aisle.label}."
                )
        return value


class AisleSerializer(serializers.ModelSerializer):
    bays = BaySerializer(many=True, read_only=True)
    cages = AisleCageSerializer(many=True, read_only=True)
    catalogue_lines = serializers.SerializerMethodField()
    estimated_seconds = serializers.IntegerField(read_only=True, allow_null=True)
    rows_missing_time = serializers.IntegerField(read_only=True)

    class Meta:
        model = Aisle
        fields = [
            "id",
            "store",
            "label",
            "active",
            "aisle_total_lines",
            "detail_mode",
            "cages",
            "bays",
            "catalogue_lines",
            "estimated_seconds",
            "rows_missing_time",
        ]
        read_only_fields = ["store"]

    def validate_label(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Label cannot be blank.")
        store = self.instance.store if self.instance else self.context.get("store")
        if store is not None:
            clash = Aisle.objects.filter(store=store, label__iexact=value)
            if self.instance:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError(f"{value} already exists.")
        return value

    def get_catalogue_lines(self, obj: Aisle) -> int:
        return obj.catalogue_lines


class AssumptionSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssumptionSet
        fields = [
            "id",
            "version",
            "effective_at",
            "cages_min",
            "cages_max",
            "default_lines_per_cage",
            "units_per_line",
            "find_sec",
            "unpack_sec",
            "seconds_per_unit",
            "other_sec",
            "provenance",
            "notes",
        ]
        read_only_fields = ["id", "version", "effective_at"]


class AssumptionCreateSerializer(serializers.Serializer):
    """Create a new immutable assumption version. Any omitted field inherits
    from the current active version (handled in the service)."""

    cages_min = serializers.IntegerField(required=False, min_value=0, max_value=100)
    cages_max = serializers.IntegerField(required=False, min_value=0, max_value=100)
    default_lines_per_cage = serializers.IntegerField(
        required=False, min_value=0, max_value=100_000
    )
    units_per_line = serializers.IntegerField(required=False, min_value=0, max_value=100_000)
    find_sec = serializers.IntegerField(required=False, min_value=0, max_value=36_000)
    unpack_sec = serializers.IntegerField(required=False, min_value=0, max_value=36_000)
    seconds_per_unit = serializers.IntegerField(required=False, min_value=0, max_value=36_000)
    other_sec = serializers.IntegerField(required=False, min_value=0, max_value=36_000)
    provenance = serializers.ChoiceField(
        choices=["assumed", "user_estimate", "measured"], required=False
    )
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate(self, attrs):
        cmin = attrs.get("cages_min")
        cmax = attrs.get("cages_max")
        if cmin is not None and cmax is not None and cmin > cmax:
            raise serializers.ValidationError(
                {"cages_max": "cages_max must be greater than or equal to cages_min."}
            )
        return attrs


class CalculatorPreviewSerializer(serializers.Serializer):
    """Validated inputs for a non-persisted forecast preview."""

    find_sec = serializers.IntegerField(min_value=0, max_value=36_000)
    unpack_sec = serializers.IntegerField(min_value=0, max_value=36_000)
    seconds_per_unit = serializers.IntegerField(min_value=0, max_value=36_000)
    units_per_line = serializers.IntegerField(min_value=0, max_value=100_000)
    other_sec = serializers.IntegerField(min_value=0, max_value=36_000, default=0)
    lines_per_cage = serializers.IntegerField(min_value=0, max_value=100_000)
    cages = serializers.IntegerField(min_value=0, max_value=100)
    cages_min = serializers.IntegerField(min_value=0, max_value=100, required=False)
    cages_max = serializers.IntegerField(min_value=0, max_value=100, required=False)


class CageLogSerializer(serializers.ModelSerializer):
    estimated_hm = serializers.SerializerMethodField()
    actual_active_hm = serializers.SerializerMethodField()

    class Meta:
        model = CageLog
        fields = [
            "id",
            "work_day",
            "aisle",
            "reference",
            "line_count",
            "units_per_line",
            "estimated_seconds",   # forecast snapshot (read-only)
            "estimated_hm",
            "actual_active_seconds",  # measured actual
            "actual_active_hm",
            "status",
            "completed_line_count",
            "notes",
        ]
        read_only_fields = ["work_day", "estimated_seconds"]

    def get_estimated_hm(self, obj: CageLog) -> str:
        from tracker.calculations import seconds_to_hm

        return seconds_to_hm(obj.estimated_seconds)

    def get_actual_active_hm(self, obj: CageLog):
        from tracker.calculations import seconds_to_hm

        if obj.actual_active_seconds is None:
            return None
        return seconds_to_hm(obj.actual_active_seconds)

    def validate_status(self, value):
        if value not in CageStatus.values:
            raise serializers.ValidationError("Unknown status.")
        return value


class CageLogCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CageLog
        fields = [
            "aisle",
            "reference",
            "line_count",
            "units_per_line",
            "actual_active_seconds",
            "status",
            "completed_line_count",
            "notes",
        ]


class WorkDaySerializer(serializers.ModelSerializer):
    cages = CageLogSerializer(many=True, read_only=True)
    estimated_day_seconds = serializers.SerializerMethodField()
    measured_active_seconds = serializers.SerializerMethodField()

    class Meta:
        model = WorkDay
        fields = [
            "id",
            "store",
            "work_date",
            "assumption_set",
            "assumption_snapshot",  # immutable forecast basis (read-only)
            "shift_minutes",
            "interrupted_minutes",
            "notes",
            "cages",
            "estimated_day_seconds",
            "measured_active_seconds",
            "created_at",
        ]
        read_only_fields = [
            "assumption_set",
            "assumption_snapshot",
            "created_at",
        ]

    def get_estimated_day_seconds(self, obj: WorkDay) -> int:
        return sum(c.estimated_seconds for c in obj.cages.all())

    def get_measured_active_seconds(self, obj: WorkDay):
        values = [
            c.actual_active_seconds
            for c in obj.cages.all()
            if c.actual_active_seconds is not None
        ]
        return sum(values) if values else None


class WorkDayCreateSerializer(serializers.Serializer):
    work_date = serializers.DateField()
    store = serializers.IntegerField(required=False)
    shift_minutes = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=1440
    )
    interrupted_minutes = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=1440
    )
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    cages = CageLogCreateSerializer(many=True, required=False)
