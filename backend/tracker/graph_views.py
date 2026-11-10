"""Graph: every unfinished cage in the shared workspace, timed from creation.

A cage is FINISHED (left out) once it has been ended on Clock (a session with
end_at set) or marked 100% on Today (a CageFeed with percent == 100). Deleted
cages no longer exist, so they drop out on their own.

Shown on every page, so any logged-in role may read it: the per-page role
check (roles.PageAccess) is deliberately not applied here.
"""

from __future__ import annotations

from django.db.models import Exists, OuterRef
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from tracker import services
from tracker.models import AisleCage, CageFeed, CageSession


class GraphRunningView(APIView):
    """GET /api/graph/running/: [{cage_id, code, aisle_label, created_at,
    running}],
    oldest (longest unfinished) first."""

    permission_classes = [IsAuthenticated]  # all roles, not page-gated

    def get(self, request):
        ended = CageSession.objects.filter(cage=OuterRef("pk"), end_at__isnull=False)
        fed = CageFeed.objects.filter(cage=OuterRef("pk"), percent=100)
        open_session = CageSession.objects.filter(
            cage=OuterRef("pk"), start_at__isnull=False, end_at__isnull=True
        )
        cages = (
            AisleCage.objects.filter(aisle__store=services.get_shared_store())
            .annotate(ended=Exists(ended), fed=Exists(fed), running=Exists(open_session))
            .filter(ended=False, fed=False)
            .select_related("aisle")
            .order_by("created_at", "id")
        )
        return Response(
            [
                {
                    "cage_id": c.id,
                    "code": c.code,
                    "aisle_label": c.aisle.label,
                    "created_at": c.created_at,
                    # Started on Clock and not ended yet (being worked on).
                    "running": c.running,
                }
                for c in cages
            ]
        )
