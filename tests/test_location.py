"""Story 10: "I've parked" works only within OFFICE_RADIUS_M of the office."""

import re

import pytest

from support import HAIFA, OFFICE_RADIUS_M, button, button_labels, messages, near_office, tap_park

R = OFFICE_RADIUS_M


@pytest.mark.parametrize("north, east", [(0, 0), (0.95 * R, 0), (0, -0.95 * R), (-0.67 * R, 0.67 * R)])
def test_parks_within_the_radius(open_app, phone, db, north, east):
    tap_park(open_app("Avi"), phone, near_office(north, east))
    assert db.parked() == ["Avi"]


@pytest.mark.parametrize("north, east", [(1.05 * R, 0), (0, 1.05 * R), (-0.75 * R, -0.75 * R)])
def test_refuses_outside_the_radius(open_app, phone, db, north, east):
    at = tap_park(open_app("Avi"), phone, near_office(north, east))
    assert db.parked() == []
    assert any(f"You can mark your car as parked only within {R} m of it." in m for m in messages(at))
    assert "I've parked" in button_labels(at)                      # can try again


def test_refusal_says_how_far_away_i_am(open_app, phone, db):
    at = tap_park(open_app("Avi"), phone, HAIFA)
    (msg,) = [m for m in messages(at) if "from the office" in m]
    metres = int(re.match(r"You're ([\d,]+) m from the office", msg).group(1).replace(",", ""))
    assert 17_000 < metres < 20_000                              # Haifa is about 18 km away
    assert db.parked() == []


def test_location_is_asked_only_after_tapping(open_app, phone):
    open_app("Avi")
    assert phone.asked == []


def test_waits_for_the_phone_before_parking(open_app, phone, db):
    at = open_app("Avi")
    button(at, "I've parked").click().run()
    assert button(at, "Checking your location…").disabled
    at.run()                                                     # board refreshes meanwhile
    assert button(at, "Checking your location…").disabled
    assert db.parked() == []
    phone.answer = near_office()
    at.run()
    assert db.parked() == ["Avi"]


def test_each_tap_takes_a_fresh_reading(open_app, phone):
    at = open_app("Avi")
    tap_park(at, phone, HAIFA)
    tap_park(at, phone, HAIFA)
    assert len(set(phone.asked)) == 2


def test_location_refused_or_unavailable_is_explained(open_app, phone, db):
    at = tap_park(open_app("Avi"), phone, {"error": "User denied Geolocation"})
    assert ("Couldn't get your location (User denied Geolocation). "
            "Allow location access for this site and tap again.") in messages(at)
    assert db.parked() == []


def test_undo_works_from_anywhere(open_app, phone, db):
    db.add("Avi")
    at = open_app("Avi")
    phone.answer = HAIFA
    button(at, "Undo, free my spot").click().run()
    assert db.parked() == [] and phone.asked == []
