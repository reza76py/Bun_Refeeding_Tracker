"""Today asks for a start/end when a cage with no Clock session is ticked:
the summary exposes each cage's session, and /api/clock/manual records one."""

from datetime import datetime, timedelta, timezone as tz
from unittest import mock

from rest_framework.test import APITestCase

from tracker.models import CageFeed, CageSession
from tracker.tests.test_api import AuthMixin

DAY = "2026-11-10"


class ManualSessionTests(AuthMixin, APITestCase):
    def setUp(self):
        self.user = self.make_user("manual")
        self.client.force_authenticate(self.user)
        aid = self.client.post("/api/aisles/", {"label": "1"}, format="json").json()["id"]
        self.c1 = self.client.post(
            f"/api/aisles/{aid}/cages/", {"code": "A1", "minutes": 30}, format="json"
        ).json()["id"]

    def _manual(self, start, end, cage_id=None):
        return self.client.post(
            "/api/clock/manual",
            {"cage_id": cage_id or self.c1, "start_at": start, "end_at": end},
            format="json",
        )

    def _cage(self, day=DAY):
        s = self.client.get(f"/api/feed/summary/?date={day}").json()
        return s["aisles"][0]["cages"][0], s

    def test_summary_session_is_null_without_clock(self):
        cage, _ = self._cage()
        self.assertIsNone(cage["session"])

    def test_manual_stores_session_and_marks_today_100(self):
        # Local (Brisbane) times, as sent by <input type="datetime-local">.
        r = self._manual("2026-11-10T06:05", "2026-11-10T06:50")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["duration_seconds"], 45 * 60)
        sess = CageSession.objects.get(cage_id=self.c1)
        self.assertEqual(sess.start_at, datetime(2026, 11, 9, 20, 5, tzinfo=tz.utc))
        feed = CageFeed.objects.get(cage_id=self.c1)
        self.assertEqual((feed.feed_date.isoformat(), feed.percent), (DAY, 100))
        cage, summary = self._cage()
        self.assertEqual(cage["percent"], 100)
        self.assertIsNotNone(cage["session"]["end_at"])
        self.assertEqual(summary["percent_fed"], 100)

    def test_manual_overnight_marks_end_date(self):
        self._manual("2026-11-10T23:30", "2026-11-11T00:40")
        feed = CageFeed.objects.get(cage_id=self.c1)
        self.assertEqual(feed.feed_date.isoformat(), "2026-11-11")
        # The session covers both days on Today.
        self.assertIsNotNone(self._cage("2026-11-10")[0]["session"])
        self.assertIsNotNone(self._cage("2026-11-11")[0]["session"])

    def test_end_before_start_rejected(self):
        r = self._manual("2026-11-10T07:00", "2026-11-10T06:00")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(CageSession.objects.exists())
        self.assertFalse(CageFeed.objects.exists())

    def test_bad_datetime_rejected(self):
        self.assertEqual(self._manual("soon", "2026-11-10T06:00").status_code, 400)

    def test_running_session_shows_on_today(self):
        start = datetime(2026, 11, 9, 21, 0, tzinfo=tz.utc)  # 10 Nov 07:00 Brisbane
        with mock.patch("django.utils.timezone.now", return_value=start):
            self.client.post("/api/clock/start", {"cage_id": self.c1}, format="json")
        cage, _ = self._cage()
        self.assertIsNone(cage["session"]["end_at"])
        # A running session started earlier still counts on later days.
        self.assertIsNotNone(self._cage("2026-11-12")[0]["session"])
        # But not on a day before it started.
        self.assertIsNone(self._cage("2026-11-09")[0]["session"])

    def test_other_user_cannot_create_on_foreign_cage(self):
        other = self.make_user("intruder-manual")
        self.client.force_authenticate(other)
        self.assertEqual(
            self._manual("2026-11-10T06:00", "2026-11-10T06:30").status_code, 404
        )
        self.assertFalse(CageSession.objects.exists())
        self.assertFalse(CageFeed.objects.exists())
