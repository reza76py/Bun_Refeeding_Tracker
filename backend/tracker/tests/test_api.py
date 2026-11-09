"""API / integration tests (brief section 10, the DB-backed cases).

Run with the project's test settings on any configured database:
    python manage.py test
"""

from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from tracker import services
from tracker.models import Aisle, Bay, CageLog, WorkDay

User = get_user_model()


class AuthMixin:
    def make_user(self, username, password="pass12345"):
        user = User.objects.create_user(username=username, password=password)
        services.active_assumption_set(user)  # ensure baseline v1
        services.default_store(user)
        return user


class CalculatorPreviewApiTests(AuthMixin, APITestCase):
    def setUp(self):
        self.user = self.make_user("alice")
        self.client.force_authenticate(self.user)

    def test_baseline_preview_matches_brief_demo(self):
        resp = self.client.post(
            "/api/calculator/preview/",
            {
                "find_sec": 30,
                "unpack_sec": 10,
                "seconds_per_unit": 1,
                "units_per_line": 5,
                "other_sec": 0,
                "lines_per_cage": 100,
                "cages": 3,
                "cages_min": 2,
                "cages_max": 5,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["per_line_seconds"], 45)
        self.assertEqual(data["per_cage_seconds"], 4500)  # 1h15m
        self.assertEqual(data["per_cage_hm"], "1h 15m")
        self.assertEqual(data["day_seconds"], 13500)  # 3 cages
        day_by_cages = {r["cages"]: r["day_seconds"] for r in data["scenarios"]}
        self.assertEqual(day_by_cages[2], 9000)
        self.assertEqual(day_by_cages[5], 22500)

    def test_preview_rejects_negative_input(self):
        resp = self.client.post(
            "/api/calculator/preview/",
            {
                "find_sec": -1,
                "unpack_sec": 10,
                "seconds_per_unit": 1,
                "units_per_line": 5,
                "lines_per_cage": 100,
                "cages": 2,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class WorkDayForecastTests(AuthMixin, APITestCase):
    def setUp(self):
        self.user = self.make_user("bob")
        self.client.force_authenticate(self.user)

    def test_workday_snapshots_assumptions_and_computes_cage_forecast(self):
        resp = self.client.post(
            "/api/workdays/",
            {
                "work_date": "2026-11-07",
                "cages": [{"line_count": 100}, {"line_count": 0}],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        data = resp.json()
        # 100-line cage = 4500s; 0-line cage = 0s (NOT treated as default 100).
        est = {c["line_count"]: c["estimated_seconds"] for c in data["cages"]}
        self.assertEqual(est[100], 4500)
        self.assertEqual(est[0], 0)
        self.assertEqual(data["estimated_day_seconds"], 4500)
        self.assertIn("assumption_snapshot", data)
        self.assertEqual(data["assumption_snapshot"]["find_sec"], 30)

    def test_past_day_forecast_unchanged_after_new_assumptions_saved(self):
        created = self.client.post(
            "/api/workdays/",
            {"work_date": "2026-11-01", "cages": [{"line_count": 100}]},
            format="json",
        ).json()
        original = created["estimated_day_seconds"]
        self.assertEqual(original, 4500)

        # Save a NEW assumption version with a much larger find time.
        resp = self.client.post(
            "/api/assumptions/", {"find_sec": 300}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.json()["version"], 2)

        # The past day's forecast must be unchanged.
        again = self.client.get(f"/api/workdays/{created['id']}/").json()
        self.assertEqual(again["estimated_day_seconds"], original)
        self.assertEqual(again["assumption_snapshot"]["find_sec"], 30)

    def test_measured_and_forecast_are_separately_labelled(self):
        wd = self.client.post(
            "/api/workdays/",
            {"work_date": "2026-11-05", "cages": [{"line_count": 100}]},
            format="json",
        ).json()
        cage_id = wd["cages"][0]["id"]
        # Record a measured actual that differs from the forecast.
        resp = self.client.patch(
            f"/api/cages/{cage_id}/",
            {"actual_active_seconds": 6000, "status": "complete"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        cage = resp.json()
        # Forecast snapshot is preserved; actual is a distinct field.
        self.assertEqual(cage["estimated_seconds"], 4500)
        self.assertEqual(cage["actual_active_seconds"], 6000)
        self.assertNotEqual(cage["estimated_seconds"], cage["actual_active_seconds"])

    def test_duplicate_workday_is_rejected(self):
        self.client.post(
            "/api/workdays/", {"work_date": "2026-11-09"}, format="json"
        )
        dup = self.client.post(
            "/api/workdays/", {"work_date": "2026-11-09"}, format="json"
        )
        self.assertEqual(dup.status_code, status.HTTP_400_BAD_REQUEST)


class OwnershipTests(AuthMixin, APITestCase):
    def test_unauthorized_user_cannot_access_another_users_records(self):
        alice = self.make_user("alice2")
        bob = self.make_user("bob2")

        self.client.force_authenticate(alice)
        wd = self.client.post(
            "/api/workdays/", {"work_date": "2026-11-07"}, format="json"
        ).json()
        wd_id = wd["id"]

        # Bob must not see Alice's work day.
        self.client.force_authenticate(bob)
        resp = self.client.get(f"/api/workdays/{wd_id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        # Bob's list excludes it.
        listed = self.client.get("/api/workdays/").json()
        self.assertEqual(listed, [])

    def test_anonymous_requests_are_rejected(self):
        resp = self.client.get("/api/workdays/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class CatalogueTests(AuthMixin, APITestCase):
    def test_seeded_catalogue_totals(self):
        from django.core.management import call_command

        call_command("seed", "--username", "seeded", "--password", "pass12345")
        user = User.objects.get(username="seeded")
        self.client.force_authenticate(user)
        data = self.client.get("/api/catalogue/summary/").json()
        self.assertEqual(data["combined_catalogue_lines"], 4950)
        totals = {r["label"]: r["catalogue_lines"] for r in data["per_aisle"]}
        self.assertEqual(totals["Aisle 9"], 3150)
        self.assertEqual(totals["Aisle 10"], 1800)


class AisleBayManagementTests(AuthMixin, APITestCase):
    def setUp(self):
        self.user = self.make_user("carol")
        self.client.force_authenticate(self.user)

    def _create_aisle(self, label):
        return self.client.post("/api/aisles/", {"label": label}, format="json")

    def test_create_aisle(self):
        resp = self._create_aisle("Aisle 15")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.json()
        self.assertEqual(data["label"], "Aisle 15")
        self.assertEqual(data["bays"], [])
        self.assertEqual(data["catalogue_lines"], 0)
        self.assertTrue(
            Aisle.objects.filter(id=data["id"], store__owner=self.user).exists()
        )

    def test_create_bay_via_nested_route_without_aisle_in_body(self):
        aisle_id = self._create_aisle("Aisle 18").json()["id"]
        resp = self.client.post(
            f"/api/aisles/{aisle_id}/bays/",
            {"bay_number": 3, "estimated_catalogue_lines": 120},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.content)
        self.assertEqual(resp.json()["aisle"], aisle_id)
        aisle = self.client.get(f"/api/aisles/{aisle_id}/").json()
        self.assertEqual(aisle["catalogue_lines"], 120)

    def test_delete_aisle_cascades_bays(self):
        aisle_id = self._create_aisle("Aisle 20").json()["id"]
        for n in (1, 2):
            self.client.post(
                f"/api/aisles/{aisle_id}/bays/",
                {"bay_number": n, "estimated_catalogue_lines": 50},
                format="json",
            )
        self.assertEqual(Bay.objects.filter(aisle_id=aisle_id).count(), 2)
        resp = self.client.delete(f"/api/aisles/{aisle_id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Aisle.objects.filter(id=aisle_id).exists())
        self.assertEqual(Bay.objects.filter(aisle_id=aisle_id).count(), 0)

    def test_patch_aisle_rename_and_toggle_active(self):
        aisle_id = self._create_aisle("Aisle 21").json()["id"]
        resp = self.client.patch(
            f"/api/aisles/{aisle_id}/",
            {"label": "Aisle 22", "active": False},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["label"], "Aisle 22")
        self.assertFalse(resp.json()["active"])

    def test_duplicate_aisle_label_returns_400(self):
        self._create_aisle("Aisle 15")
        resp = self._create_aisle("Aisle 15")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_bay_number_returns_400(self):
        aisle_id = self._create_aisle("Aisle 15").json()["id"]
        body = {"bay_number": 1, "estimated_catalogue_lines": 10}
        self.client.post(f"/api/aisles/{aisle_id}/bays/", body, format="json")
        resp = self.client.post(f"/api/aisles/{aisle_id}/bays/", body, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_other_users_aisle_is_not_accessible(self):
        aisle_id = self._create_aisle("Aisle 15").json()["id"]
        self.client.force_authenticate(self.make_user("dave"))
        self.assertEqual(
            self.client.get(f"/api/aisles/{aisle_id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.delete(f"/api/aisles/{aisle_id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        resp = self.client.post(
            f"/api/aisles/{aisle_id}/bays/",
            {"bay_number": 1, "estimated_catalogue_lines": 10},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class WholeAisleTotalTests(AuthMixin, APITestCase):
    def setUp(self):
        self.user = self.make_user("erin")
        self.client.force_authenticate(self.user)
        self.aisle_id = self.client.post(
            "/api/aisles/", {"label": "Aisle 30"}, format="json"
        ).json()["id"]

    def _set_total(self, n):
        return self.client.patch(
            f"/api/aisles/{self.aisle_id}/", {"aisle_total_lines": n}, format="json"
        )

    def _summary_total(self):
        data = self.client.get("/api/catalogue/summary/").json()
        return {r["aisle_id"]: r["catalogue_lines"] for r in data["per_aisle"]}[
            self.aisle_id
        ]

    def test_aisle_without_bays_uses_whole_aisle_total(self):
        resp = self._set_total(2500)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["aisle_total_lines"], 2500)
        self.assertEqual(resp.json()["catalogue_lines"], 2500)
        self.assertEqual(
            self.client.get(f"/api/aisles/{self.aisle_id}/").json()["catalogue_lines"],
            2500,
        )
        self.assertEqual(self._summary_total(), 2500)

    def test_bays_override_whole_aisle_total(self):
        self._set_total(2500)
        self.client.post(
            f"/api/aisles/{self.aisle_id}/bays/",
            {"bay_number": 1, "estimated_catalogue_lines": 40},
            format="json",
        )
        aisle = self.client.get(f"/api/aisles/{self.aisle_id}/").json()
        self.assertEqual(aisle["aisle_total_lines"], 2500)  # stored, but unused
        self.assertEqual(aisle["catalogue_lines"], 40)
        self.assertEqual(self._summary_total(), 40)

    def test_whole_aisle_total_rejects_out_of_range(self):
        self.assertEqual(self._set_total(-1).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            self._set_total(1_000_001).status_code, status.HTTP_400_BAD_REQUEST
        )

    def test_whole_aisle_total_is_owner_scoped(self):
        self.client.force_authenticate(self.make_user("frank"))
        self.assertEqual(self._set_total(999).status_code, status.HTTP_404_NOT_FOUND)
        self.client.force_authenticate(self.user)
        self.assertEqual(
            self.client.get(f"/api/aisles/{self.aisle_id}/").json()["aisle_total_lines"],
            0,
        )


class AisleCageTests(AuthMixin, APITestCase):
    def setUp(self):
        self.user = self.make_user("gina")
        self.client.force_authenticate(self.user)
        self.aisle_id = self.client.post(
            "/api/aisles/", {"label": "Aisle 40"}, format="json"
        ).json()["id"]

    def _add_cage(self, code, lines, aisle_id=None):
        return self.client.post(
            f"/api/aisles/{aisle_id or self.aisle_id}/cages/",
            {"code": code, "lines": lines},
            format="json",
        )

    def _aisle(self):
        return self.client.get(f"/api/aisles/{self.aisle_id}/").json()

    def test_cages_set_aisle_lines_and_summary(self):
        r = self._add_cage("a10", 120)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        self.assertEqual(r.json()["code"], "A10")  # normalised to upper case
        self._add_cage("B11", 80)
        aisle = self._aisle()
        self.assertEqual([c["code"] for c in aisle["cages"]], ["A10", "B11"])
        self.assertEqual(aisle["catalogue_lines"], 200)
        per_aisle = self.client.get("/api/catalogue/summary/").json()["per_aisle"]
        self.assertEqual(
            {r["aisle_id"]: r["catalogue_lines"] for r in per_aisle}[self.aisle_id], 200
        )

    def test_cages_override_bays_and_bays_used_without_cages(self):
        self.client.post(
            f"/api/aisles/{self.aisle_id}/bays/",
            {"bay_number": 1, "estimated_catalogue_lines": 500},
            format="json",
        )
        self.assertEqual(self._aisle()["catalogue_lines"], 500)
        cage_id = self._add_cage("A10", 50).json()["id"]
        self.assertEqual(self._aisle()["catalogue_lines"], 50)
        self.client.delete(f"/api/aisle-cages/{cage_id}/")
        self.assertEqual(self._aisle()["catalogue_lines"], 500)

    def test_edit_cage_lines(self):
        cage_id = self._add_cage("A10", 50).json()["id"]
        r = self.client.patch(
            f"/api/aisle-cages/{cage_id}/", {"lines": 75}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(self._aisle()["catalogue_lines"], 75)

    def test_duplicate_cage_code_returns_400(self):
        self._add_cage("A10", 50)
        self.assertEqual(
            self._add_cage("a10", 10).status_code, status.HTTP_400_BAD_REQUEST
        )
        # Same code is fine in a different aisle.
        other = self.client.post(
            "/api/aisles/", {"label": "Aisle 41"}, format="json"
        ).json()["id"]
        self.assertEqual(
            self._add_cage("A10", 10, aisle_id=other).status_code,
            status.HTTP_201_CREATED,
        )

    def test_blank_code_and_negative_lines_rejected(self):
        self.assertEqual(self._add_cage("  ", 5).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self._add_cage("A1", -1).status_code, status.HTTP_400_BAD_REQUEST)

    def test_deleting_aisle_deletes_its_cages(self):
        from tracker.models import AisleCage

        self._add_cage("A10", 50)
        self.client.delete(f"/api/aisles/{self.aisle_id}/")
        self.assertFalse(AisleCage.objects.filter(aisle_id=self.aisle_id).exists())

    def test_cages_are_owner_scoped(self):
        cage_id = self._add_cage("A10", 50).json()["id"]
        self.client.force_authenticate(self.make_user("hank"))
        self.assertEqual(self._add_cage("Z9", 1).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.patch(
                f"/api/aisle-cages/{cage_id}/", {"lines": 1}, format="json"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.delete(f"/api/aisle-cages/{cage_id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )


class AisleDetailModeTests(AuthMixin, APITestCase):
    def setUp(self):
        self.user = self.make_user("ivy")
        self.client.force_authenticate(self.user)

    def test_create_bay_mode_aisle_and_bays_drive_lines(self):
        r = self.client.post(
            "/api/aisles/", {"label": "Aisle 2", "detail_mode": "bays"}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        aid = r.json()["id"]
        self.assertEqual(r.json()["detail_mode"], "bays")
        for n, lines in ((3, 100), (4, 150), (5, 200)):
            self.client.post(
                f"/api/aisles/{aid}/bays/",
                {"bay_number": n, "estimated_catalogue_lines": lines},
                format="json",
            )
        # Even with a stray cage, a bays-mode aisle counts its bays.
        self.client.post(f"/api/aisles/{aid}/cages/", {"code": "A1", "lines": 9}, format="json")
        self.assertEqual(self.client.get(f"/api/aisles/{aid}/").json()["catalogue_lines"], 450)

    def test_default_mode_is_cages_and_mode_can_be_switched(self):
        aid = self.client.post("/api/aisles/", {"label": "Aisle 3"}, format="json").json()["id"]
        self.assertEqual(self.client.get(f"/api/aisles/{aid}/").json()["detail_mode"], "cages")
        r = self.client.patch(f"/api/aisles/{aid}/", {"detail_mode": "bays"}, format="json")
        self.assertEqual(r.json()["detail_mode"], "bays")
        bad = self.client.patch(f"/api/aisles/{aid}/", {"detail_mode": "shelves"}, format="json")
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_seeded_aisles_use_bay_mode(self):
        from django.core.management import call_command

        call_command("seed", "--username", "seeded2", "--password", "pass12345")
        self.client.force_authenticate(User.objects.get(username="seeded2"))
        modes = {a["label"]: a["detail_mode"] for a in self.client.get("/api/aisles/").json()}
        self.assertEqual(modes, {"Aisle 10": "bays", "Aisle 9": "bays"})


class SecondsPerLineTests(AuthMixin, APITestCase):
    def setUp(self):
        self.user = self.make_user("jade")
        self.client.force_authenticate(self.user)

    def _aisle(self, label, mode):
        return self.client.post(
            "/api/aisles/", {"label": label, "detail_mode": mode}, format="json"
        ).json()["id"]

    def test_cage_time_is_lines_times_seconds(self):
        aid = self._aisle("Aisle 10", "cages")
        r = self.client.post(
            f"/api/aisles/{aid}/cages/",
            {"code": "A10", "lines": 120, "seconds_per_line": 5},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        self.assertEqual(r.json()["estimated_seconds"], 600)
        self.client.post(
            f"/api/aisles/{aid}/cages/",
            {"code": "B11", "lines": 30, "seconds_per_line": 10},
            format="json",
        )
        aisle = self.client.get(f"/api/aisles/{aid}/").json()
        self.assertEqual(aisle["estimated_seconds"], 900)
        self.assertEqual(aisle["rows_missing_time"], 0)

    def test_rows_without_time_are_skipped_and_counted(self):
        aid = self._aisle("Aisle 2", "bays")
        self.client.post(
            f"/api/aisles/{aid}/bays/",
            {"bay_number": 3, "estimated_catalogue_lines": 100, "seconds_per_line": 10},
            format="json",
        )
        bay = self.client.post(
            f"/api/aisles/{aid}/bays/",
            {"bay_number": 4, "estimated_catalogue_lines": 50},
            format="json",
        ).json()
        self.assertIsNone(bay["estimated_seconds"])
        aisle = self.client.get(f"/api/aisles/{aid}/").json()
        self.assertEqual(aisle["estimated_seconds"], 1000)
        self.assertEqual(aisle["rows_missing_time"], 1)
        # Setting the time later updates the aisle.
        self.client.patch(f"/api/bays/{bay['id']}/", {"seconds_per_line": 6}, format="json")
        self.assertEqual(
            self.client.get(f"/api/aisles/{aid}/").json()["estimated_seconds"], 1300
        )

    def test_summary_combined_time_and_none_when_unset(self):
        self.assertIsNone(
            self.client.get("/api/catalogue/summary/").json()["combined_estimated_seconds"]
        )
        a1 = self._aisle("Aisle 1", "cages")
        a2 = self._aisle("Aisle 2", "bays")
        self.client.post(
            f"/api/aisles/{a1}/cages/",
            {"code": "A1", "lines": 10, "seconds_per_line": 5},
            format="json",
        )
        self.client.post(
            f"/api/aisles/{a2}/bays/",
            {"bay_number": 1, "estimated_catalogue_lines": 20, "seconds_per_line": 3},
            format="json",
        )
        data = self.client.get("/api/catalogue/summary/").json()
        self.assertEqual(data["combined_estimated_seconds"], 110)

    def test_seconds_per_line_out_of_range_rejected(self):
        aid = self._aisle("Aisle 5", "cages")
        for bad in (-1, 3601):
            r = self.client.post(
                f"/api/aisles/{aid}/cages/",
                {"code": f"X{bad}", "lines": 1, "seconds_per_line": bad},
                format="json",
            )
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class RemoveAllAislesTests(AuthMixin, APITestCase):
    def test_remove_all_deletes_only_own_aisles_cages_and_bays(self):
        from tracker.models import AisleCage

        me = self.make_user("kim")
        other = self.make_user("lee")
        self.client.force_authenticate(other)
        other_aisle = self.client.post("/api/aisles/", {"label": "Keep"}, format="json").json()["id"]

        self.client.force_authenticate(me)
        a1 = self.client.post("/api/aisles/", {"label": "A1"}, format="json").json()["id"]
        a2 = self.client.post(
            "/api/aisles/", {"label": "A2", "detail_mode": "bays"}, format="json"
        ).json()["id"]
        self.client.post(f"/api/aisles/{a1}/cages/", {"code": "A10", "lines": 5}, format="json")
        self.client.post(
            f"/api/aisles/{a2}/bays/",
            {"bay_number": 1, "estimated_catalogue_lines": 5},
            format="json",
        )

        r = self.client.delete("/api/aisles/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()["deleted_aisles"], 2)
        self.assertEqual(self.client.get("/api/aisles/").json(), [])
        self.assertFalse(AisleCage.objects.filter(aisle_id=a1).exists())
        self.assertFalse(Bay.objects.filter(aisle_id=a2).exists())
        self.assertEqual(
            self.client.get("/api/catalogue/summary/").json()["combined_catalogue_lines"], 0
        )
        # Another user's data is untouched.
        self.assertTrue(Aisle.objects.filter(id=other_aisle).exists())


class CageMinutesTests(AuthMixin, APITestCase):
    def setUp(self):
        self.user = self.make_user("mia")
        self.client.force_authenticate(self.user)
        self.aid = self.client.post("/api/aisles/", {"label": "Aisle 7"}, format="json").json()["id"]

    def _cage(self, body):
        return self.client.post(f"/api/aisles/{self.aid}/cages/", body, format="json")

    def test_time_only_cages_sum_minutes(self):
        for code, mins in (("A10", 45), ("B11", 17), ("C12", 70), ("D13", 80)):
            r = self._cage({"code": code, "minutes": mins})
            self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
            self.assertEqual(r.json()["lines"], 0)
        aisle = self.client.get(f"/api/aisles/{self.aid}/").json()
        self.assertEqual(aisle["estimated_seconds"], (45 + 17 + 70 + 80) * 60)
        self.assertEqual(aisle["rows_missing_time"], 0)
        summary = self.client.get("/api/catalogue/summary/").json()
        self.assertEqual(summary["combined_estimated_seconds"], 212 * 60)

    def test_minutes_override_lines_times_seconds_and_mix(self):
        r = self._cage({"code": "A1", "lines": 100, "seconds_per_line": 5, "minutes": 30})
        self.assertEqual(r.json()["estimated_seconds"], 1800)  # minutes win
        self._cage({"code": "A2", "lines": 60, "seconds_per_line": 10})  # 600s
        self.assertEqual(
            self.client.get(f"/api/aisles/{self.aid}/").json()["estimated_seconds"], 2400
        )
        # Clearing minutes falls back to lines x seconds.
        cid = r.json()["id"]
        r2 = self.client.patch(f"/api/aisle-cages/{cid}/", {"minutes": None}, format="json")
        self.assertEqual(r2.json()["estimated_seconds"], 500)

    def test_minutes_out_of_range_rejected(self):
        self.assertEqual(self._cage({"code": "X", "minutes": -1}).status_code, 400)
        self.assertEqual(self._cage({"code": "Y", "minutes": 1441}).status_code, 400)


class CageFeedTests(AuthMixin, APITestCase):
    def setUp(self):
        self.user = self.make_user("feeder")
        self.client.force_authenticate(self.user)
        aid = self.client.post("/api/aisles/", {"label": "1"}, format="json").json()["id"]
        mk = lambda code, mins: self.client.post(  # noqa: E731
            f"/api/aisles/{aid}/cages/", {"code": code, "minutes": mins}, format="json"
        ).json()["id"]
        self.a1 = mk("A1", 60)
        self.a2 = mk("A2", 20)

    def _put(self, cage_id, percent, day="2026-11-09"):
        return self.client.put(
            "/api/feed/", {"date": day, "cage_id": cage_id, "percent": percent}, format="json"
        )

    def _summary(self, day="2026-11-09"):
        return self.client.get(f"/api/feed/summary/?date={day}").json()

    def test_upsert_saves_then_updates(self):
        from tracker.models import CageFeed

        self.assertEqual(self._put(self.a1, 40).status_code, 200)
        self.assertEqual(self._put(self.a1, 100).json()["percent"], 100)
        self.assertEqual(CageFeed.objects.filter(cage_id=self.a1).count(), 1)
        cages = self._summary()["aisles"][0]["cages"]
        self.assertEqual({c["code"]: c["percent"] for c in cages}, {"A1": 100, "A2": 0})
        # Another date is independent.
        self.assertEqual(self._summary("2026-11-10")["percent_fed"], 0)

    def test_percent_fed_is_time_weighted(self):
        self._put(self.a1, 40)   # 60 min
        self._put(self.a2, 100)  # 20 min
        s = self._summary()
        # (60*40 + 20*100) / 80 = 55, not the plain average 70.
        self.assertEqual(s["percent_fed"], 55)
        self.assertEqual(s["aisles"][0]["percent_fed"], 55)
        self.assertEqual(s["aisles"][0]["cages"][0]["planned_minutes"], 60)
        self._put(self.a1, 50)  # (3000 + 2000) / 80 = 62.5 -> rounds half up
        self.assertEqual(self._summary()["percent_fed"], 63)

    def test_percent_range_validated(self):
        self.assertEqual(self._put(self.a1, 101).status_code, 400)
        self.assertEqual(self._put(self.a1, -1).status_code, 400)
        self.assertEqual(self._put(self.a1, "abc").status_code, 400)

    def test_other_users_cage_is_404(self):
        other = self.make_user("intruder")
        self.client.force_authenticate(other)
        self.assertEqual(self._put(self.a1, 50).status_code, 404)
        self.assertEqual(self._summary()["aisles"], [])

