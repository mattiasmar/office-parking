"""Story 7: a plain message instead of a crash when something breaks."""

from support import button, button_labels, messages, tap_park

TRY_AGAIN = "Couldn't save your change. Tap again in a moment."


def test_unreachable_database_is_reported(open_app, db):
    db.down = True
    at = open_app("Avi")
    assert any(m.startswith("Can't reach the parking database.") for m in messages(at))
    assert button_labels(at) == []


def test_failed_park_asks_me_to_try_again(open_app, phone, db):
    at = open_app("Avi")
    db.failing.add("POST")
    tap_park(at, phone)
    assert TRY_AGAIN in messages(at)
    assert db.parked() == []


def test_failed_undo_asks_me_to_try_again(open_app, db):
    db.add("Avi")
    at = open_app("Avi")
    db.failing.add("DELETE")
    button(at, "Undo, free my spot").click().run()
    assert TRY_AGAIN in messages(at)
    assert db.parked() == ["Avi"]


def test_missing_setup_explains_what_is_missing(open_app):
    at = open_app("Avi", secrets=False)
    (help_text,) = [m for m in messages(at) if "parking database" in m]
    for needed in ("supabase_url", "supabase_key", "supabase_setup.sql"):
        assert needed in help_text
