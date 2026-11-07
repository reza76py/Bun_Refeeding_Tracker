"""API views.

Every owned queryset is filtered by ``request.user`` so one user can never
read or modify another's records. Forecasts are computed by the pure
calculation module; measured actuals are stored and returned distinctly.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError, transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from tracker import services
from tracker.calculations import (
    Assumptions,
    estimated_cage_seconds,
    estimated_line_seconds,
    scenario_table,
    seconds_to_hm,
)
from tracker.models import Aisle, AisleCage, AssumptionSet, Bay, CageLog, Store, WorkDay
from tracker.serializers import (
    AisleCageSerializer,
    AisleSerializer,
    AssumptionCreateSerializer,
    AssumptionSetSerializer,
    BayCreateSerializer,
    BaySerializer,
    CageLogCreateSerializer,
    CageLogSerializer,
    CalculatorPreviewSerializer,
    StoreSerializer,
    UserSerializer,
    WorkDayCreateSerializer,
    WorkDaySerializer,
)


# --- Auth -----------------------------------------------------------------

@method_decorator(ensure_csrf_cookie, name="get")
class CsrfView(APIView):
    """GET to receive the CSRF cookie before any unsafe request."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"detail": "CSRF cookie set."})


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    username = (request.data.get("username") or "").strip()
    password = request.data.get("password") or ""
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {"detail": "Invalid username or password."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    login(request, user)
    return Response(UserSerializer(user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request)
    return Response({"detail": "Logged out."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response(UserSerializer(request.user).data)


# --- Ownership mixin ------------------------------------------------------

class OwnedQuerysetMixin:
    """Restrict a queryset to records owned by the requesting user."""

    owner_field = "owner"

    def get_queryset(self):
        return super().get_queryset().filter(**{self.owner_field: self.request.user})


# --- Store ----------------------------------------------------------------

class StoreListView(OwnedQuerysetMixin, generics.ListCreateAPIView):
    serializer_class = StoreSerializer
    queryset = Store.objects.all()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class StoreDetailView(OwnedQuerysetMixin, generics.RetrieveUpdateAPIView):
    serializer_class = StoreSerializer
    queryset = Store.objects.all()


# --- Aisles & bays --------------------------------------------------------

def _save_or_400(serializer, message, **kwargs):
    """Save, turning a unique-constraint race (missed by serializer
    validation) into a 400 instead of a 500."""
    try:
        with transaction.atomic():
            serializer.save(**kwargs)
    except IntegrityError:
        raise ValidationError({"detail": message})


class AisleListView(generics.ListCreateAPIView):
    serializer_class = AisleSerializer

    def get_queryset(self):
        return (
            Aisle.objects.filter(store__owner=self.request.user)
            .prefetch_related("bays", "cages")
            .select_related("store")
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.request.method == "POST":
            ctx["store"] = services.default_store(self.request.user)
        return ctx

    def perform_create(self, serializer):
        store = services.default_store(self.request.user)
        _save_or_400(serializer, "This aisle already exists.", store=store)

    @transaction.atomic
    def delete(self, request):
        """DELETE /api/aisles/ removes ALL of this user's aisles, with their
        cages and bays. Logged work-day cages keep their history (aisle set
        to null)."""
        deleted = Aisle.objects.filter(store__owner=request.user)
        count = deleted.count()
        deleted.delete()
        return Response({"deleted_aisles": count}, status=status.HTTP_200_OK)


class AisleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH (label, active)/DELETE one aisle. DELETE cascades its bays;
    cage logs that referenced the aisle keep their history (aisle set null)."""

    serializer_class = AisleSerializer

    def get_queryset(self):
        return (
            Aisle.objects.filter(store__owner=self.request.user)
            .prefetch_related("bays", "cages")
            .select_related("store")
        )

    def perform_update(self, serializer):
        _save_or_400(serializer, "This aisle already exists.")


class BayListView(generics.ListCreateAPIView):
    """GET/POST bays for one aisle: /api/aisles/{aisle_id}/bays/."""

    serializer_class = BaySerializer

    def get_queryset(self):
        return Bay.objects.filter(
            aisle_id=self.kwargs["aisle_id"], aisle__store__owner=self.request.user
        )

    def get_serializer_class(self):
        return BayCreateSerializer if self.request.method == "POST" else BaySerializer

    def _aisle(self):
        return generics.get_object_or_404(
            Aisle, id=self.kwargs["aisle_id"], store__owner=self.request.user
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.request.method == "POST":
            ctx["aisle"] = self._aisle()
        return ctx

    def perform_create(self, serializer):
        _save_or_400(
            serializer, "This bay number already exists in the aisle.",
            aisle=serializer.context["aisle"],
        )


class BayDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BaySerializer

    def get_queryset(self):
        return Bay.objects.filter(aisle__store__owner=self.request.user)

    def perform_update(self, serializer):
        _save_or_400(serializer, "This bay number already exists in the aisle.")


class AisleCageListView(generics.ListCreateAPIView):
    """GET/POST Settings cages for one aisle: /api/aisles/{aisle_id}/cages/."""

    serializer_class = AisleCageSerializer

    def get_queryset(self):
        return AisleCage.objects.filter(
            aisle_id=self.kwargs["aisle_id"], aisle__store__owner=self.request.user
        )

    def _aisle(self):
        return generics.get_object_or_404(
            Aisle, id=self.kwargs["aisle_id"], store__owner=self.request.user
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.request.method == "POST":
            ctx["aisle"] = self._aisle()
        return ctx

    def perform_create(self, serializer):
        _save_or_400(
            serializer, "This cage number already exists in the aisle.",
            aisle=serializer.context["aisle"],
        )


class AisleCageDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AisleCageSerializer

    def get_queryset(self):
        return AisleCage.objects.filter(aisle__store__owner=self.request.user)

    def perform_update(self, serializer):
        _save_or_400(serializer, "This cage number already exists in the aisle.")


class CatalogueSummaryView(APIView):
    def get(self, request):
        aisles = (
            Aisle.objects.filter(store__owner=request.user)
            .prefetch_related("bays", "cages")
            .order_by("label")
        )
        per_aisle = []
        combined = 0
        combined_seconds = None
        for aisle in aisles:
            total = aisle.catalogue_lines
            combined += total
            secs = aisle.estimated_seconds
            if secs is not None:
                combined_seconds = (combined_seconds or 0) + secs
            per_aisle.append(
                {
                    "aisle_id": aisle.id,
                    "label": aisle.label,
                    "catalogue_lines": total,
                    "estimated_seconds": secs,
                }
            )
        return Response(
            {
                "per_aisle": per_aisle,
                "combined_catalogue_lines": combined,
                # Lines x seconds-per-line entered in Settings; None if no
                # cage/bay has a time yet.
                "combined_estimated_seconds": combined_seconds,
                "note": (
                    "Catalogue lines describe area size only — assumed distinct "
                    "stocked lines, not units on shelves and not daily "
                    "replenishment demand."
                ),
            }
        )


# --- Assumptions ----------------------------------------------------------

class AssumptionListCreateView(generics.ListCreateAPIView):
    def get_queryset(self):
        return AssumptionSet.objects.filter(owner=self.request.user)

    def get_serializer_class(self):
        return (
            AssumptionCreateSerializer
            if self.request.method == "POST"
            else AssumptionSetSerializer
        )

    def create(self, request, *args, **kwargs):
        serializer = AssumptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_version = services.create_assumption_version(
            request.user, **serializer.validated_data
        )
        return Response(
            AssumptionSetSerializer(new_version).data, status=status.HTTP_201_CREATED
        )


class ActiveAssumptionView(APIView):
    def get(self, request):
        active = services.active_assumption_set(request.user)
        return Response(AssumptionSetSerializer(active).data)


# --- Calculator (no persistence) -----------------------------------------

class CalculatorPreviewView(APIView):
    def post(self, request):
        serializer = CalculatorPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        a = Assumptions(
            find_sec=d["find_sec"],
            unpack_sec=d["unpack_sec"],
            seconds_per_unit=d["seconds_per_unit"],
            units_per_line=d["units_per_line"],
            other_sec=d["other_sec"],
            default_lines_per_cage=d["lines_per_cage"],
        )
        per_line = estimated_line_seconds(a)
        per_cage = estimated_cage_seconds(a)
        cages = d["cages"]
        day = per_cage * cages
        cmin = d.get("cages_min", 2)
        cmax = d.get("cages_max", 5)
        return Response(
            {
                "per_line_seconds": per_line,
                "per_line_hm": seconds_to_hm(per_line),
                "per_cage_seconds": per_cage,
                "per_cage_hm": seconds_to_hm(per_cage),
                "cages": cages,
                "day_seconds": day,
                "day_hm": seconds_to_hm(day),
                "scenarios": scenario_table(a, cmin, cmax),
            }
        )


# --- Work days & cages ----------------------------------------------------

def _parse_date(value, fallback=None):
    if not value:
        return fallback
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return fallback


class WorkDayListCreateView(APIView):
    def get(self, request):
        qs = WorkDay.objects.filter(owner=request.user).prefetch_related("cages")
        d_from = _parse_date(request.query_params.get("from"))
        d_to = _parse_date(request.query_params.get("to"))
        if d_from:
            qs = qs.filter(work_date__gte=d_from)
        if d_to:
            qs = qs.filter(work_date__lte=d_to)
        return Response(WorkDaySerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        serializer = WorkDayCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        store_id = data.get("store")
        if store_id:
            store = generics.get_object_or_404(
                Store, id=store_id, owner=request.user
            )
        else:
            store = services.default_store(request.user)

        active = services.active_assumption_set(request.user)
        try:
            work_day = WorkDay.objects.create(
                owner=request.user,
                store=store,
                work_date=data["work_date"],
                assumption_set=active,
                assumption_snapshot=active.snapshot(),
                shift_minutes=data.get("shift_minutes"),
                interrupted_minutes=data.get("interrupted_minutes"),
                notes=data.get("notes", ""),
            )
        except IntegrityError:
            return Response(
                {"detail": "A work day for this date and store already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for cage_data in data.get("cages", []):
            aisle = cage_data.get("aisle")
            if aisle is not None and aisle.store.owner_id != request.user.id:
                return Response(
                    {"detail": "Aisle does not belong to you."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            CageLog.objects.create(work_day=work_day, **cage_data)

        return Response(
            WorkDaySerializer(work_day).data, status=status.HTTP_201_CREATED
        )


class WorkDayDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = WorkDaySerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return WorkDay.objects.filter(owner=self.request.user).prefetch_related("cages")


class CageCreateView(APIView):
    def post(self, request, work_day_id):
        work_day = generics.get_object_or_404(
            WorkDay, id=work_day_id, owner=request.user
        )
        serializer = CageLogCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        aisle = serializer.validated_data.get("aisle")
        if aisle is not None and aisle.store.owner_id != request.user.id:
            return Response(
                {"detail": "Aisle does not belong to you."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cage = CageLog.objects.create(work_day=work_day, **serializer.validated_data)
        return Response(CageLogSerializer(cage).data, status=status.HTTP_201_CREATED)


class CageDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CageLogSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return CageLog.objects.filter(work_day__owner=self.request.user)

    def perform_update(self, serializer):
        cage = serializer.save()
        # Re-run the forecast snapshot if a forecast input changed.
        cage.save()


# --- Dashboard ------------------------------------------------------------

class DashboardSummaryView(APIView):
    def get(self, request):
        today = _parse_date(request.query_params.get("date"), fallback=date.today())
        active = services.active_assumption_set(request.user)
        a = Assumptions.from_mapping(active.snapshot())

        work_day = (
            WorkDay.objects.filter(owner=request.user, work_date=today)
            .prefetch_related("cages")
            .first()
        )

        payload = {
            "date": today.isoformat(),
            "active_assumptions": AssumptionSetSerializer(active).data,
            "scenarios": scenario_table(a, active.cages_min, active.cages_max),
            "work_day": None,
        }

        if work_day is not None:
            cages = list(work_day.cages.all())
            estimated = sum(c.estimated_seconds for c in cages)
            measured_vals = [
                c.actual_active_seconds
                for c in cages
                if c.actual_active_seconds is not None
            ]
            measured = sum(measured_vals) if measured_vals else None
            interruptions_sec = (
                (work_day.interrupted_minutes or 0) * 60
                if work_day.interrupted_minutes is not None
                else None
            )
            gap = None
            if work_day.shift_minutes:
                gap = estimated - work_day.shift_minutes * 60
            payload["work_day"] = {
                "id": work_day.id,
                "cage_count": len(cages),
                "estimated_seconds": estimated,
                "estimated_hm": seconds_to_hm(estimated),
                "measured_active_seconds": measured,
                "measured_active_hm": seconds_to_hm(measured) if measured is not None else None,
                "interrupted_minutes": work_day.interrupted_minutes,
                "shift_minutes": work_day.shift_minutes,
                "forecast_vs_actual_seconds": (
                    None if measured is None else measured - estimated
                ),
                "workload_gap_seconds": gap,  # positive => forecast exceeds shift
                "shift_minutes_note": (
                    "A full shift is not all available for restocking; "
                    "customer service reduces it."
                ),
            }
        return Response(payload)


# --- Reports --------------------------------------------------------------

class ReportsSummaryView(APIView):
    def get(self, request):
        today = date.today()
        d_from = _parse_date(
            request.query_params.get("from"), fallback=today - timedelta(days=30)
        )
        d_to = _parse_date(request.query_params.get("to"), fallback=today)

        days = list(
            WorkDay.objects.filter(
                owner=request.user, work_date__gte=d_from, work_date__lte=d_to
            ).prefetch_related("cages")
        )

        total_estimated = 0
        total_measured = 0
        measured_cage_count = 0
        complete_cage_count = 0
        total_interrupt_min = 0
        measured_lines = 0
        measured_line_seconds = 0

        rows = []
        for wd in days:
            cages = list(wd.cages.all())
            est = sum(c.estimated_seconds for c in cages)
            meas_vals = [
                c.actual_active_seconds
                for c in cages
                if c.actual_active_seconds is not None
            ]
            meas = sum(meas_vals) if meas_vals else None
            total_estimated += est
            if meas is not None:
                total_measured += meas
                measured_cage_count += len(meas_vals)
            if wd.interrupted_minutes:
                total_interrupt_min += wd.interrupted_minutes
            for c in cages:
                if c.status == "complete":
                    complete_cage_count += 1
                if c.actual_active_seconds is not None and c.line_count:
                    measured_lines += c.line_count
                    measured_line_seconds += c.actual_active_seconds
            rows.append(
                {
                    "work_date": wd.work_date.isoformat(),
                    "estimated_seconds": est,
                    "measured_active_seconds": meas,
                    "interrupted_minutes": wd.interrupted_minutes,
                    "variance_seconds": None if meas is None else meas - est,
                }
            )

        avg_seconds_per_line = (
            round(measured_line_seconds / measured_lines, 1) if measured_lines else None
        )
        avg_net_per_cage = (
            round(total_measured / measured_cage_count) if measured_cage_count else None
        )

        return Response(
            {
                "from": d_from.isoformat(),
                "to": d_to.isoformat(),
                "day_count": len(days),
                "total_estimated_seconds": total_estimated,
                "total_estimated_hm": seconds_to_hm(total_estimated),
                "total_measured_active_seconds": total_measured if days else 0,
                "total_measured_active_hm": seconds_to_hm(total_measured),
                "complete_cage_count": complete_cage_count,
                "avg_net_seconds_per_measured_cage": avg_net_per_cage,
                "avg_measured_seconds_per_line": avg_seconds_per_line,
                "total_interrupted_minutes": total_interrupt_min,
                "rows": rows,
            }
        )
