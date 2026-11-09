"""
Tests for the office parking app.

Run from the repo root:
    pip install -r requirements.txt pytest pyyaml
    pytest tests
    node --test tests/geolocation.test.js

The app runs under Streamlit's AppTest with the database and the phone's
location faked (see support.py), so no Supabase project or browser is needed.
"""

import sys

import pytest
import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit.runtime.pages_manager import PagesManager
from streamlit.testing.v1 import AppTest

from support import APP_FILE, MANAGER_PASSWORD, ROOT, FakePhone, FakeSupabase, button

sys.path.insert(0, str(ROOT))           # so the app finds store.py, as on Streamlit Cloud


@pytest.fixture(autouse=True)
def fresh_pages_flag(monkeypatch):
    # Streamlit decides once per process whether the app has a pages/ folder.
    # The clock tests run a copy of the app from a folder without one, so let
    # every test decide afresh.
    monkeypatch.setattr(PagesManager, "uses_pages_directory", None)


@pytest.fixture
def db(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(requests.Session, "request",
                        lambda session, method, url, **kw: fake.handle(method, url, **kw))
    st.cache_data.clear()
    st.cache_resource.clear()
    return fake


@pytest.fixture
def phone(monkeypatch):
    fake = FakePhone()
    monkeypatch.setattr(components, "declare_component", lambda *args, **kwargs: fake)
    return fake


def app_source_frozen_at(utc_iso):
    """The app's source with its clock stopped at utc_iso."""
    source = APP_FILE.read_text()
    assert "from datetime import datetime\n" in source
    return source.replace("from datetime import datetime\n", (
        "from datetime import datetime as _datetime\n\n\n"
        "class datetime(_datetime):\n"
        "    @classmethod\n"
        "    def now(cls, tz=None):\n"
        f"        return _datetime.fromisoformat({utc_iso!r}).astimezone(tz)\n"), 1)


@pytest.fixture
def open_app(db, phone):
    """Opens the app like a phone would: open_app("Avi") is Avi's bookmarked link.
    now="2026-07-15T21:01:00+00:00" stops the app's clock at that instant."""
    def open_app(user=None, *, secrets=True, employees=None, now=None):
        if now is None:
            at = AppTest.from_file(str(APP_FILE), default_timeout=30)
        else:
            at = AppTest.from_string(app_source_frozen_at(now), default_timeout=30)
        if secrets:
            at.secrets["supabase_url"] = "https://example.supabase.co"
            at.secrets["supabase_key"] = "test-key"
        if employees is not None:
            db.set_staff(employees)
        if user is not None:
            at.query_params["user"] = user
        at.run()
        assert not at.exception, at.exception
        return at
    return open_app


@pytest.fixture
def open_manager(db):
    """Opens /mngr in a new browser session and logs in with `password`
    (None: don't log in). configured=False: no manager_password in Secrets."""
    def open_manager(password=MANAGER_PASSWORD, *, configured=True):
        at = AppTest.from_file(str(APP_FILE), default_timeout=30)
        at.secrets["supabase_url"] = "https://example.supabase.co"
        at.secrets["supabase_key"] = "test-key"
        if configured:
            at.secrets["manager_password"] = MANAGER_PASSWORD
        at.switch_page("pages/mngr.py").run()
        if password is not None:
            at.text_input[0].input(password)
            button(at, "Open").click().run()
        assert not at.exception, at.exception
        return at
    return open_manager
