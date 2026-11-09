"""
Manager page, at /mngr: edit the staff list and see each person's password.

- Opens only with manager_password from the app's Secrets, asked once per
  browser session. The page isn't linked anywhere (.streamlit/config.toml).
- Each person gets a password of 8 random letters and digits when their name
  is added, kept for as long as the name stays on the list. Nothing checks
  these passwords yet; they're for a future login to the parking page.
"""

import hmac
import secrets
import string

import streamlit as st

from store import load_staff, save_staff

PASSWORD_CHARS = string.ascii_letters + string.digits
PASSWORD_LENGTH = 8


def new_password() -> str:
    return "".join(secrets.choice(PASSWORD_CHARS) for _ in range(PASSWORD_LENGTH))


def manager_password() -> str | None:
    try:
        return st.secrets.get("manager_password")
    except Exception:                       # no Secrets at all
        return None


st.set_page_config(page_title="Parking manager", page_icon="🅿️", layout="centered")
st.title("🅿️ Parking manager")

expected = manager_password()
if not expected:
    st.error("This page is locked. Set manager_password in the app's Secrets to use it.")
    st.stop()

if not st.session_state.get("manager"):
    with st.form("login"):
        entered = st.text_input("Manager password", type="password")
        if st.form_submit_button("Open"):
            if hmac.compare_digest(entered.encode(), str(expected).encode()):
                st.session_state.manager = True
                st.rerun()
            st.error("Wrong password.")
    st.stop()

try:
    staff = load_staff()
except Exception:
    st.error("Can't load the staff list. Check that supabase_employees.sql was run in Supabase.")
    st.stop()


def save():
    # Runs before the page redraws, so the text box can show the cleaned-up list.
    text = st.session_state.staff_text
    names = list(dict.fromkeys(line.strip() for line in text.splitlines() if line.strip()))
    kept = {p["name"]: p["password"] for p in staff}
    try:
        save_staff([{"name": n, "password": kept.get(n) or new_password()} for n in names])
    except Exception:
        st.session_state.mngr_msg = ("error", "Couldn't save. Try again in a moment.")
        return
    st.session_state.staff_text = "\n".join(names)
    st.session_state.mngr_msg = ("success", f"Saved. {len(names)} people on the list.")


if "staff_text" not in st.session_state:
    st.session_state.staff_text = "\n".join(p["name"] for p in staff)

with st.form("staff"):
    st.text_area("Staff, one name per line", key="staff_text", height=260)
    st.form_submit_button("Save", type="primary", on_click=save)

msg = st.session_state.pop("mngr_msg", None)
if msg:
    getattr(st, msg[0])(msg[1])

st.subheader("Passwords")
st.caption("Not used yet. Later, each person will need theirs to open the parking page.")
st.dataframe([{"Name": p["name"], "Password": p["password"]} for p in staff],
             hide_index=True, width="stretch")
