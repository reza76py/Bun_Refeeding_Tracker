"""Plan / Today / Clock stay in sync: cascades and the Today -> Clock link."""

from datetime import datetime, timedelta, timezone as tz
from unittest import mock

from rest_framework.test import APITestCase

from tracker.models import CageFeed, CageSession
from tracker.tests.test_api import AuthMixin

# 10 Nov 2026, 08:00 Brisbane (UTC+10).
T0 = datetime(2026, 11, 9, 22, 0, tzinfo=tz.utc)
DAY = "2026-11-10"


class SyncTests(AuthMixin, APITestCase):
    def setUp(self):
        self.user = self.make_user("syncer")
        self.client.force_authenticate(self.user)
        self.aid = self.client.post("/api/aisles/", {"label": "1"}, format="json").json()["id"]
        self.c1 = self._cage("A1")
        self.c2 = self._cage("A2")

    def _cage(self, code):
        return self.client.post(
            f"/api/aisles/{self.aid}/cages/", {"code": code, "minutes": 30}, format="json"
        ).json()["id"]

    def _clock(self, action, cage_id, at):
        with mock.patch("django.utils.timezone.now", return_value=at):
            return self.client.post(f"/api/clock/{action}", {"cage_id": cage_id}, format="json")

    def _feed(self, cage_id, percent, day=DAY, at=None):
        with mock.patch("django.utils.timezone.now", return_value=at or T0):
            return self.client.put(
                "/api/feed/", {"date": day, "cage_id": cage_id, "percent": percent},
                format="json",
            )

    # --- cascade ------------------------------------------------------------
    def test_deleting_cage_removes_its_feeds_and_sessions(self):
        self._clock("start", self.c1, T0)
        self._clock("end", self.c1, T0 + timedelta(minutes=20))  # also writes a feed
        self._clock("start", self.c2, T0)
        self.assertEqual(CageFeed.objects.filter(cage_id=self.c1).count(), 1)
        self.assertEqual(CageSession.objects.filter(cage_id=self.c1).count(), 1)
        self.assertEqual(self.client.delete(f"/api/aisle-cages/{self.c1}/").status_code, 204)
        self.assertFalse(CageFeed.objects.filter(cage_id=self.c1).exists())
        self.assertFalse(CageSession.objects.filter(cage_id=self.c1).exists())
        self.assertTrue(CageSession.objects.filter(cage_id=self.c2).exists())

    def test_deleting_aisle_removes_feeds_and_sessions(self):
        self._clock("start", self.c1, T0)
        self._clock("end", self.c1, T0 + timedelta(minutes=20))
        self.client.delete(f"/api/aisles/{self.aid}/")
        self.assertFalse(CageFeed.objects.exists())
        self.assertFalse(CageSession.objects.exists())

    # --- Today -> Clock -----------------------------------------------------
    def test_below_100_reopens_session_ended_that_day(self):
        self._clock("start", self.c1, T0)
        self._clock("end", self.c1, T0 + timedelta(minutes=20))
        self.assertEqual(self._feed(self.c1, 60).status_code, 200)
        s = CageSession.objects.get(cage_id=self.c1)
        self.assertIsNone(s.end_at)  # running again
        self.assertEqual(CageFeed.objects.get(cage_id=self.c1).percent, 60)

    def test_below_100_on_other_day_leaves_session_alone(self):
        self._clock("start", self.c1, T0)
        self._clock("end", self.c1, T0 + timedelta(minutes=20))
        self._feed(self.c1, 50, day="2026-11-11")
        self.assertIsNotNone(CageSession.objects.get(cage_id=self.c1).end_at)

    def test_below_100_does_not_reopen_when_another_session_is_running(self):
        self._clock("start", self.c1, T0)
        self._clock("end", self.c1, T0 + timedelta(minutes=20))
        self._clock("start", self.c1, T0 + timedelta(minutes=30))
        self._feed(self.c1, 40)
        self.assertEqual(CageSession.objects.filter(cage_id=self.c1, end_at__isnull=True).count(), 1)

    def test_100_closes_open_session(self):
        self._clock("start", self.c1, T0)
        later = T0 + timedelta(minutes=45)
        self._feed(self.c1, 100, at=later)
        s = CageSession.objects.get(cage_id=self.c1)
        self.assertEqual(s.end_at, later)
        self.assertEqual(s.duration_seconds, 45 * 60)

    def test_100_without_session_only_stores_percent(self):
        self._feed(self.c1, 100)
        self.assertFalse(CageSession.objects.exists())
        self.assertEqual(CageFeed.objects.get(cage_id=self.c1).percent, 100)

    def test_other_user_unaffected(self):
        self._clock("start", self.c1, T0)
        other = self.make_user("bystander2")
        self.client.force_authenticate(other)
        self.assertEqual(self._feed(self.c1, 100).status_code, 404)
        self.assertIsNone(CageSession.objects.get(cage_id=self.c1).end_at)
