"""Clock page: real start / end sessions per Plan cage.

Every session is kept as its own row (history / training data). A session can
span several days, so full timezone-aware datetimes are stored. The "open"
session of a cage is its latest row with no end_at.
"""

from __future__ import annotations

import csv

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from tracker.models import Aisle, AisleCage, CageFeed, CageSession


def _owned_cage(request, lock=False):
    qs = AisleCage.objects.filter(aisle__store__owner=request.user)
    if lock:
        qs = qs.select_for_update()
    return generics.get_object_or_404(qs, id=request.data.get("cage_id"))


def _open_session(cage):
    return (
        CageSession.objects.filter(cage=cage, end_at__isnull=True)
        .order_by("-start_at", "-id")
        .first()
    )


def _session_json(s):
    if s is None:
        return None
    return {
        "id": s.id,
        "start_at": s.start_at,
        "end_at": s.end_at,
        "duration_seconds": s.duration_seconds,
    }


def _iso(dt):
    return timezone.localtime(dt).isoformat() if dt else ""


class ClockSummaryView(APIView):
    """GET /api/clock/summary/: aisles (Plan order) → cages with their open
    session and last finished session."""

    def get(self, request):
        aisles = Aisle.objects.filter(store__owner=request.user).prefetch_related("cages")
        open_by_cage, last_by_cage = {}, {}
        # Ascending order, so later rows overwrite earlier ones.
        for s in CageSession.objects.filter(
            cage__aisle__store__owner=request.user
        ).order_by("start_at", "id"):
            if s.end_at is None:
                open_by_cage[s.cage_id] = s
            else:
                last_by_cage[s.cage_id] = s
        out = []
        for aisle in aisles:
            cages = []
            for c in aisle.cages.all():
                o = open_by_cage.get(c.id)
                cages.append(
                    {
                        "cage_id": c.id,
                        "code": c.code,
                        "open_session": o and {"id": o.id, "start_at": o.start_at},
                        "last_session": _session_json(last_by_cage.get(c.id)),
                    }
                )
            out.append({"aisle_id": aisle.id, "label": aisle.label, "cages": cages})
        return Response({"aisles": out})


class ClockStartView(APIView):
    """POST /api/clock/start {cage_id}: open a session (or return the open one)."""

    def post(self, request):
        with transaction.atomic():
            cage = _owned_cage(request, lock=True)  # serialises double taps
            session = _open_session(cage)
            if session is None:
                session = CageSession.objects.create(cage=cage, start_at=timezone.now())
        return Response(_session_json(session))


class ClockEndView(APIView):
    """POST /api/clock/end {cage_id}: close the cage's open session, and mark
    the cage 100% fed on Today for the (Brisbane) date it ended."""

    def post(self, request):
        with transaction.atomic():
            cage = _owned_cage(request, lock=True)
            session = _open_session(cage)
            if session is None:
                raise ValidationError({"detail": "This cage has no running session."})
            session.end_at = timezone.now()
            session.save(update_fields=["end_at"])
            CageFeed.objects.update_or_create(
                cage=cage,
                feed_date=timezone.localdate(session.end_at),
                defaults={"percent": 100},
            )
        return Response(_session_json(session))


def _manual_dt(value, field):
    """ISO datetime; a value without a zone is read as Brisbane local time
    (what an <input type="datetime-local"> sends)."""
    dt = parse_datetime(str(value)) if value else None
    if dt is None:
        raise ValidationError({field: "Use a date and time, e.g. 2026-11-10T06:05."})
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


class ClockManualView(APIView):
    """POST /api/clock/manual {cage_id, start_at, end_at}: record a finished
    session by hand, and mark the cage 100% fed on Today for the (Brisbane)
    date it ended — the same as ending it on the Clock page."""

    def post(self, request):
        start_at = _manual_dt(request.data.get("start_at"), "start_at")
        end_at = _manual_dt(request.data.get("end_at"), "end_at")
        if end_at < start_at:
            raise ValidationError({"end_at": "End must be after start."})
        with transaction.atomic():
            cage = _owned_cage(request, lock=True)
            session = CageSession.objects.create(
                cage=cage, start_at=start_at, end_at=end_at
            )
            CageFeed.objects.update_or_create(
                cage=cage,
                feed_date=timezone.localdate(end_at),
                defaults={"percent": 100},
            )
        return Response(_session_json(session), status=201)


class ClockCancelView(APIView):
    """POST /api/clock/cancel {cage_id}: delete the open session (mis-tap)."""

    def post(self, request):
        with transaction.atomic():
            cage = _owned_cage(request, lock=True)
            session = _open_session(cage)
            if session is not None:
                session.delete()
        return Response({"cancelled": session is not None})


class ClockExportView(APIView):
    """GET /api/clock/export.csv: every session of this user, one row each."""

    def perform_content_negotiation(self, request, force=False):
        # Always answer with CSV, whatever the Accept header says.
        return super().perform_content_negotiation(request, force=True)

    def get(self, request):
        sessions = (
            CageSession.objects.filter(cage__aisle__store__owner=request.user)
            .select_related("cage__aisle")
            .order_by("start_at", "id")
        )
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="cage_sessions.csv"'
        w = csv.writer(resp)
        w.writerow(
            [
                "aisle_label",
                "cage_code",
                "planned_minutes",
                "start_at",
                "end_at",
                "duration_seconds",
                "created_at",
            ]
        )
        for s in sessions:
            secs = s.cage.estimated_seconds
            dur = s.duration_seconds
            w.writerow(
                [
                    s.cage.aisle.label,
                    s.cage.code,
                    "" if secs is None else round(secs / 60, 2),
                    _iso(s.start_at),
                    _iso(s.end_at),
                    "" if dur is None else dur,
                    _iso(s.created_at),
                ]
            )
        return resp
