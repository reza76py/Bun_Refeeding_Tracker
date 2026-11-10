"""Demo roles: each role only reaches its own page's API; admin reaches all."""

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

User = get_user_model()

# One representative read endpoint per page.
PLAN = ["/api/aisles/", "/api/catalogue/summary/"]
TODAY = ["/api/feed/summary/?date=2026-11-10"]
CLOCK = ["/api/clock/summary/", "/api/clock/export.csv"]


class RoleAccessTests(APITestCase):
    def login(self, username):
        # The data migration created the demo users (password == username).
        self.assertTrue(self.client.login(username=username, password=username))

    def codes(self, urls):
        return {self.client.get(u).status_code for u in urls}

    def test_demo_users_exist_with_roles(self):
        for name, role, pages in [
            ("GI", "gi", ["plan"]),
            ("MNG", "mng", ["today"]),
            ("MBR", "mbr", ["clock"]),
            ("admin", "admin", ["plan", "today", "clock", "settings"]),
        ]:
            self.login(name)
            me = self.client.get("/api/auth/me/").json()
            self.assertEqual((me["username"], me["role"], me["pages"]), (name, role, pages))
            self.client.logout()
        self.assertTrue(User.objects.get(username="admin").is_staff)

    def test_login_returns_role_and_pages(self):
        r = self.client.post(
            "/api/auth/login/", {"username": "MNG", "password": "MNG"}, format="json"
        )
        self.assertEqual((r.json()["role"], r.json()["pages"]), ("mng", ["today"]))

    def test_gi_plan_only(self):
        self.login("GI")
        self.assertEqual(self.codes(PLAN), {200})
        self.assertEqual(self.codes(TODAY + CLOCK), {403})
        r = self.client.post("/api/clock/start", {"cage_id": 1}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_mng_today_only(self):
        self.login("MNG")
        self.assertEqual(self.codes(TODAY), {200})
        self.assertEqual(self.codes(PLAN + CLOCK), {403})
        r = self.client.post("/api/aisles/", {"label": "9"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_mbr_clock_only(self):
        self.login("MBR")
        self.assertEqual(self.codes(CLOCK), {200})
        self.assertEqual(self.codes(PLAN + TODAY), {403})

    def test_admin_all(self):
        self.login("admin")
        self.assertEqual(self.codes(PLAN + TODAY + CLOCK), {200})

    def test_superuser_and_pre_role_accounts_keep_full_access(self):
        User.objects.create_superuser("boss", password="pw-boss-123")
        User.objects.create_user("legacy", password="pw-legacy-123")
        for name, pw in (("boss", "pw-boss-123"), ("legacy", "pw-legacy-123")):
            self.assertTrue(self.client.login(username=name, password=pw))
            self.assertEqual(self.client.get("/api/auth/me/").json()["role"], "admin")
            self.assertEqual(self.codes(PLAN + TODAY + CLOCK), {200})
            self.client.logout()

    def test_role_users_blocked_from_unmapped_legacy_apis(self):
        self.login("GI")
        self.assertEqual(self.client.get("/api/stores/").status_code, 403)
        self.client.logout()
        self.login("admin")
        self.assertEqual(self.client.get("/api/stores/").status_code, 200)

    def test_auth_endpoints_open_to_any_role(self):
        self.login("MBR")
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 200)
        self.assertEqual(self.client.get("/api/auth/csrf/").status_code, 200)


class GiPlanCrudTests(APITestCase):
    """GI has full Plan access; MNG/MBR are refused Plan; admin allowed."""

    def login(self, username):
        self.client.logout()
        self.assertTrue(self.client.login(username=username, password=username))

    def test_gi_can_record_aisles_and_cages(self):
        self.login("GI")
        self.assertEqual(self.client.get("/api/aisles/").status_code, 200)
        r = self.client.post("/api/aisles/", {"label": "Aisle 5"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        aid = r.json()["id"]
        self.assertEqual(self.client.get(f"/api/aisles/{aid}/").status_code, 200)
        r = self.client.post(
            f"/api/aisles/{aid}/cages/", {"code": "A1", "minutes": 30}, format="json"
        )
        self.assertEqual(r.status_code, 201, r.content)
        cid = r.json()["id"]
        r = self.client.patch(f"/api/aisle-cages/{cid}/", {"minutes": 45}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["minutes"], 45)
        self.assertEqual(self.client.delete(f"/api/aisle-cages/{cid}/").status_code, 204)
        r = self.client.post(
            f"/api/aisles/{aid}/bays/",
            {"bay_number": 1, "estimated_catalogue_lines": 10},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.client.get("/api/catalogue/summary/").status_code, 200)
        self.assertEqual(self.client.get("/api/graph/running/").status_code, 200)

    def test_mng_and_mbr_refused_plan_admin_allowed(self):
        self.login("admin")
        aid = self.client.post("/api/aisles/", {"label": "Aisle 6"}, format="json").json()["id"]
        cid = self.client.post(
            f"/api/aisles/{aid}/cages/", {"code": "B1", "minutes": 20}, format="json"
        ).json()["id"]
        for role in ("MNG", "MBR"):
            self.login(role)
            self.assertEqual(self.client.get("/api/aisles/").status_code, 403, role)
            self.assertEqual(
                self.client.post("/api/aisles/", {"label": "X"}, format="json").status_code,
                403, role,
            )
            self.assertEqual(
                self.client.post(
                    f"/api/aisles/{aid}/cages/", {"code": "Z", "minutes": 1}, format="json"
                ).status_code,
                403, role,
            )
            self.assertEqual(
                self.client.patch(f"/api/aisle-cages/{cid}/", {"minutes": 1}, format="json").status_code,
                403, role,
            )
            self.assertEqual(self.client.delete(f"/api/aisle-cages/{cid}/").status_code, 403, role)
            self.assertEqual(self.client.get("/api/graph/running/").status_code, 200, role)
        self.login("admin")
        self.assertEqual(self.client.get("/api/aisles/").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/aisle-cages/{cid}/").status_code, 204)
