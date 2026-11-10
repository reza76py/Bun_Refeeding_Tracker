"""Settings page (ADMIN only): testing tools.

Change a cage's created_at so the age colours (green -> red) can be previewed.
Access comes from roles.PageAccess: /api/admin/... belongs to the "settings"
page, which only ADMIN (and superusers) have.
"""

from __future__ import annotations

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from tracker import services
from tracker.clock_views import _manual_dt
from tracker.models import AisleCage


def _row(cage):
    return {
        "cage_id": cage.id,
        "code": cage.code,
        "aisle_label": cage.aisle.label,
        "created_at": cage.created_at,
    }


def _cages():
    return AisleCage.objects.filter(
        aisle__store=services.get_shared_store()
    ).select_related("aisle")


class AdminCageListView(APIView):
    """GET /api/admin/cages/: every cage in the shared workspace."""

    def get(self, request):
        cages = _cages().order_by("aisle__label", "code")
        return Response([_row(c) for c in cages])


class AdminCageCreatedView(APIView):
    """PATCH /api/admin/cages/<id>/created/ {created_at}: backdate a cage.

    A time without a zone is read as Brisbane local time (what a
    datetime-local input sends). created_at is auto_now_add, so it is set with
    a queryset update, which skips that."""

    def patch(self, request, pk):
        cage = generics.get_object_or_404(_cages(), pk=pk)
        when = _manual_dt(request.data.get("created_at"), "created_at")
        AisleCage.objects.filter(pk=cage.pk).update(created_at=when)
        cage.refresh_from_db()
        return Response(_row(cage))
