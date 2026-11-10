"""One shared workspace for all demo roles; roles only limit which pages."""

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from tracker import services
from tracker.models import Aisle, Store

User = get_user_model()


class SharedWorkspaceTests(APITestCase):
    def as_(self, username):
        self.client.logout()
        self.assertTrue(self.client.login(username=username, password=username))

    def test_gi_plan_appears_for_mng_mbr_and_admin(self):
        self.as_("GI")
        aid = self.client.post("/api/aisles/", {"label": "7"}, format="json").json()["id"]
        cid = self.client.post(
            f"/api/aisles/{aid}/cages/", {"code": "C1", "minutes": 40}, format="json"
        ).json()["id"]

        self.as_("MNG")  # Today sees GI's cage and can mark it
        s = self.client.get("/api/feed/summary/?date=2026-11-10").json()
        self.assertEqual([c["code"] for c in s["aisles"][0]["cages"]], ["C1"])
        r = self.client.put(
            "/api/feed/", {"date": "2026-11-10", "cage_id": cid, "percent": 50}, format="json"
        )
        self.assertEqual(r.status_code, 200)

        self.as_("MBR")  # Clock sees the same cage
        s = self.client.get("/api/clock/summary/").json()
        self.assertEqual(s["aisles"][0]["cages"][0]["cage_id"], cid)
        self.assertEqual(self.client.post("/api/clock/start", {"cage_id": cid}, format="json").status_code, 200)

        self.as_("admin")  # admin sees everything
        self.assertEqual([a["label"] for a in self.client.get("/api/aisles/").json()], ["7"])
        s = self.client.get("/api/feed/summary/?date=2026-11-10").json()
        self.assertEqual(s["aisles"][0]["cages"][0]["percent"], 50)
        s = self.client.get("/api/clock/summary/").json()
        self.assertIsNotNone(s["aisles"][0]["cages"][0]["open_session"])

    def test_roles_still_limit_pages(self):
        self.as_("GI")
        self.assertEqual(self.client.get("/api/feed/summary/").status_code, 403)
        self.assertEqual(self.client.get("/api/clock/summary/").status_code, 403)
        self.as_("MNG")
        self.assertEqual(self.client.get("/api/aisles/").status_code, 403)
        self.assertEqual(self.client.get("/api/clock/summary/").status_code, 403)
        self.as_("MBR")
        self.assertEqual(self.client.get("/api/aisles/").status_code, 403)
        self.assertEqual(self.client.get("/api/feed/summary/").status_code, 403)

    def test_shared_store_is_the_one_with_most_aisles_and_stays_put(self):
        u1 = User.objects.create_user("u1", password="pw-123456")
        u2 = User.objects.create_user("u2", password="pw-123456")
        Store.objects.filter(is_shared=True).update(is_shared=False)
        small = Store.objects.create(owner=u1, name="Small")
        big = Store.objects.create(owner=u2, name="Big")
        Aisle.objects.create(store=small, label="1")
        for label in ("1", "2"):
            Aisle.objects.create(store=big, label=label)
        self.assertEqual(services.get_shared_store(), big)
        # Emptying it does not move the workspace to another store.
        big.aisles.all().delete()
        self.assertEqual(services.get_shared_store(), big)

    def test_creates_shared_store_when_none_exists(self):
        Store.objects.all().delete()
        store = services.get_shared_store()
        self.assertTrue(store.is_shared)
        self.assertEqual(store.owner.username, "admin")
        self.assertEqual(store.name, "Shared")
