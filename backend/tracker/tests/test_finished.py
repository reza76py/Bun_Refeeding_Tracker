"""`finished` on cages (aisles list, Clock summary, Today summary).

finished = ended on Clock, or 100% on Today. Pages hide finished cages; the
records stay (sessions, feeds, CSV).
"""

from rest_framework.test import APITestCase

from tracker.models import AisleCage, CageSession

DAY = "2026-11-10"


class FinishedFlagTests(APITestCase):
    def setUp(self):
        self.assertTrue(self.client.login(username="admin", password="admin"))
        self.aid = self.client.post("/api/aisles/", {"label": "Aisle 8"}, format="json").json()["id"]
        mk = lambda code: self.client.post(  # noqa: E731
            f"/api/aisles/{self.aid}/cages/", {"code": code, "minutes": 30}, format="json"
        ).json()["id"]
        self.ended, self.fed, self.partial, self.idle = mk("E1"), mk("F1"), mk("P1"), mk("I1")
        self.client.post("/api/clock/start", {"cage_id": self.ended}, format="json")
        self.client.post("/api/clock/end", {"cage_id": self.ended}, format="json")
        put = lambda cid, pct: self.client.put(  # noqa: E731
            "/api/feed/", {"date": DAY, "cage_id": cid, "percent": pct}, format="json"
        )
        put(self.fed, 100)
        put(self.partial, 40)

    EXPECTED = {"E1": True, "F1": True, "P1": False, "I1": False}

    def test_aisles_list_and_detail(self):
        cages = self.client.get("/api/aisles/").json()[0]["cages"]
        self.assertEqual({c["code"]: c["finished"] for c in cages}, self.EXPECTED)
        cages = self.client.get(f"/api/aisles/{self.aid}/").json()["cages"]
        self.assertEqual({c["code"]: c["finished"] for c in cages}, self.EXPECTED)

    def test_new_cage_response_has_finished_false(self):
        r = self.client.post(
            f"/api/aisles/{self.aid}/cages/", {"code": "N1", "minutes": 5}, format="json"
        )
        self.assertFalse(r.json()["finished"])

    def test_clock_summary(self):
        cages = self.client.get("/api/clock/summary/").json()["aisles"][0]["cages"]
        self.assertEqual({c["code"]: c["finished"] for c in cages}, self.EXPECTED)

    def test_today_summary_any_date(self):
        for day in (DAY, "2026-11-20"):
            cages = self.client.get(f"/api/feed/summary/?date={day}").json()["aisles"][0]["cages"]
            self.assertEqual({c["code"]: c["finished"] for c in cages}, self.EXPECTED)

    def test_records_are_kept(self):
        # Finished is display-only: the cages and their history still exist.
        self.assertEqual(AisleCage.objects.filter(aisle_id=self.aid).count(), 4)
        self.assertTrue(CageSession.objects.filter(cage_id=self.ended).exists())
        csv_text = self.client.get("/api/clock/export.csv").content.decode()
        self.assertIn("E1", csv_text)
