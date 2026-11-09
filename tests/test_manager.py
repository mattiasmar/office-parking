"""Manager page (/mngr): edit the staff list; each person gets a password."""

import re

from support import (DEFAULT_STAFF, bays, button, button_labels, messages, page_text,
                     tap_park)


def save(at, text):
    at.text_area[0].input(text)
    return button(at, "Save").click().run()


def shown_passwords(at) -> dict[str, str]:
    table = at.dataframe[0].value
    return dict(zip(table["Name"], table["Password"]))


# ---------------------------------------------------------------- getting in ---
def test_locked_until_a_manager_password_is_set(open_manager, db):
    at = open_manager(password=None, configured=False)
    assert "This page is locked. Set manager_password in the app's Secrets to use it." in messages(at)
    assert not at.text_input and not at.text_area and not at.dataframe


def test_wrong_password_shows_nothing(open_manager, db):
    at = open_manager(password="guess")
    assert "Wrong password." in messages(at)
    assert not at.text_area and not at.dataframe
    assert not any(p["password"] in page_text(at) for p in db.staff)


def test_right_password_shows_the_list_and_passwords(open_manager, db):
    at = open_manager()
    assert at.text_area[0].value.splitlines() == db.staff_names()
    assert shown_passwords(at) == db.passwords()


def test_password_is_asked_again_in_a_new_session(open_manager):
    open_manager()
    at = open_manager(password=None)
    assert at.text_input[0].label == "Manager password"
    assert not at.text_area


# --------------------------------------------------------------- editing ---
def test_saved_list_reaches_the_parking_page_right_away(open_manager, open_app, db):
    at = save(open_manager(), "Avi\nNoa\nZohar")
    assert "Saved. 3 people on the list." in messages(at)
    assert db.staff_names() == ["Avi", "Noa", "Zohar"]
    assert open_app().selectbox[0].options == ["Avi", "Noa", "Zohar"]


def test_spaces_blank_lines_and_duplicates_are_cleaned_up(open_manager, db):
    at = save(open_manager(), "  Avi \n\nNoa\nAvi\n   \n")
    assert db.staff_names() == ["Avi", "Noa"]
    assert at.text_area[0].value == "Avi\nNoa"


def test_removed_person_bookmark_no_longer_selects_them(open_manager, open_app, db):
    save(open_manager(), "Avi\nDana")
    assert open_app("Noa").selectbox[0].value is None


def test_failed_save_says_so_and_keeps_the_list(open_manager, db):
    at = open_manager()
    db.failing.add("POST")
    save(at, "Zohar")
    assert "Couldn't save. Try again in a moment." in messages(at)
    assert db.staff == DEFAULT_STAFF
    assert shown_passwords(at) == db.passwords()


def test_name_with_html_shows_as_text_on_the_board(open_manager, open_app, phone, db):
    save(open_manager(), "<b>Bo</b>")
    tap_park(open_app("<b>Bo</b>"), phone)
    assert ("&lt;b&gt;Bo&lt;/b&gt;", "bay mine") in bays(open_app("<b>Bo</b>"))


# ------------------------------------------------------------- passwords ---
def test_new_people_get_their_own_8_character_password(open_manager, db):
    at = save(open_manager(), "Avi\nZohar\nYael")
    new = [db.passwords()["Zohar"], db.passwords()["Yael"]]
    assert all(re.fullmatch(r"[A-Za-z0-9]{8}", p) for p in new), new
    assert len(set(db.passwords().values())) == 3
    assert shown_passwords(at) == db.passwords()


def test_passwords_mix_upper_and_lower_case_letters_and_digits(open_manager, db):
    save(open_manager(), "\n".join(f"Person {i}" for i in range(30)))
    chars = "".join(db.passwords().values())      # 240 random characters
    for kind in (str.isupper, str.islower, str.isdigit):
        assert any(kind(c) for c in chars), kind.__name__


def test_people_who_stay_keep_their_password(open_manager, db):
    before = db.passwords()
    save(open_manager(), "Noa\nAvi\nZohar")              # Dana, Eitan, Maya, Yossi removed
    assert db.passwords()["Avi"] == before["Avi"]
    assert db.passwords()["Noa"] == before["Noa"]


def test_removed_and_re_added_person_gets_a_new_password(open_manager, db):
    old = db.passwords()["Avi"]
    at = save(open_manager(), "Noa")
    save(at, "Noa\nAvi")
    assert db.passwords()["Avi"] != old


def test_parking_page_never_shows_passwords_or_asks_for_one(open_app, phone, db):
    db.add("Noa")
    at = tap_park(open_app("Avi"), phone)
    text = page_text(at)
    assert not [p for p in db.staff if p["password"] in text]
    assert not at.text_input
    assert "Undo, free my spot" in button_labels(at)
