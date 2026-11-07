"""Unit tests for the pure domain calculations (brief section 10).

These need no database and no Django, so they double as a plain-unittest
suite: `python -m unittest tracker.tests.test_calculations`.
"""

import unittest

from tracker.calculations import (
    Assumptions,
    catalogue_total,
    default_bays_aisle9,
    default_bays_aisle10,
    estimated_cage_seconds,
    estimated_day_seconds,
    estimated_day_seconds_uniform,
    estimated_line_seconds,
    line_seconds,
    scenario_table,
    seconds_to_hm,
)


class CatalogueTotalsTests(unittest.TestCase):
    def test_aisle9_total_is_3150(self):
        # 9 odd bays * 150 + 9 even bays * 200
        self.assertEqual(catalogue_total(default_bays_aisle9()), 3150)

    def test_aisle10_total_is_1800(self):
        self.assertEqual(catalogue_total(default_bays_aisle10()), 1800)

    def test_combined_total_is_4950(self):
        combined = default_bays_aisle9() + default_bays_aisle10()
        self.assertEqual(catalogue_total(combined), 4950)


class BaselineLineTests(unittest.TestCase):
    def test_baseline_line_is_45_seconds(self):
        # 30 find + 10 unpack + (5 units * 1 sec) + 0 other
        self.assertEqual(estimated_line_seconds(Assumptions()), 45)
        self.assertEqual(line_seconds(30, 10, 1, 5, 0), 45)


class CageAndDayTests(unittest.TestCase):
    def setUp(self):
        self.a = Assumptions()  # baseline 45 s/line, 100 lines/cage

    def test_100_lines_per_cage_is_4500_seconds_75_minutes(self):
        cage = estimated_cage_seconds(self.a)
        self.assertEqual(cage, 4500)
        self.assertEqual(cage, 75 * 60)

    def test_cage_count_scenarios(self):
        # (cages, expected day seconds)
        cases = {2: 9000, 3: 13500, 4: 18000, 5: 22500}
        for cages, expected in cases.items():
            with self.subTest(cages=cages):
                self.assertEqual(
                    estimated_day_seconds_uniform(cages, self.a), expected
                )

    def test_zero_cages_is_zero_seconds(self):
        self.assertEqual(estimated_day_seconds_uniform(0, self.a), 0)
        self.assertEqual(estimated_day_seconds([], self.a), 0)


class SensitivityTests(unittest.TestCase):
    def test_find_time_30_to_40_adds_1000_sec_per_100_line_cage(self):
        base = estimated_cage_seconds(Assumptions(find_sec=30))
        changed = estimated_cage_seconds(Assumptions(find_sec=40))
        self.assertEqual(changed - base, 1000)  # 10 extra sec * 100 lines
        self.assertEqual((changed - base), 16 * 60 + 40)  # 16m40s

    def test_units_5_to_8_makes_placement_8_seconds(self):
        # At 1 sec/unit, placing 8 units costs 8 seconds of placement.
        self.assertEqual(line_seconds(0, 0, 1, 8, 0), 8)
        # Whole line with 8 units: 30 + 10 + 8 + 0 = 48
        self.assertEqual(estimated_line_seconds(Assumptions(units_per_line=8)), 48)


class CageOverrideTests(unittest.TestCase):
    def test_planned_cage_with_zero_lines_is_zero_not_default_100(self):
        a = Assumptions()
        self.assertEqual(estimated_cage_seconds(a, lines_in_cage=0), 0)
        # Unknown (None) falls back to the default 100-line forecast.
        self.assertEqual(estimated_cage_seconds(a, lines_in_cage=None), 4500)

    def test_per_cage_overrides_in_day_total(self):
        a = Assumptions()
        cages = [
            {"line_count": 50},                 # 50 * 45 = 2250
            {"line_count": 100, "units_per_line": 8},  # 100 * 48 = 4800
            {},                                 # default 100 * 45 = 4500
        ]
        self.assertEqual(estimated_day_seconds(cages, a), 2250 + 4800 + 4500)


class ScenarioTableTests(unittest.TestCase):
    def test_scenario_table_matches_brief(self):
        rows = scenario_table(Assumptions(), 2, 5)
        self.assertEqual([r["cages"] for r in rows], [2, 3, 4, 5])
        self.assertEqual(rows[0]["day_seconds"], 9000)
        self.assertEqual(rows[-1]["day_seconds"], 22500)
        self.assertEqual(rows[-1]["units_handled"], 5 * 100 * 5)  # 2500


class FormattingTests(unittest.TestCase):
    def test_seconds_to_hm(self):
        self.assertEqual(seconds_to_hm(4500), "1h 15m")
        self.assertEqual(seconds_to_hm(9000), "2h 30m")
        self.assertEqual(seconds_to_hm(22500), "6h 15m")
        self.assertEqual(seconds_to_hm(0), "0h 0m")


if __name__ == "__main__":
    unittest.main()
