"""Graph: every unfinished cage, timed from creation; readable by every role."""

from django.utils.dateparse import parse_datetime
from rest_framework.test import APITestCase

from tracker.models import AisleCage


class GraphUnfinishedTests(APITestCase):
    def as_(self, username):
        self.client.logout()
        self.assertTrue(self.client.login(username=username, password=username))

    def setUp(self):
        self.as_("admin")
        self.aid = self.client.post("/api/aisles/", {"label": "3"}, format="json").json()["id"]

    def _cage(self, code):
        return self.client.post(
            f"/api/aisles/{self.aid}/cages/", {"code": code, "minutes": 30}, format="json"
        ).json()["id"]

    def _codes(self):
        return [r["code"] for r in self.client.get("/api/graph/running/").json()]

    def test_new_cage_listed_with_created_at(self):
        cid = self._cage("N1")
        rows = self.client.get("/api/graph/running/").json()
        self.assertEqual(
            [(r["cage_id"], r["code"], r["aisle_label"]) for r in rows], [(cid, "N1", "3")]
        )
        created = AisleCage.objects.get(id=cid).created_at
        self.assertEqual(parse_datetime(rows[0]["created_at"]), created)

    def test_started_but_not_ended_is_still_listed(self):
        cid = self._cage("S1")
        self.client.post("/api/clock/start", {"cage_id": cid}, format="json")
        self.assertEqual(self._codes(), ["S1"])

    def test_ended_on_clock_is_removed(self):
        cid = self._cage("E1")
        self.client.post("/api/clock/start", {"cage_id": cid}, format="json")
        self.client.post("/api/clock/end", {"cage_id": cid}, format="json")
        self.assertEqual(self._codes(), [])

    def test_100_on_today_is_removed_but_partial_is_not(self):
        cid = self._cage("T1")
        put = lambda pct: self.client.put(  # noqa: E731
            "/api/feed/", {"date": "2026-11-10", "cage_id": cid, "percent": pct}, format="json"
        )
        put(60)
        self.assertEqual(self._codes(), ["T1"])
        put(100)
        self.assertEqual(self._codes(), [])

    def test_deleted_cage_is_removed(self):
        cid = self._cage("D1")
        self.client.delete(f"/api/aisle-cages/{cid}/")
        self.assertEqual(self._codes(), [])

    def test_every_role_sees_the_same_list(self):
        self._cage("A1")
        self._cage("A2")
        seen = {}
        for role in ("GI", "MNG", "MBR", "admin"):
            self.as_(role)
            r = self.client.get("/api/graph/running/")
            self.assertEqual(r.status_code, 200, role)
            seen[role] = r.json()
        self.assertTrue(all(v == seen["admin"] for v in seen.values()))
        self.assertEqual([r["code"] for r in seen["admin"]], ["A1", "A2"])  # oldest first

    def test_requires_login(self):
        self.client.logout()
        self.assertIn(self.client.get("/api/graph/running/").status_code, (401, 403))
