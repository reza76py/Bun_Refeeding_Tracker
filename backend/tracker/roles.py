"""Demo roles and the pages each may use (the single source of truth).

    GI    -> Plan
    MNG   -> Today
    MBR   -> Clock
    ADMIN -> Plan, Today, Clock, Settings (admin-only testing tools)

A superuser counts as admin. An account in none of these groups (e.g. an
existing personal account created before roles existed) also keeps full
access, so nobody is locked out.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

# Every page, in nav order. Only ADMIN (and superusers) get "settings".
ALL_PAGES = ["plan", "today", "clock", "settings"]

# Group name -> (role, pages). Order = priority when a user is in several.
ROLE_PAGES = {
    "ADMIN": ("admin", ALL_PAGES),
    "GI": ("gi", ["plan"]),
    "MNG": ("mng", ["today"]),
    "MBR": ("mbr", ["clock"]),
}

# API path prefix (after /api/) -> page it belongs to.
API_PAGE = {
    "aisles/": "plan",
    "aisle-cages/": "plan",
    "bays/": "plan",
    "catalogue/": "plan",
    "assumptions/": "plan",
    "feed/": "today",
    "clock/": "clock",
    "admin/": "settings",
}


def role_and_pages(user) -> tuple[str | None, list[str]]:
    if not user or not user.is_authenticated:
        return None, []
    if user.is_superuser:
        return "admin", list(ALL_PAGES)
    groups = set(user.groups.values_list("name", flat=True))
    matched = [(name, rp) for name, rp in ROLE_PAGES.items() if name in groups]
    if not matched:
        return "admin", list(ALL_PAGES)  # pre-role account: full access
    role = matched[0][1][0]
    pages = [p for p in ALL_PAGES if any(p in rp[1] for _, rp in matched)]
    return role, pages


def page_for_path(path: str) -> str | None:
    """Page an /api/... path belongs to; None for anything not page-specific."""
    rest = path.split("/api/", 1)[-1]
    for prefix, page in API_PAGE.items():
        if rest.startswith(prefix):
            return page
    return None


class PageAccess(BasePermission):
    """Limit each page's API to the roles allowed to see that page. Endpoints
    that belong to no page (older, unused APIs) need full (admin) access.
    Auth endpoints set their own permissions and are not affected."""

    message = "Your role cannot use this page."

    def has_permission(self, request, view):
        _, pages = role_and_pages(request.user)
        page = page_for_path(request.path)
        if page is None:
            return pages == ALL_PAGES
        return page in pages
