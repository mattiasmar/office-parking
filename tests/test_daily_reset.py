"""Story 5: a fresh lot every day, at midnight Israel time, summer time included."""

import pytest

from support import TOTAL_SPOTS, lot_text, tap_park


@pytest.mark.parametrize("utc, parked_on, still_full", [
    ("2026-01-15T21:59:00+00:00", "2026-01-15", True),     # 23:59 Israel winter time (UTC+2)
    ("2026-01-15T22:01:00+00:00", "2026-01-15", False),    # 00:01
    ("2026-07-15T20:59:00+00:00", "2026-07-15", True),     # 23:59 Israel summer time (UTC+3)
    ("2026-07-15T21:01:00+00:00", "2026-07-15", False),    # 00:01
])
def test_lot_empties_at_israel_midnight(open_app, db, freeze_clock, utc, parked_on, still_full):
    freeze_clock(utc)
    for i in range(TOTAL_SPOTS):
        db.add(f"Colleague {i}", day=parked_on)
    text = lot_text(open_app("Avi"))
    if still_full:
        assert "The lot is full" in text
    else:
        assert f"{TOTAL_SPOTS} of {TOTAL_SPOTS} spots free" in text


def test_parking_just_after_midnight_counts_for_the_new_day(open_app, phone, db, freeze_clock):
    freeze_clock("2026-07-15T21:01:00+00:00")               # 00:01 on 16 July in Israel
    tap_park(open_app("Avi"), phone)
    assert db.parked("2026-07-16") == ["Avi"]
