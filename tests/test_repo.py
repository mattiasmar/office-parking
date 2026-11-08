"""Story 8 (no secrets in the public code), story 9 (the morning check) and
setup safeguards, checked by reading the repo's files."""

import re
import subprocess

import yaml

from support import APP_FILE, ROOT, WORKFLOW_FILE

APP = APP_FILE.read_text()


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [ROOT / name for name in out.stdout.splitlines()]


def workflow():
    wf = yaml.safe_load(WORKFLOW_FILE.read_text())
    wf["on"] = wf.pop(True, wf.get("on"))           # YAML 1.1 reads the key `on` as True
    return wf


def wake_step(name):
    return next(s for s in workflow()["jobs"]["wake"]["steps"] if s.get("name") == name)


def cron_hours(cron):
    minute, hour, *days = cron.split()
    assert days == ["*", "*", "*"], f"{cron!r} doesn't run every day"
    if hour == "*":
        return list(range(24))
    if hour.startswith("*/"):
        return list(range(0, 24, int(hour[2:])))
    return [int(h) for h in hour.split(",")]


# ------------------------------------------------- 8. keep parking data private ---
SECRET_PATTERNS = {
    "Supabase JWT key": r"eyJ[\w-]{10,}\.[\w-]{10,}\.",
    "Supabase API key": r"sb_(secret|publishable)_[\w-]{10,}",
    "database password": r"postgres(ql)?://[^\s:/]+:[^\s@]+@",
}


def test_no_key_or_password_in_the_public_code():
    for path in tracked_files():
        text = path.read_text(errors="ignore")
        for what, pattern in SECRET_PATTERNS.items():
            assert not re.search(pattern, text), f"{path.relative_to(ROOT)} contains a {what}"


def test_secrets_file_is_not_committed():
    assert not [p for p in tracked_files() if p.name == "secrets.toml"]


# ------------------------------------------------------ 9. ready every morning ---
def test_app_is_checked_at_least_every_12_hours():
    hours = sorted(h for entry in workflow()["on"]["schedule"] for h in cron_hours(entry["cron"]))
    gaps = [(b - a) % 24 or 24 for a, b in zip(hours, hours[1:] + hours[:1])]
    assert max(gaps) <= 12, f"checks at {hours} UTC leave a {max(gaps)} h gap"


def test_sleeping_app_is_woken():
    assert 'get_by_role("button", name="Yes, get this app back up")' in wake_step(
        "Open the app (and wake it if asleep)")["run"]


def test_morning_check_recognises_the_app_title():
    title = re.search(r'st\.title\("([^"]+)"\)', APP).group(1)
    waited_for = re.search(r'get_by_text\("([^"]+)"\)', wake_step("Open the app (and wake it if asleep)")["run"])
    assert waited_for.group(1) in title


def test_failures_tell_the_admin_why_with_a_screenshot():
    assert 'test "$code" = "200"' in wake_step("Ping Supabase")["run"]
    assert 'page.screenshot(path="wake-failure.png"' in wake_step("Open the app (and wake it if asleep)")["run"]
    upload = wake_step("Save screenshot if something went wrong")
    assert upload["if"] == "failure()" and upload["with"]["path"] == "wake-failure.png"


def test_morning_check_never_takes_a_spot():
    assert "user=" not in workflow()["env"]["APP_URL"]       # opened without a name: no buttons
    wake = yaml.safe_dump(workflow()["jobs"]["wake"])
    for forbidden in ("rpc/", "I've parked", "Undo", "-X ", "--request", "--data", " -d "):
        assert forbidden not in wake


# --------------------------------------------------------- setup safeguards ---
def test_supabase_ping_reads_the_secrets_it_names():
    ping = wake_step("Ping Supabase")
    assert all(value == f"${{{{ secrets.{name} }}}}" for name, value in ping["env"].items())
    assert set(re.findall(r"\$(SUPABASE_\w+)", ping["run"])) <= ping["env"].keys()


def test_setup_help_names_every_secret_the_app_needs():
    setup_help = re.search(r'SETUP_HELP = \((.*?)\)\n', APP, re.S).group(1)
    for key in re.findall(r'st\.secrets\["(\w+)"\]', APP):
        assert key in setup_help


def test_test_tools_stay_out_of_the_app_install_list():
    lines = (ROOT / "requirements.txt").read_text().splitlines()
    packages = {re.split(r"[<>=~!\[;\s]", line.strip())[0].lower() for line in lines if line.strip()}
    assert not packages & {"pytest", "pyyaml"}


def test_tests_run_on_every_change_and_on_schedule():
    wf = workflow()
    assert {"pull_request", "push", "schedule"} <= wf["on"].keys()
    runs = [s.get("run", "") for s in wf["jobs"]["test"]["steps"]]
    assert "pytest tests" in runs and "node --test tests/geolocation.test.js" in runs
    assert "schedule" in wf["jobs"]["wake"]["if"] and "pull_request" not in wf["jobs"]["wake"]["if"]
