"""Fakes and helpers shared by the tests (the fixtures are in conftest.py)."""

import ast
import copy
import datetime as dt
import json
import math
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
APP_FILE = ROOT / "streamlit_app.py"
STORE_FILE = ROOT / "store.py"
WORKFLOW_FILE = ROOT / ".github" / "workflows" / "keep-awake.yml"
ISRAEL = ZoneInfo("Asia/Jerusalem")

MANAGER_PASSWORD = "manager-test-pw"
DEFAULT_STAFF = [
    {"name": "Avi", "password": "Qx7aB2mK"},
    {"name": "Dana", "password": "pL4nW9sT"},
    {"name": "Eitan", "password": "R3vY8cHd"},
    {"name": "Maya", "password": "z6KfJ1qE"},
    {"name": "Noa", "password": "M9tG2wXb"},
    {"name": "Yossi", "password": "h5NcV7rP"},
]


def app_setting(name: str):
    """A top-level constant from streamlit_app.py, read without running the app."""
    for node in ast.parse(APP_FILE.read_text()).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(name)


TOTAL_SPOTS = app_setting("TOTAL_SPOTS")
OFFICE = app_setting("OFFICE")
OFFICE_RADIUS_M = app_setting("OFFICE_RADIUS_M")

M_PER_DEGREE = 6_371_000 * math.pi / 180      # along a meridian, same sphere as the app
HAIFA = {"lat": 32.7940, "lon": 34.9896, "accuracy": 20}


def near_office(north_m: float = 0, east_m: float = 0, accuracy: float = 10) -> dict:
    """What the phone reports when it stands this many metres from OFFICE."""
    lat, lon = OFFICE
    return {"lat": lat + north_m / M_PER_DEGREE,
            "lon": lon + east_m / (M_PER_DEGREE * math.cos(math.radians(lat))),
            "accuracy": accuracy}


def israel_today(days_ago: int = 0) -> str:
    return (dt.datetime.now(ISRAEL).date() - dt.timedelta(days=days_ago)).isoformat()


# ------------------------------------------------------------------- fakes ---
def _response(status: int, body=None) -> requests.Response:
    r = requests.Response()
    r.status_code = status
    r._content = b"" if body is None else json.dumps(body).encode()
    r.url = "https://example.supabase.co"
    return r


class FakeSupabase:
    """In-memory stand-in for the parts of Supabase's REST API the app uses.

    rpc/park behaves like the database's park() function: "already" if the
    employee has a spot that day, "full" if all p_spots are taken, else it
    inserts the parking and returns "ok". Rows come back in insertion order
    unless the app asks for order=parked_at, like Postgres without ORDER BY.
    The settings row (supabase_employees.sql) holds the staff list; writing
    it needs the upsert header, as in PostgREST.
    """

    def __init__(self):
        self.rows = []          # {"employee", "day", "parked_at"}
        self.staff = copy.deepcopy(DEFAULT_STAFF)    # settings.employees
        self.settings_table = True                   # False: supabase_employees.sql not run
        self.requests = []      # (method, path, params, json body)
        self.down = False       # every call fails, as if the database were unreachable
        self.failing = set()    # HTTP methods that answer 500

    def set_staff(self, names: list[str]) -> None:
        self.staff = [{"name": n, "password": f"pw{i:06d}"} for i, n in enumerate(names)]

    def staff_names(self) -> list[str]:
        return [p["name"] for p in self.staff]

    def passwords(self) -> dict[str, str]:
        return {p["name"]: p["password"] for p in self.staff}

    def add(self, employee: str, day: str | None = None, time: str = "08:00") -> None:
        day = day or israel_today()
        self.rows.append({"employee": employee, "day": day, "parked_at": f"{day}T{time}:00+03:00"})

    def handle(self, method, url, params=None, json=None, headers=None, **_):
        path = url.split("/rest/v1/", 1)[1]
        params = dict(params or {})
        self.requests.append((method, path, params, json))
        if self.down:
            raise requests.ConnectionError("database unreachable")
        if method in self.failing:
            return _response(500, {"message": "server error"})
        if path == "settings":
            return self._settings(method, params, json, headers or {})
        if (method, path) == ("GET", "parkings"):
            rows = self._match(params)
            if params.get("order") == "parked_at":
                rows = sorted(rows, key=lambda r: r["parked_at"])
            cols = params["select"].split(",")
            return _response(200, [{c: r[c] for c in cols} for r in rows])
        if (method, path) == ("DELETE", "parkings"):
            gone = self._match(params)
            self.rows = [r for r in self.rows if r not in gone]
            return _response(204)
        if (method, path) == ("POST", "rpc/park"):
            today = [r for r in self.rows if r["day"] == json["p_day"]]
            if any(r["employee"] == json["p_employee"] for r in today):
                return _response(200, "already")
            if len(today) >= json["p_spots"]:
                return _response(200, "full")
            self.add(json["p_employee"], json["p_day"], f"{9 + len(today):02d}:00")
            return _response(200, "ok")
        raise AssertionError(f"unexpected request {method} {path}")

    def _settings(self, method, params, body, headers):
        if not self.settings_table:
            return _response(404, {"message": 'relation "public.settings" does not exist'})
        if method == "GET":
            assert params == {"select": "employees", "id": "eq.1"}, params
            return _response(200, [{"employees": copy.deepcopy(self.staff)}])
        if method == "POST":
            if headers.get("Prefer") != "resolution=merge-duplicates":
                return _response(409, {"message": "duplicate key value violates unique constraint"})
            assert body["id"] == 1, body
            self.staff = copy.deepcopy(body["employees"])
            return _response(201)
        raise AssertionError(f"unexpected request {method} settings")

    def _match(self, params):
        rows = self.rows
        for col in ("day", "employee"):
            if col in params:
                op, value = params[col].split(".", 1)
                rows = [r for r in rows if (r[col] == value if op == "eq" else r[col] >= value)]
        return rows

    def parked(self, day: str | None = None) -> list[str]:
        day = day or israel_today()
        return [r["employee"] for r in self.rows if r["day"] == day]


class FakePhone:
    """Stands in for the browser's geolocation component (geolocation/index.html).

    answer is what the browser sends back; None means it hasn't answered yet.
    asked lists the component keys the app mounted, one per location request.
    """

    def __init__(self):
        self.answer = None
        self.asked = []

    def __call__(self, key=None, default=None):
        self.asked.append(key)
        return default if self.answer is None else self.answer


# ------------------------------------------------------- reading the page ---
def button(at, label):
    return next(b for b in at.button if b.label == label)


def button_labels(at) -> list[str]:
    return [b.label for b in at.button]


def messages(at) -> list[str]:
    return [m.value for kind in ("success", "info", "error") for m in getattr(at, kind)]


def page_text(at) -> str:
    """Everything the page shows or sends to the browser, as one string."""
    def walk(node):
        proto = getattr(node, "proto", None)
        yield "" if proto is None else str(proto)
        for child in getattr(node, "children", {}).values():
            yield from walk(child)
    return "\n".join(walk(at._tree))


def lot_text(at) -> str:
    """The board (status line and bays) as plain text."""
    html = " ".join(m.value for m in at.markdown if 'class="lot' in m.value)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>|&nbsp;", " ", html)).strip()


def bays(at) -> list[tuple[str, str]]:
    """(name or "Free", css class) for each bay, left to right."""
    html = next(m.value for m in at.markdown if 'class="lot"' in m.value)
    bay = r'<div class="(bay[^"]*)"><div class="num">\d+</div><div class="who">([^<]*)</div>'
    return [(who, cls) for cls, who in re.findall(bay, html)]


def tap_park(at, phone, where: dict | None = None):
    """Tap "I've parked"; the phone then answers with `where` (default: at the office)."""
    phone.answer = None
    button(at, "I've parked").click().run()
    phone.answer = near_office() if where is None else where
    return at.run()


def reload(at):
    """Rerun after changing the database behind the app's back (skips its 5 s cache)."""
    st.cache_data.clear()
    return at.run()
