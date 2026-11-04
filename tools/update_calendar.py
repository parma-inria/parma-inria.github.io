"""Build updating iCalendar subscriptions from the single seminar JSON source.

The generated state records stable event revisions and cancelled sessions. It is
saved by GitHub like the publication snapshot; editors only change seminar.json.
No network, external calendar account or Python package is required.
"""

import argparse
import copy
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "content/seminar.json"
STATE = ROOT / "content/calendar-state.json"
PUBLIC_URL = "https://parma-inria.github.io/"
FEED_PATH = "calendar/gdt-ot-pde-ml.ics"
SEMINAR_URL = PUBLIC_URL + "gdt-ot-pde-ml/"
DEFAULTS = {
    "name": "GdT OT-PDE-ML — ParMA",
    "timezone": "Europe/Paris",
    "start_time": "10:00",
    "end_time": "12:00",
}
ID_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
TIME_PATTERN = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")

# Self-contained Paris daylight-saving rules, also usable on Windows without
# the optional tzdata package. All published seminar dates are after 1996.
PARIS_TIMEZONE = (
    "BEGIN:VTIMEZONE", "TZID:Europe/Paris", "X-LIC-LOCATION:Europe/Paris",
    "BEGIN:DAYLIGHT", "DTSTART:19960331T020000", "TZOFFSETFROM:+0100",
    "TZOFFSETTO:+0200", "TZNAME:CEST",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU", "END:DAYLIGHT",
    "BEGIN:STANDARD", "DTSTART:19961027T030000", "TZOFFSETFROM:+0200",
    "TZOFFSETTO:+0100", "TZNAME:CET",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU", "END:STANDARD",
    "END:VTIMEZONE",
)


def session_id(session):
    """The date-based fallback supports older fixtures, not published sessions."""
    return session.get("calendar_id", "gdt-" + session["date"])


def feed_url(session=None):
    path = FEED_PATH if session is None else "calendar/sessions/" + session_id(session) + ".ics"
    return PUBLIC_URL + path


def settings(seminar):
    values = {**DEFAULTS, **seminar.get("calendar", {})}
    if not isinstance(values["name"], str) or not values["name"].strip():
        raise ValueError("seminar.calendar.name must be nonempty text.")
    if values["timezone"] != "Europe/Paris":
        raise ValueError("The seminar calendar timezone must be Europe/Paris.")
    return values


def session_times(session, config):
    start = session.get("start_time", config["start_time"])
    end = session.get("end_time", config["end_time"])
    if not all(isinstance(value, str) and TIME_PATTERN.fullmatch(value) for value in (start, end)):
        raise ValueError("Calendar start_time and end_time must use HH:MM.")
    if end <= start:
        raise ValueError("Calendar end_time must be later than start_time on the same day.")
    return start, end


def validate_calendar(seminar):
    if "calendar" in seminar and not isinstance(seminar["calendar"], dict):
        raise ValueError("seminar.calendar must be an object.")
    config = settings(seminar)
    session_times({}, config)
    seen = set()
    for session in seminar["sessions"]:
        identifier = session_id(session)
        if ("calendar" in seminar and "calendar_id" not in session):
            raise ValueError("Each session needs a unique calendar_id; keep it unchanged when rescheduling.")
        if not isinstance(identifier, str) or not ID_PATTERN.fullmatch(identifier) or len(identifier) > 100:
            raise ValueError("calendar_id must contain lowercase words or numbers separated by hyphens.")
        if identifier in seen:
            raise ValueError("Duplicate calendar_id: " + identifier)
        seen.add(identifier)
        day = date.fromisoformat(session["date"])
        if day.year < 1997:
            raise ValueError("Calendar dates must be after 1996.")
        session_times(session, config)
        for flag in ("cancelled", "all_day"):
            if type(session.get(flag, False)) is not bool:
                raise ValueError("Session " + flag + " must be true or false.")


def event_payload(seminar, session):
    """Use original scientific titles and prose, independently of page language."""
    config = settings(seminar)
    start, end = session_times(session, config)
    venue = seminar["venue"]
    room = session["room"] or venue["room"]
    location = ", ".join(part for part in (
        venue["name"], "Building " + venue["building"] if venue["building"] else "",
        "Room " + room if room else "", "Orsay, France",
    ) if part)
    paragraphs = [config["name"]]
    if session["talks"]:
        for talk in session["talks"]:
            heading = " — ".join(part for part in (talk["time"], talk["speaker"]) if part)
            paragraphs.append("\n".join(part for part in (
                heading, talk["title"], "\n\n".join(talk["abstract"]),
            ) if part))
    else:
        paragraphs.append("Programme to be announced.")
    paragraphs.append(SEMINAR_URL)
    return {
        "date": session["date"], "start_time": start, "end_time": end,
        "summary": config["name"], "description": "\n\n".join(paragraphs),
        "location": location, "url": SEMINAR_URL,
        "cancelled": session.get("cancelled", False),
        "all_day": session.get("all_day", False),
    }


def read_state(path=STATE):
    if not path.exists():
        return {"schema_version": 1, "events": {}}
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("schema_version") != 1 or not isinstance(state.get("events"), dict):
        raise ValueError("Invalid generated calendar-state.json.")
    for identifier, event in state["events"].items():
        if not ID_PATTERN.fullmatch(identifier):
            raise ValueError("Invalid saved calendar ID.")
        if type(event.get("sequence")) is not int or not 0 <= event["sequence"] < 2147483647:
            raise ValueError("Invalid saved event sequence.")
        datetime.strptime(event["modified"], "%Y%m%dT%H%M%SZ")
        payload = event["payload"]
        if not isinstance(payload, dict) or any(not isinstance(payload.get(key), str) for key in (
            "date", "start_time", "end_time", "summary", "description", "location", "url",
        )) or any(type(payload.get(flag)) is not bool for flag in ("cancelled", "all_day")):
            raise ValueError("Invalid saved calendar event.")
        date.fromisoformat(payload["date"])
        session_times(payload, DEFAULTS)
    return state


def update_state(seminar, previous, now=None):
    """Only changed event content advances its revision; removed IDs stay online."""
    validate_calendar(seminar)
    result = copy.deepcopy(previous)
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("Calendar revision time must include a timezone.")
    modified = instant.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    desired = {session_id(session): event_payload(seminar, session) for session in seminar["sessions"]}
    for identifier, event in previous["events"].items():
        if identifier not in desired:
            desired[identifier] = {**event["payload"], "cancelled": True}
    for identifier, payload in desired.items():
        old = previous["events"].get(identifier)
        if old and old["payload"] == payload:
            continue
        result["events"][identifier] = {
            "sequence": old["sequence"] + 1 if old else 0,
            "modified": modified, "payload": payload,
        }
    return result


def escape_text(value):
    """RFC 5545 TEXT escaping; newlines cannot inject iCalendar properties."""
    return value.replace("\\", "\\\\").replace("\r\n", "\n").replace("\r", "\n").replace(
        "\n", "\\n",
    ).replace(";", "\\;").replace(",", "\\,")


def fold_line(value):
    """Fold at 75 UTF-8 octets, keeping each Unicode character intact."""
    lines, current, size = [], "", 0
    for character in value:
        length = len(character.encode("utf-8"))
        if size + length > 75:
            lines.append(current)
            current, size = " ", 1
        current += character
        size += length
    lines.append(current)
    return "\r\n".join(lines)


def render_feed(state, identifiers, name):
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ParMA Inria//Seminar Calendar//EN",
        "CALSCALE:GREGORIAN", "NAME:" + escape_text(name),
        "X-WR-CALNAME:" + escape_text(name), "X-WR-TIMEZONE:Europe/Paris",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H", "X-PUBLISHED-TTL:PT1H",
        *PARIS_TIMEZONE,
    ]
    for identifier in sorted(identifiers, key=lambda key: (state["events"][key]["payload"]["date"], key)):
        event = state["events"][identifier]
        payload = event["payload"]
        day = payload["date"].replace("-", "")
        if payload["all_day"]:
            next_day = (date.fromisoformat(payload["date"]) + timedelta(days=1)).strftime("%Y%m%d")
            times = ("DTSTART;VALUE=DATE:" + day, "DTEND;VALUE=DATE:" + next_day)
        else:
            times = (
                "DTSTART;TZID=Europe/Paris:" + day + "T" + payload["start_time"].replace(":", "") + "00",
                "DTEND;TZID=Europe/Paris:" + day + "T" + payload["end_time"].replace(":", "") + "00",
            )
        lines.extend((
            "BEGIN:VEVENT", "UID:" + identifier + "@parma-inria.github.io",
            "DTSTAMP:" + event["modified"], "LAST-MODIFIED:" + event["modified"],
            "SEQUENCE:" + str(event["sequence"]),
            *times,
            "STATUS:" + ("CANCELLED" if payload["cancelled"] else "CONFIRMED"),
            "SUMMARY:" + escape_text(payload["summary"]),
            "DESCRIPTION:" + escape_text(payload["description"]),
            "LOCATION:" + escape_text(payload["location"]),
            "URL:" + payload["url"], "TRANSP:OPAQUE", "END:VEVENT",
        ))
    lines.append("END:VCALENDAR")
    return ("\r\n".join(fold_line(line) for line in lines) + "\r\n").encode("utf-8")


def write_feeds(output, seminar, state):
    paths = [(FEED_PATH, list(state["events"]), settings(seminar)["name"])]
    for identifier, event in state["events"].items():
        paths.append((
            "calendar/sessions/" + identifier + ".ics", [identifier],
            settings(seminar)["name"] + " — " + event["payload"]["date"],
        ))
    for relative, identifiers, name in paths:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(render_feed(state, identifiers, name))


def save_to_git():
    """Commit the exact generated state artifact, without refreshing it again."""
    git = ["git", "-c", "safe.directory=" + ROOT.as_posix()]
    path = "content/calendar-state.json"
    subprocess.run(git + ["add", "--", path], cwd=ROOT, check=True)
    difference = subprocess.run(git + ["diff", "--cached", "--quiet", "--", path], cwd=ROOT)
    if difference.returncode == 0:
        print("Calendar revisions unchanged; no commit needed.")
        return
    if difference.returncode != 1:
        raise ValueError("Cannot inspect staged calendar state.")
    subprocess.run(git + [
        "-c", "user.name=github-actions[bot]", "-c",
        "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit", "--only", "-m", "Update seminar calendar revisions", "--", path,
    ], cwd=ROOT, check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save-to-git", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.save_to_git:
            save_to_git()
        else:
            seminar = json.loads(SOURCE.read_text(encoding="utf-8"))
            state = update_state(seminar, read_state())
            payload = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            if not STATE.exists() or STATE.read_text(encoding="utf-8") != payload:
                temporary = STATE.with_suffix(".json.tmp")
                temporary.write_text(payload, encoding="utf-8")
                temporary.replace(STATE)
            print("Calendar revisions ready:", len(state["events"]), "sessions.")
        return 0
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        print("Calendar update failed:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
