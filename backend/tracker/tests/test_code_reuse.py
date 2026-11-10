"""A finished cage's code can be reused; its history is kept."""

import csv
import io

from rest_framework.test import APITestCase

from tracker.models import AisleCage, CageSession

DAY = "2026-11-10"


class CageCodeReuseTests(APITestCase):
    def as_(self, username):
        self.client.logout()
        self.assertTrue(self.client.login(username=username, password=username))

    def setUp(self):
        self.as_("GI")
        self.aid = self.client.post("/api/aisles/", {"label": "Aisle 9"}, format="json").json()["id"]
        self.old = self._add("C2").json()["id"]

    def _add(self, code):
        return self.client.post(
            f"/api/aisles/{self.aid}/cages/", {"code": code, "minutes": 30}, format="json"
        )

    def _end_as_member(self, cage_id):
        self.as_("MBR")
        self.client.post("/api/clock/start", {"cage_id": cage_id}, format="json")
        self.client.post("/api/clock/end", {"cage_id": cage_id}, format="json")

    def _live_codes(self, cages):
        return sorted(c["code"] for c in cages if not c["finished"])

    def test_active_duplicate_still_rejected(self):
        r = self._add("c2")  # case-insensitive
        self.assertEqual(r.status_code, 400)
        self.assertIn("already exists", str(r.json()))

    def test_code_reusable_after_member_ends_it_and_history_kept(self):
        self._end_as_member(self.old)

        # Finished -> hidden on every page (pages show only unfinished cages).
        self.as_("GI")
        aisle = self.client.get("/api/aisles/").json()[0]
        self.assertEqual(self._live_codes(aisle["cages"]), [])
        self.as_("MBR")
        clock = self.client.get("/api/clock/summary/").json()["aisles"][0]["cages"]
        self.assertEqual(self._live_codes(clock), [])
        self.as_("MNG")
        today = self.client.get(f"/api/feed/summary/?date={DAY}").json()["aisles"][0]["cages"]
        self.assertEqual(self._live_codes(today), [])

        # GI can add C2 again.
        self.as_("GI")
        r = self._add("C2")
        self.assertEqual(r.status_code, 201, r.content)
        new = r.json()["id"]
        self.assertNotEqual(new, self.old)
        aisle = self.client.get("/api/aisles/").json()[0]
        self.assertEqual(self._live_codes(aisle["cages"]), ["C2"])
        # ...but not a second active C2.
        self.assertEqual(self._add("C2").status_code, 400)

        # The old cage and its session are kept, and still exported.
        self.assertTrue(AisleCage.objects.filter(id=self.old).exists())
        self.assertTrue(CageSession.objects.filter(cage_id=self.old).exists())
        self.as_("MBR")
        rows = list(csv.DictReader(io.StringIO(
            self.client.get("/api/clock/export.csv").content.decode())))
        self.assertEqual([r["cage_code"] for r in rows], ["C2"])
        self.assertTrue(rows[0]["end_at"])

    def test_code_reusable_after_100_on_today(self):
        self.as_("MNG")
        self.client.put(
            "/api/feed/", {"date": DAY, "cage_id": self.old, "percent": 100}, format="json"
        )
        self.as_("GI")
        self.assertEqual(self._add("C2").status_code, 201)

    def test_rename_into_a_finished_code_is_allowed(self):
        other = self._add("C3").json()["id"]
        self._end_as_member(self.old)
        self.as_("GI")
        r = self.client.patch(f"/api/aisle-cages/{other}/", {"code": "C2"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
