"""Settings (ADMIN only): change a cage's created_at."""

from datetime import datetime, timezone as tz

from django.utils.dateparse import parse_datetime
from rest_framework.test import APITestCase

from tracker.models import AisleCage


class AdminCageCreatedTests(APITestCase):
    def as_(self, username):
        self.client.logout()
        self.assertTrue(self.client.login(username=username, password=username))

    def setUp(self):
        self.as_("admin")
        aid = self.client.post("/api/aisles/", {"label": "Aisle 4"}, format="json").json()["id"]
        self.cid = self.client.post(
            f"/api/aisles/{aid}/cages/", {"code": "K1", "minutes": 30}, format="json"
        ).json()["id"]
        self.url = f"/api/admin/cages/{self.cid}/created/"

    def test_admin_lists_cages(self):
        r = self.client.get("/api/admin/cages/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            [(c["cage_id"], c["code"], c["aisle_label"]) for c in r.json()],
            [(self.cid, "K1", "Aisle 4")],
        )
        self.assertIsNotNone(r.json()[0]["created_at"])

    def test_admin_backdates_and_graph_reports_it(self):
        # Brisbane local time (UTC+10), as a datetime-local input sends it.
        r = self.client.patch(self.url, {"created_at": "2026-11-05T08:30"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        expected = datetime(2026, 11, 4, 22, 30, tzinfo=tz.utc)
        self.assertEqual(parse_datetime(r.json()["created_at"]), expected)
        self.assertEqual(AisleCage.objects.get(id=self.cid).created_at, expected)
        graph = self.client.get("/api/graph/running/").json()
        self.assertEqual(parse_datetime(graph[0]["created_at"]), expected)

    def test_bad_datetime_rejected(self):
        before = AisleCage.objects.get(id=self.cid).created_at
        self.assertEqual(
            self.client.patch(self.url, {"created_at": "yesterday"}, format="json").status_code,
            400,
        )
        self.assertEqual(AisleCage.objects.get(id=self.cid).created_at, before)

    def test_other_roles_get_403(self):
        for role in ("GI", "MNG", "MBR"):
            self.as_(role)
            self.assertEqual(self.client.get("/api/admin/cages/").status_code, 403, role)
            r = self.client.patch(self.url, {"created_at": "2026-11-01T08:00"}, format="json")
            self.assertEqual(r.status_code, 403, role)
            me = self.client.get("/api/auth/me/").json()
            self.assertNotIn("settings", me["pages"])
        self.as_("admin")
        self.assertIn("settings", self.client.get("/api/auth/me/").json()["pages"])
