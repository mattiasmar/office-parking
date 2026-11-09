"""
Database access shared by the parking page (streamlit_app.py) and the
manager page (pages/mngr.py), through Supabase's REST API.
"""

import requests
import streamlit as st


@st.cache_resource
def get_api() -> tuple[str, requests.Session]:
    base = st.secrets["supabase_url"].rstrip("/") + "/rest/v1"
    key = st.secrets["supabase_key"]
    s = requests.Session()
    s.headers["apikey"] = key
    if not key.startswith("sb_"):               # legacy service_role JWT key
        s.headers["Authorization"] = f"Bearer {key}"
    return base, s


def call(method: str, path: str, **kwargs):
    base, s = get_api()
    r = s.request(method, f"{base}/{path}", timeout=10, **kwargs)
    r.raise_for_status()
    return r.json() if r.content else None


# The staff list is the one row of the "settings" table (supabase_employees.sql):
# [{"name": ..., "password": ...}, ...] in the order the manager typed it.

@st.cache_data(ttl=60, show_spinner=False)
def load_staff() -> list[dict]:
    rows = call("GET", "settings", params={"select": "employees", "id": "eq.1"})
    return rows[0]["employees"] if rows else []


def save_staff(staff: list[dict]) -> None:
    call("POST", "settings", json={"id": 1, "employees": staff},
         headers={"Prefer": "resolution=merge-duplicates"})
    load_staff.clear()
