"""Stories 1-4: identify myself once, take a spot, see the lot, free my spot."""

from support import (TOTAL_SPOTS, bays, button, button_labels, israel_today, lot_text,
                     messages, reload, tap_park)


def fill_lot(db, but=0):
    for i in range(TOTAL_SPOTS - but):
        db.add(f"Colleague {i}")


# ------------------------------------------------------- 1. identify myself ---
def test_without_a_name_i_see_the_board_but_cannot_take_or_free(open_app, db):
    db.add("Dana")
    at = open_app()
    assert "Dana" in lot_text(at)
    assert button_labels(at) == []
    assert "Pick your name above to take or free a spot." in messages(at)


def test_bookmarked_link_opens_with_my_name(open_app):
    at = open_app("Noa")
    assert at.selectbox[0].value == "Noa"
    assert "I've parked" in button_labels(at)


def test_picking_my_name_puts_it_in_the_link(open_app):
    at = open_app()
    at.selectbox[0].select("Maya").run()
    assert at.query_params["user"] in ("Maya", ["Maya"])


def test_name_not_on_the_staff_list_is_ignored(open_app):
    at = open_app("Mallory")
    assert at.selectbox[0].value is None
    assert button_labels(at) == []


def test_picker_shows_the_managers_staff_list(open_app):
    at = open_app(employees=["Zohar", "Yael"])
    assert at.selectbox[0].options == ["Zohar", "Yael"]


# -------------------------------------------------------- 2. take a spot ---
def test_tapping_takes_a_spot(open_app, phone, db):
    at = tap_park(open_app("Avi"), phone)
    assert db.parked() == ["Avi"]
    assert "You're parked. The spot is yours until midnight." in messages(at)
    assert "Undo, free my spot" in button_labels(at)
    assert "I've parked" not in button_labels(at)


def test_database_is_asked_for_today_and_the_lot_size(open_app, phone, db):
    tap_park(open_app("Avi"), phone)
    sent = [body for method, path, _, body in db.requests if path == "rpc/park"]
    assert sent == [{"p_employee": "Avi", "p_day": israel_today(), "p_spots": TOTAL_SPOTS}]


def test_full_lot_button_reads_lot_full_and_cannot_be_tapped(open_app, db):
    fill_lot(db)
    at = open_app("Avi")
    assert button(at, "Lot full").disabled
    assert "I've parked" not in button_labels(at)


def test_last_spot_taken_while_i_look_fails_clearly(open_app, phone, db):
    fill_lot(db, but=1)
    at = open_app("Avi")
    db.add("Faster colleague")
    tap_park(at, phone)
    assert "Someone took the last spot just before you. The lot is full." in messages(at)
    assert len(db.parked()) == TOTAL_SPOTS and "Avi" not in db.parked()
    assert button(at, "Lot full").disabled


def test_one_spot_per_person_per_day(open_app, phone, db):
    at = open_app("Avi")
    db.add("Avi")                                   # parked from another phone meanwhile
    tap_park(at, phone)
    assert "You already have a spot today." in messages(at)
    assert db.parked() == ["Avi"]


# --------------------------------------------------------- 3. see the lot ---
def test_board_shows_free_spots_and_names_in_arrival_order(open_app, db):
    db.add("Noa", time="08:40")
    db.add("Eitan", time="07:55")
    at = open_app("Maya")
    assert f"{TOTAL_SPOTS - 2} of {TOTAL_SPOTS} spots free" in lot_text(at)
    assert [who for who, _ in bays(at)] == ["Eitan", "Noa"] + ["Free"] * (TOTAL_SPOTS - 2)


def test_full_lot_says_so(open_app, db):
    fill_lot(db)
    assert "0 spots free. The lot is full." in lot_text(open_app("Avi"))


def test_my_spot_stands_out(open_app, db):
    db.add("Noa")
    db.add("Maya")
    taken = dict(bays(open_app("Maya")))
    assert taken["Maya"] == "bay mine" and taken["Noa"] == "bay"


def test_bays_show_no_parking_time(open_app, db):
    db.add("Noa")
    assert "since" not in lot_text(open_app("Maya"))


# ------------------------------------------------------- 4. free my spot ---
def test_undo_frees_only_my_spot_and_only_today(open_app, db):
    db.add("Avi", day=israel_today(days_ago=1))
    db.add("Avi")
    db.add("Noa")
    at = open_app("Avi")
    button(at, "Undo, free my spot").click().run()
    assert "Your spot is free again." in messages(at)
    assert db.parked() == ["Noa"]
    assert db.parked(israel_today(days_ago=1)) == ["Avi"]
    assert "I've parked" in button_labels(at)


def test_i_cannot_free_someone_elses_spot(open_app, db):
    db.add("Noa")
    assert "Undo, free my spot" not in button_labels(open_app("Avi"))


def test_freed_spot_can_be_taken_right_away(open_app, phone, db):
    fill_lot(db, but=1)
    db.add("Noa")
    avi = open_app("Avi")
    assert button(avi, "Lot full").disabled
    noa = open_app("Noa")
    button(noa, "Undo, free my spot").click().run()
    reload(avi)
    tap_park(avi, phone)
    assert "Avi" in db.parked() and "Noa" not in db.parked()
