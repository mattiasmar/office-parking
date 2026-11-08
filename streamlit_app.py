"""
Office parking tracker for Streamlit Community Cloud.

- 4 spots, first come first served.
- An employee taps "I've parked"; everyone sees the spots left.
- "I've parked" only works at the office: the phone's location must be within
  100 m of HaMelakha 4, Yokneam Illit.
- A spot stays taken until the end of the day (local time) unless its owner taps "Undo".
- The board refreshes itself every few seconds, so phones stay up to date.
- Data lives in Supabase (Postgres), so it survives app restarts and sleep.
  Run supabase_setup.sql once in the Supabase SQL editor before first use.
"""

import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import streamlit as st
import streamlit.components.v1 as components

# ---------------------------------------------------------------- settings ---
TOTAL_SPOTS = 4
TIMEZONE = ZoneInfo("Asia/Jerusalem")   # the "day" resets at local midnight
REFRESH_EVERY = "10s"                   # how often the board updates itself

OFFICE = (32.66151, 35.10618)           # HaMelakha 4, Yokneam Illit (lat, lon)
OFFICE_RADIUS_M = 100                   # parking can be marked only this close to it

DEFAULT_EMPLOYEES = ["Avi", "Dana", "Eitan", "Maya", "Noa", "Yossi"]


def load_employees() -> list[str]:
    """Names come from Streamlit secrets if set, else the default list."""
    try:
        names = st.secrets.get("employees")
        if names:
            return list(names)
    except Exception:
        pass
    return DEFAULT_EMPLOYEES


EMPLOYEES = load_employees()

# ---------------------------------------------------------------- storage ---
# Talks to Supabase's REST API. The "park" database function locks the day,
# counts the cars and inserts in one step, so two people can never grab the
# last spot at the same moment.


@st.cache_resource
def get_api() -> tuple[str, requests.Session]:
    base = st.secrets["supabase_url"].rstrip("/") + "/rest/v1"
    key = st.secrets["supabase_key"]
    s = requests.Session()
    s.headers["apikey"] = key
    if not key.startswith("sb_"):               # legacy service_role JWT key
        s.headers["Authorization"] = f"Bearer {key}"
    return base, s


def _call(method: str, path: str, **kwargs):
    base, s = get_api()
    r = s.request(method, f"{base}/{path}", timeout=10, **kwargs)
    r.raise_for_status()
    return r.json() if r.content else None


def now() -> datetime:
    return datetime.now(TIMEZONE)


def today() -> str:
    return now().date().isoformat()


@st.cache_data(ttl=5, show_spinner=False)
def todays_parkings(day: str) -> list[str]:
    rows = _call("GET", "parkings", params={
        "select": "employee", "day": f"eq.{day}", "order": "parked_at",
    })
    return [r["employee"] for r in rows]


def park(name: str) -> str:
    result = _call("POST", "rpc/park", json={
        "p_employee": name, "p_day": today(), "p_spots": TOTAL_SPOTS,
    })
    todays_parkings.clear()
    return result


def undo(name: str) -> None:
    _call("DELETE", "parkings", params={
        "day": f"eq.{today()}", "employee": f"eq.{name}",
    })
    todays_parkings.clear()


# --------------------------------------------------------------- location ---
# Tapping "I've parked" asks the phone where it is (geolocation/index.html);
# the car is marked parked only if the answer is within OFFICE_RADIUS_M.

get_location = components.declare_component(
    "geolocation", path=str(Path(__file__).parent / "geolocation"))


def metres_from_office(lat: float, lon: float) -> float:
    """Great-circle (haversine) distance from OFFICE."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*OFFICE, lat, lon))
    a = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6_371_000 * math.asin(math.sqrt(a))


# --------------------------------------------------------------------- UI ---
st.set_page_config(page_title="Parking", page_icon="🅿️", layout="centered")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Overpass:wght@400;700;900&display=swap');

.lot-status   { font-family: 'Overpass', system-ui, sans-serif; margin: .25rem 0 1rem; }
.lot-status b { font-size: 3.25rem; font-weight: 900; line-height: 1; }
.lot-status span { font-size: 1.15rem; margin-left: .4rem; opacity: .8; }

.lot {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 0;
  background: #3a3d42; border-radius: 6px; padding: 14px 6px 6px;
  border-top: 6px solid #f2c230;           /* curb line */
  font-family: 'Overpass', system-ui, sans-serif;
}
.bay {
  min-height: 118px; padding: 8px 6px;
  border-left: 3px solid #f2c230; display: flex; flex-direction: column;
  justify-content: space-between; color: #fff; text-align: center;
}
.bay:last-child { border-right: 3px solid #f2c230; }
.bay .num  { font-size: .8rem; opacity: .6; }
.bay .who  { font-weight: 700; font-size: 1rem; word-break: break-word; }
.bay .when { font-size: .8rem; opacity: .7; }
.bay.free .who { color: #8fd18f; font-weight: 400; }
.bay.mine { background: #1e4e9c; }         /* road-sign blue */
</style>
""",
    unsafe_allow_html=True,
)

st.title("🅿️ Office parking")

# ---- who am I? Remembered in the URL so each phone can bookmark its own link.
if "user" not in st.session_state:
    from_url = st.query_params.get("user")
    st.session_state.user = from_url if from_url in EMPLOYEES else None


def on_pick_user():
    if st.session_state.user:
        st.query_params["user"] = st.session_state.user


st.selectbox(
    "Who are you?",
    EMPLOYEES,
    key="user",
    index=None,
    placeholder="Pick your name",
    on_change=on_pick_user,
)
if st.session_state.user:
    st.caption("Tip: bookmark this page or add it to your home screen; it remembers your name.")


# ---- button callbacks (run before the board redraws)
SETUP_HELP = ("Can't reach the parking database. Check that supabase_url and supabase_key "
              "are set in the app's Secrets and that supabase_setup.sql was run in Supabase.")


def do_park():
    try:
        result = park(st.session_state.user)
    except Exception:
        st.session_state.msg = ("error", "Couldn't save your change. Tap again in a moment.")
        return
    st.session_state.msg = {
        "ok": ("success", "You're parked. The spot is yours until midnight."),
        "already": ("info", "You already have a spot today."),
        "full": ("error", "Someone took the last spot just before you. The lot is full."),
    }[result]


def start_park():
    # The board now asks the phone where it is (park_if_at_office). A new key
    # per tap makes the phone take a fresh reading each time.
    st.session_state.tries = st.session_state.get("tries", 0) + 1
    st.session_state.locating = f"location-{st.session_state.tries}"


def park_if_at_office():
    loc = get_location(key=st.session_state.locating, default=None)
    if loc is None:
        return                  # no answer yet; it reruns the board when it comes
    st.session_state.locating = None
    if "error" in loc:
        st.session_state.msg = ("error", f"Couldn't get your location ({loc['error']}). "
                                "Allow location access for this site and tap again.")
        return
    d = metres_from_office(loc["lat"], loc["lon"])
    if d > OFFICE_RADIUS_M:
        st.session_state.msg = ("error", f"You're {d:,.0f} m from the office (±{loc['accuracy']:.0f} m). "
                                f"You can mark your car as parked only within {OFFICE_RADIUS_M} m of it.")
        return
    do_park()


def do_undo():
    try:
        undo(st.session_state.user)
    except Exception:
        st.session_state.msg = ("error", "Couldn't save your change. Tap again in a moment.")
        return
    st.session_state.msg = ("info", "Your spot is free again.")


@st.fragment(run_every=REFRESH_EVERY)
def board():
    user = st.session_state.get("user")
    if st.session_state.get("locating"):
        park_if_at_office()
    try:
        names = todays_parkings(today())
    except Exception:
        st.error(SETUP_HELP)
        return
    free = TOTAL_SPOTS - len(names)

    if free == 0:
        status = "<b>0</b><span>spots free. The lot is full.</span>"
    else:
        status = f"<b>{free}</b><span>of {TOTAL_SPOTS} spots free</span>"
    st.markdown(f'<div class="lot-status">{status}</div>', unsafe_allow_html=True)

    bays = []
    for i in range(TOTAL_SPOTS):
        if i < len(names):
            name = names[i]
            cls = "bay mine" if name == user else "bay"
            bays.append(
                f'<div class="{cls}"><div class="num">{i + 1}</div>'
                f'<div class="who">{name}</div><div class="when">&nbsp;</div></div>'
            )
        else:
            bays.append(
                f'<div class="bay free"><div class="num">{i + 1}</div>'
                f'<div class="who">Free</div><div class="when">&nbsp;</div></div>'
            )
    st.markdown(f'<div class="lot">{"".join(bays)}</div>', unsafe_allow_html=True)
    st.write("")

    if not user:
        st.info("Pick your name above to take or free a spot.")
    elif user in names:
        st.button("Undo, free my spot", on_click=do_undo,
                  width="stretch")
    elif st.session_state.get("locating"):
        st.button("Checking your location…", disabled=True, width="stretch")
    elif free > 0:
        st.button("I've parked", on_click=start_park, type="primary",
                  width="stretch")
    else:
        st.button("Lot full", disabled=True, width="stretch")

    msg = st.session_state.pop("msg", None)
    if msg:
        getattr(st, msg[0])(msg[1])

    st.caption(f"Updated {now().strftime('%H:%M:%S')}. Refreshes automatically.")


board()
