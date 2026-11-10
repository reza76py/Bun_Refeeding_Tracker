"""Clock page: real start / end sessions per cage, kept as history."""

import csv
import io
from datetime import datetime, timedelta, timezone as tz

from rest_framework.test import APITestCase

from tracker.models import CageSession
from tracker.tests.test_api import AuthMixin


class ClockTests(AuthMixin, APITestCase):
    def setUp(self):
        self.user = self.make_user("clocker")
        self.client.force_authenticate(self.user)
        a1 = self._aisle("1")
        a2 = self._aisle("2")
        self.c1 = self._cage(a1, "A1", 45)
        self.c2 = self._cage(a1, "A2", 30)
        self.c3 = self._cage(a2, "B1", 60)

    def _aisle(self, label):
        return self.client.post("/api/aisles/", {"label": label}, format="json").json()["id"]

    def _cage(self, aisle_id, code, minutes):
        return self.client.post(
            f"/api/aisles/{aisle_id}/cages/", {"code": code, "minutes": minutes}, format="json"
        ).json()["id"]

    def _post(self, action, cage_id):
        return self.client.post(f"/api/clock/{action}", {"cage_id": cage_id}, format="json")

    def _cages(self):
        s = self.client.get("/api/clock/summary/").json()
        return {c["code"]: c for a in s["aisles"] for c in a["cages"]}

    def test_summary_groups_cages_under_aisles(self):
        s = self.client.get("/api/clock/summary/").json()
        self.assertEqual([a["label"] for a in s["aisles"]], ["1", "2"])
        self.assertEqual([c["code"] for c in s["aisles"][0]["cages"]], ["A1", "A2"])
        self.assertIsNone(s["aisles"][0]["cages"][0]["open_session"])
        self.assertIsNone(s["aisles"][0]["cages"][0]["last_session"])

    def test_start_creates_open_session_and_second_start_returns_it(self):
        r1 = self._post("start", self.c1)
        self.assertEqual(r1.status_code, 200)
        self.assertIsNone(r1.json()["end_at"])
        r2 = self._post("start", self.c1)
        self.assertEqual(r2.json()["id"], r1.json()["id"])
        self.assertEqual(CageSession.objects.filter(cage_id=self.c1).count(), 1)
        self.assertEqual(self._cages()["A1"]["open_session"]["id"], r1.json()["id"])
        self.assertIsNone(self._cages()["A2"]["open_session"])

    def test_end_closes_session_and_keeps_history(self):
        self.assertEqual(self._post("end", self.c1).status_code, 400)  # none open
        self._post("start", self.c1)
        r = self._post("end", self.c1).json()
        self.assertIsNotNone(r["end_at"])
        self.assertGreaterEqual(r["duration_seconds"], 0)
        c = self._cages()["A1"]
        self.assertIsNone(c["open_session"])
        self.assertEqual(c["last_session"]["id"], r["id"])
        # A new start makes a second row; the first stays as history.
        self._post("start", self.c1)
        self.assertEqual(CageSession.objects.filter(cage_id=self.c1).count(), 2)

    def test_multi_day_duration(self):
        start = datetime(2026, 11, 9, 22, 0, tzinfo=tz.utc)
        CageSession.objects.create(
            cage_id=self.c3, start_at=start, end_at=start + timedelta(days=1, hours=2, minutes=5)
        )
        self.assertEqual(self._cages()["B1"]["last_session"]["duration_seconds"], 93900)

    def test_cancel_removes_open_session_only(self):
        self._post("start", self.c1)
        self._post("end", self.c1)  # finished one stays
        self._post("start", self.c1)
        self.assertEqual(self._post("cancel", self.c1).json(), {"cancelled": True})
        self.assertEqual(CageSession.objects.filter(cage_id=self.c1).count(), 1)
        self.assertIsNone(self._cages()["A1"]["open_session"])
        self.assertEqual(self._post("cancel", self.c1).json(), {"cancelled": False})

    def test_export_csv(self):
        self._post("start", self.c1)
        self._post("end", self.c1)
        self._post("start", self.c3)  # still running
        r = self.client.get("/api/clock/export.csv")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r["Content-Type"])
        rows = list(csv.DictReader(io.StringIO(r.content.decode())))
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            list(rows[0].keys()),
            ["aisle_label", "cage_code", "planned_minutes", "start_at", "end_at",
             "duration_seconds", "created_at"],
        )
        a1 = next(x for x in rows if x["cage_code"] == "A1")
        self.assertEqual(a1["aisle_label"], "1")
        self.assertEqual(float(a1["planned_minutes"]), 45)
        self.assertTrue(a1["end_at"])
        self.assertTrue(a1["start_at"].endswith("+10:00"))  # Brisbane
        b1 = next(x for x in rows if x["cage_code"] == "B1")
        self.assertEqual(b1["end_at"], "")
        self.assertEqual(b1["duration_seconds"], "")

    def test_other_user_shares_clock(self):
        self._post("start", self.c1)
        self.client.force_authenticate(self.make_user("other-clock"))
        # Same workspace: sees the running session and can end it.
        self.assertIsNotNone(self._cages()["A1"]["open_session"])
        self.assertEqual(self._post("end", self.c1).status_code, 200)
        rows = list(csv.reader(io.StringIO(
            self.client.get("/api/clock/export.csv").content.decode())))
        self.assertEqual(len(rows), 2)  # header + the shared session


class ClockEndMarksTodayFedTests(AuthMixin, APITestCase):
    """Ending a Clock session marks the cage 100% fed on Today (end date)."""

    def setUp(self):
        self.user = self.make_user("linker")
        self.client.force_authenticate(self.user)
        aid = self.client.post("/api/aisles/", {"label": "1"}, format="json").json()["id"]
        self.c1 = self.client.post(
            f"/api/aisles/{aid}/cages/", {"code": "A1", "minutes": 60}, format="json"
        ).json()["id"]
        self.c2 = self.client.post(
            f"/api/aisles/{aid}/cages/", {"code": "A2", "minutes": 20}, format="json"
        ).json()["id"]

    def _post(self, action, cage_id):
        return self.client.post(f"/api/clock/{action}", {"cage_id": cage_id}, format="json")

    def _end_date(self, resp):
        from django.utils.dateparse import parse_datetime
        from django.utils import timezone

        return timezone.localdate(parse_datetime(resp.json()["end_at"])).isoformat()

    def test_end_sets_percent_100_on_end_date(self):
        from tracker.models import CageFeed

        self._post("start", self.c1)
        self.assertFalse(CageFeed.objects.exists())  # starting changes nothing
        r = self._post("end", self.c1)
        day = self._end_date(r)
        feed = CageFeed.objects.get(cage_id=self.c1)
        self.assertEqual((feed.feed_date.isoformat(), feed.percent), (day, 100))
        s = self.client.get(f"/api/feed/summary/?date={day}").json()
        pct = {c["code"]: c["percent"] for c in s["aisles"][0]["cages"]}
        self.assertEqual(pct, {"A1": 100, "A2": 0})
        self.assertEqual(s["percent_fed"], 75)  # 60 of 80 planned minutes

    def test_end_uses_brisbane_date_and_overwrites_partial(self):
        from unittest import mock

        from tracker.models import CageFeed

        # Start 10 Nov 23:30 Brisbane (13:30 UTC), end 11 Nov 00:30 Brisbane.
        start = datetime(2026, 11, 10, 13, 30, tzinfo=tz.utc)
        end = start + timedelta(hours=1)
        self.client.put(
            "/api/feed/", {"date": "2026-11-11", "cage_id": self.c1, "percent": 40},
            format="json",
        )
        with mock.patch("django.utils.timezone.now", return_value=start):
            self._post("start", self.c1)
        with mock.patch("django.utils.timezone.now", return_value=end):
            self._post("end", self.c1)
        feeds = CageFeed.objects.filter(cage_id=self.c1)
        self.assertEqual(
            [(f.feed_date.isoformat(), f.percent) for f in feeds], [("2026-11-11", 100)]
        )

    def test_cancel_does_not_create_feed(self):
        from tracker.models import CageFeed

        self._post("start", self.c1)
        self._post("cancel", self.c1)
        self.assertFalse(CageFeed.objects.exists())

    def test_end_without_open_session_creates_nothing(self):
        from tracker.models import CageFeed

        self.assertEqual(self._post("end", self.c1).status_code, 400)
        self.assertFalse(CageFeed.objects.exists())

    def test_end_shows_on_everyones_today(self):
        self._post("start", self.c1)
        day = self._end_date(self._post("end", self.c1))
        self.client.force_authenticate(self.make_user("bystander"))
        s = self.client.get(f"/api/feed/summary/?date={day}").json()
        self.assertEqual(s["aisles"][0]["cages"][0]["percent"], 100)

