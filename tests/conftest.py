"""
Tests for the office parking app.

Run from the repo root:
    pip install -r requirements.txt pytest pyyaml
    pytest tests
    node --test tests/geolocation.test.js

The app runs under Streamlit's AppTest with the database and the phone's
location faked (see support.py), so no Supabase project or browser is needed.
"""

import datetime as dt

import pytest
import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit.testing.v1 import AppTest

from support import APP_FILE, FakePhone, FakeSupabase


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


@pytest.fixture
def open_app(db, phone):
    """Opens the app like a phone would: open_app("Avi") is Avi's bookmarked link."""
    def open_app(user=None, *, secrets=True, employees=None):
        at = AppTest.from_file(str(APP_FILE), default_timeout=30)
        if secrets:
            at.secrets["supabase_url"] = "https://example.supabase.co"
            at.secrets["supabase_key"] = "test-key"
        if employees is not None:
            at.secrets["employees"] = employees
        if user is not None:
            at.query_params["user"] = user
        at.run()
        assert not at.exception, at.exception
        return at
    return open_app


@pytest.fixture
def freeze_clock(monkeypatch):
    """freeze_clock("2026-07-15T21:01:00+00:00") stops the app's clock at that instant."""
    real = dt.datetime

    class AnyDatetime(type):
        def __instancecheck__(cls, obj):
            return isinstance(obj, real)

    def freeze(utc_iso):
        instant = real.fromisoformat(utc_iso)

        class FrozenDatetime(real, metaclass=AnyDatetime):
            @classmethod
            def now(cls, tz=None):
                return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

        monkeypatch.setattr(dt, "datetime", FrozenDatetime)
    return freeze
