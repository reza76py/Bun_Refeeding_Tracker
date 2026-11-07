"""
Domain calculations for the Shelf Replenishment Workload Tracker.

This module is deliberately free of Django and database imports so the
business logic can be unit-tested in isolation and reused anywhere.

Golden rule of the tool: the numbers produced here are *forecasts* derived
from editable planning assumptions. They are never to be presented as
measured actual time. Measured values come from user-entered actuals and are
handled separately in the API/models layer.

All durations are integer seconds.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Sequence

# --- Provisional planning baseline (NOT a verified industry standard) -----
# These mirror the brief's variables A-G. They are starting assumptions the
# user is expected to edit and, over time, replace with measured values.
DEFAULT_FIND_SEC = 30          # D: find correct shelf location (sec/line)
DEFAULT_UNPACK_SEC = 10        # E: pick up / grab and unpack (sec/line)
DEFAULT_SECONDS_PER_UNIT = 1   # F: put one unit onto the shelf (sec/unit)
DEFAULT_UNITS_PER_LINE = 5     # C: units per barcode line
DEFAULT_OTHER_SEC = 0          # G: cleanup/cage movement, excluded in baseline
DEFAULT_LINES_PER_CAGE = 100   # B: replenishment barcode lines per cage
DEFAULT_CAGES_MIN = 2          # A: rough daily minimum
DEFAULT_CAGES_MAX = 5          # A: rough daily maximum


@dataclass(frozen=True)
class Assumptions:
    """A single, immutable set of planning assumptions.

    One barcode *line* = one distinct product-location replenishment
    operation (find shelf, handle pack, place ~N units). It is not a count of
    scanned barcodes from any Bunnings system.
    """

    find_sec: int = DEFAULT_FIND_SEC
    unpack_sec: int = DEFAULT_UNPACK_SEC
    seconds_per_unit: int = DEFAULT_SECONDS_PER_UNIT
    units_per_line: int = DEFAULT_UNITS_PER_LINE
    other_sec: int = DEFAULT_OTHER_SEC
    default_lines_per_cage: int = DEFAULT_LINES_PER_CAGE

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: Mapping) -> "Assumptions":
        """Build from a dict, ignoring unrelated keys and falling back to
        defaults for anything missing or explicitly ``None``."""
        fields = {
            "find_sec",
            "unpack_sec",
            "seconds_per_unit",
            "units_per_line",
            "other_sec",
            "default_lines_per_cage",
        }
        kwargs = {}
        for key in fields:
            value = data.get(key)
            if value is not None:
                kwargs[key] = int(value)
        return cls(**kwargs)


# --- Core formulas --------------------------------------------------------

def line_seconds(
    find_sec: int,
    unpack_sec: int,
    seconds_per_unit: int,
    units: int,
    other_sec: int = 0,
) -> int:
    """Active time to replenish one barcode line that places ``units`` items.

        placement_seconds = units * seconds_per_unit
        line_seconds = find + unpack + placement + other
    """
    placement_seconds = units * seconds_per_unit
    return int(find_sec + unpack_sec + placement_seconds + other_sec)


def estimated_line_seconds(a: Assumptions) -> int:
    """Forecast seconds for one line using the assumption's own units/line."""
    return line_seconds(
        a.find_sec, a.unpack_sec, a.seconds_per_unit, a.units_per_line, a.other_sec
    )


def cage_seconds(lines_in_cage: int, per_line_seconds: int) -> int:
    """Forecast seconds for a cage of ``lines_in_cage`` lines."""
    return int(lines_in_cage) * int(per_line_seconds)


def estimated_cage_seconds(
    a: Assumptions,
    lines_in_cage: int | None = None,
    units_per_line: int | None = None,
) -> int:
    """Forecast seconds for one cage.

    ``lines_in_cage``/``units_per_line`` of ``None`` fall back to the
    assumption defaults. An explicit ``0`` is respected (a planned cage with
    zero known lines forecasts zero time — it is not silently treated as the
    default 100).
    """
    lines = a.default_lines_per_cage if lines_in_cage is None else int(lines_in_cage)
    units = a.units_per_line if units_per_line is None else int(units_per_line)
    per_line = line_seconds(
        a.find_sec, a.unpack_sec, a.seconds_per_unit, units, a.other_sec
    )
    return cage_seconds(lines, per_line)


# A cage forecast input: either an int (lines count) or a mapping that may
# carry a per-cage ``line_count`` and/or ``units_per_line`` override.
CageSpec = int | Mapping


def _normalise_cage(spec: CageSpec) -> tuple[int | None, int | None]:
    if isinstance(spec, Mapping):
        lc = spec.get("line_count")
        up = spec.get("units_per_line")
        return (None if lc is None else int(lc), None if up is None else int(up))
    return (int(spec), None)


def estimated_day_seconds(cages: Sequence[CageSpec], a: Assumptions) -> int:
    """Forecast seconds for a day made up of the given cages.

    Zero cages => zero seconds.
    """
    total = 0
    for spec in cages:
        lines, units = _normalise_cage(spec)
        total += estimated_cage_seconds(a, lines, units)
    return total


def estimated_day_seconds_uniform(num_cages: int, a: Assumptions) -> int:
    """Forecast a day of ``num_cages`` identical cages at the default size."""
    if num_cages <= 0:
        return 0
    return estimated_cage_seconds(a) * int(num_cages)


def scenario_table(a: Assumptions, cages_min: int, cages_max: int) -> list[dict]:
    """Per-day forecast for each cage count in the min..max range.

    Used by the Overview mini-table and the Calculator page.
    """
    rows = []
    if cages_min > cages_max:
        cages_min, cages_max = cages_max, cages_min
    for n in range(max(0, cages_min), max(0, cages_max) + 1):
        day_sec = estimated_day_seconds_uniform(n, a)
        rows.append(
            {
                "cages": n,
                "line_operations": n * a.default_lines_per_cage,
                "units_handled": n * a.default_lines_per_cage * a.units_per_line,
                "day_seconds": day_sec,
            }
        )
    return rows


# --- Catalogue (area size) helpers ---------------------------------------
# These describe area size only. They are NOT a count of what gets replenished
# on any given day and must never be turned into a "% of catalogue replenished"
# figure without measured, unique-line evidence.

def default_bays_aisle9() -> list[tuple[int, int]]:
    """(bay_number, catalogue_lines) for aisle 9: odd bays 150, even bays 200."""
    return [(n, 150 if n % 2 == 1 else 200) for n in range(1, 19)]


def default_bays_aisle10() -> list[tuple[int, int]]:
    """(bay_number, catalogue_lines) for aisle 10: 100 per bay."""
    return [(n, 100) for n in range(1, 19)]


def catalogue_total(bays: Iterable[tuple[int, int]]) -> int:
    """Sum of catalogue lines across the given (bay_number, lines) pairs."""
    return sum(int(lines) for _bay, lines in bays)


# --- Formatting -----------------------------------------------------------

def seconds_to_hm(total_seconds: int) -> str:
    """Format seconds as 'Xh Ym' (used in reports/tests; the UI formats too)."""
    total_seconds = int(total_seconds)
    minutes, _seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"
