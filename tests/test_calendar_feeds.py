"""Exercise calendar subscriptions with independent, editable seminar fixtures.

No live website, committed snapshot, network connection, or timezone package is
needed. Generated files are captured in memory so the source tree stays untouched.
"""

import calendar
import copy
import json
import re
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check
import update_calendar


FIRST_REVISION = datetime(2026, 11, 4, 12, 30, tzinfo=timezone.utc)
NEXT_REVISION = FIRST_REVISION + timedelta(days=1)


def seminar_fixture():
    """Use opaque IDs and deliberately unordered dates spanning several years."""
    return {
        "calendar": {
            "name": "Fixture seminar",
            "timezone": "Europe/Paris",
            "start_time": "10:00",
            "end_time": "12:00",
        },
        "venue": {"name": "Research institute", "building": "307", "room": "A"},
        "sessions": [
            {"calendar_id": "session-gamma", "date": "2027-06-21", "room": "C", "talks": []},
            {
                "calendar_id": "session-beta", "date": "2026-11-16", "room": "B",
                "talks": [{
                    "time": "10:00", "speaker": "Example Speaker", "title": "Original talk title",
                    "abstract": ["An original abstract."],
                }],
            },
            {"calendar_id": "session-alpha", "date": "2025-01-20", "room": "A", "talks": []},
        ],
    }


def empty_state():
    return {"schema_version": 1, "events": {}}


def state_bytes(state):
    return (json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def unfold(payload):
    """Decode physical lines independently, then remove RFC continuation spaces."""
    # Decoding each line catches an incorrectly split multibyte UTF-8 character.
    for line in payload.split(b"\r\n"):
        line.decode("utf-8")
    return payload.decode("utf-8").replace("\r\n ", "").replace("\r\n\t", "")


def event_components(payload):
    events = []
    for body in re.findall(r"BEGIN:VEVENT\r\n(.*?)\r\nEND:VEVENT", unfold(payload), re.DOTALL):
        properties, nesting = {}, 0
        for line in body.split("\r\n"):
            if line.startswith("BEGIN:"):
                nesting += 1
            elif line.startswith("END:"):
                nesting -= 1
            elif nesting == 0:
                name, value = line.split(":", 1)
                properties[name] = value
        events.append(properties)
    return events


def decode_text(value):
    """Small independent reader for the TEXT escapes used by these fixtures."""
    return re.sub(r"\\([nN,;\\])", lambda match: "\n" if match[1] in "nN" else match[1], value)


class MemoryOutput:
    """Capture write_feeds' output paths and bytes without writing any files."""

    def __init__(self):
        self.files = {}

    def __truediv__(self, relative):
        return MemoryTarget(self.files, relative)


class MemoryTarget:
    def __init__(self, files, relative):
        self.files = files
        self.relative = relative
        self.parent = self

    def mkdir(self, **kwargs):
        pass

    def write_bytes(self, payload):
        self.files[self.relative] = payload


class CalendarFeedTests(unittest.TestCase):
    def setUp(self):
        self.seminar = seminar_fixture()
        self.state = update_calendar.update_state(self.seminar, empty_state(), now=FIRST_REVISION)

    def feed(self, state=None, identifiers=None):
        state = self.state if state is None else state
        return update_calendar.render_feed(
            state, list(state["events"]) if identifiers is None else identifiers, "Fixture seminar",
        )

    def test_rescheduling_keeps_uid_and_individual_subscription_url(self):
        original = self.seminar["sessions"][1]
        before_url = update_calendar.feed_url(original)
        before_event = event_components(self.feed(identifiers=["session-beta"]))[0]
        changed = copy.deepcopy(self.seminar)
        changed["sessions"][1]["date"] = "2027-02-22"
        revised = update_calendar.update_state(changed, self.state, now=NEXT_REVISION)
        after_event = event_components(self.feed(revised, ["session-beta"]))[0]

        self.assertEqual(before_event["UID"], "session-beta@parma-inria.github.io")
        self.assertEqual(after_event["UID"], before_event["UID"])
        self.assertEqual(update_calendar.feed_url(changed["sessions"][1]), before_url)
        self.assertTrue(before_url.endswith("/calendar/sessions/session-beta.ics"))
        self.assertEqual(after_event["DTSTART;TZID=Europe/Paris"], "20270222T100000")
        self.assertEqual(revised["events"]["session-beta"]["sequence"], 1)

    def test_unchanged_build_preserves_state_bytes_timestamps_and_feed_bytes(self):
        before = state_bytes(self.state)
        later = update_calendar.update_state(self.seminar, self.state, now=NEXT_REVISION)
        self.assertEqual(state_bytes(later), before)
        self.assertEqual(self.feed(later), self.feed())
        for event in later["events"].values():
            self.assertEqual(event["sequence"], 0)
            self.assertEqual(event["modified"], "20261104T123000Z")
        # Revision computation must not mutate its inputs.
        self.assertEqual(state_bytes(self.state), before)
        self.assertNotIn("cancelled", self.seminar["sessions"][1])

    def test_only_changed_event_advances_for_title_room_and_time_edits(self):
        for field in ("title", "room", "session_time", "talk_time"):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.seminar)
                session = changed["sessions"][1]
                if field == "title":
                    session["talks"][0]["title"] = "Updated scientific title"
                elif field == "room":
                    session["room"] = "Another room"
                elif field == "session_time":
                    session["start_time"], session["end_time"] = "09:30", "11:30"
                else:
                    session["talks"][0]["time"] = "10:15"
                revised = update_calendar.update_state(changed, self.state, now=NEXT_REVISION)
                self.assertEqual(revised["events"]["session-beta"]["sequence"], 1)
                self.assertEqual(revised["events"]["session-beta"]["modified"], "20261105T123000Z")
                for identifier in ("session-alpha", "session-gamma"):
                    self.assertEqual(revised["events"][identifier], self.state["events"][identifier])

    def test_removal_retains_cancelled_event_and_its_original_feed(self):
        changed = copy.deepcopy(self.seminar)
        changed["sessions"].pop(1)
        revised = update_calendar.update_state(changed, self.state, now=NEXT_REVISION)
        removed = revised["events"]["session-beta"]
        self.assertTrue(removed["payload"]["cancelled"])
        self.assertEqual(removed["sequence"], 1)
        self.assertEqual(removed["payload"]["date"], "2026-11-16")
        output = MemoryOutput()
        update_calendar.write_feeds(output, changed, revised)
        path = "calendar/sessions/session-beta.ics"
        self.assertIn(path, output.files)
        event = event_components(output.files[path])[0]
        self.assertEqual(event["STATUS"], "CANCELLED")
        self.assertEqual(event["UID"], "session-beta@parma-inria.github.io")
        self.assertEqual(len(event_components(output.files["calendar/gdt-ot-pde-ml.ics"])), 3)
        repeated = update_calendar.update_state(changed, revised, now=NEXT_REVISION + timedelta(days=1))
        self.assertEqual(state_bytes(repeated), state_bytes(revised))

    def test_explicit_cancellation_and_reinstatement_revise_the_same_event(self):
        changed = copy.deepcopy(self.seminar)
        changed["sessions"][1]["cancelled"] = True
        cancelled = update_calendar.update_state(changed, self.state, now=NEXT_REVISION)
        cancelled_event = event_components(self.feed(cancelled, ["session-beta"]))[0]
        self.assertEqual(cancelled_event["STATUS"], "CANCELLED")
        self.assertEqual(cancelled_event["SEQUENCE"], "1")
        changed["sessions"][1]["cancelled"] = False
        reinstated = update_calendar.update_state(changed, cancelled, now=NEXT_REVISION + timedelta(days=1))
        restored_event = event_components(self.feed(reinstated, ["session-beta"]))[0]
        self.assertEqual(restored_event["STATUS"], "CONFIRMED")
        self.assertEqual(restored_event["SEQUENCE"], "2")
        self.assertEqual(restored_event["UID"], cancelled_event["UID"])

    def test_removed_session_can_return_with_the_same_subscription(self):
        reduced = copy.deepcopy(self.seminar)
        reduced["sessions"].pop(1)
        removed = update_calendar.update_state(reduced, self.state, now=NEXT_REVISION)
        restored = update_calendar.update_state(self.seminar, removed, now=NEXT_REVISION + timedelta(days=1))
        self.assertFalse(restored["events"]["session-beta"]["payload"]["cancelled"])
        self.assertEqual(restored["events"]["session-beta"]["sequence"], 2)

    def test_session_time_overrides_defaults_in_the_generated_feed(self):
        self.seminar["calendar"].update(start_time="08:00", end_time="09:00")
        self.seminar["sessions"][1].update(start_time="13:30", end_time="15:45")
        revised = update_calendar.update_state(self.seminar, self.state, now=NEXT_REVISION)
        event = event_components(self.feed(revised, ["session-beta"]))[0]
        self.assertEqual(event["DTSTART;TZID=Europe/Paris"], "20261116T133000")
        self.assertEqual(event["DTEND;TZID=Europe/Paris"], "20261116T154500")

    def test_all_day_events_end_exclusively_on_the_next_calendar_day(self):
        for day, next_day in (("2028-02-28", "20280229"), ("2028-02-29", "20280301"),
                              ("2026-12-31", "20270101")):
            with self.subTest(date=day):
                changed = copy.deepcopy(self.seminar)
                changed["sessions"][1].update(date=day, all_day=True)
                revised = update_calendar.update_state(changed, self.state, now=NEXT_REVISION)
                event = event_components(self.feed(revised, ["session-beta"]))[0]
                self.assertEqual(event["DTSTART;VALUE=DATE"], day.replace("-", ""))
                self.assertEqual(event["DTEND;VALUE=DATE"], next_day)
                self.assertNotIn("DTSTART;TZID=Europe/Paris", event)
                self.assertNotIn("DTEND;TZID=Europe/Paris", event)
                self.assertEqual(event["UID"], "session-beta@parma-inria.github.io")

    def test_all_day_flag_requires_a_json_boolean(self):
        for invalid in ("true", "false", 1, 0, None, [], {}):
            changed = copy.deepcopy(self.seminar)
            changed["sessions"][1]["all_day"] = invalid
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                update_calendar.validate_calendar(changed)

    def test_subscription_links_skip_webpage_tab_rules_but_still_check_local_feeds(self):
        own_feed = "webcal://parma-inria.github.io/calendar/sessions/session-beta.ics"
        external_feed = "webcal://example.org/calendar.ics"
        for href in (own_feed, external_feed, "https://example.org/page", "//example.org/page"):
            with self.subTest(href=href):
                parser = check.PageLinks()
                parser.feed('<a href="' + href + '">Open</a>')
                self.assertEqual(parser.links, [href])
                self.assertEqual(parser.external_link_errors, [] if href.startswith("webcal:") else [href])
                safe = check.PageLinks()
                safe.feed('<a href="' + href + '" target="_blank" rel="noopener noreferrer">Open</a>')
                self.assertEqual(safe.external_link_errors, [])

        # Exercise local feed resolution with virtual files; no temporary site is written.
        root = Path(__file__).resolve().parent / "_not_written_calendar_output"
        page = root / "index.html"
        target = root / "calendar/sessions/session-beta.ics"
        document = '<a href="' + own_feed + '">Subscribe</a><a href="' + external_feed + '">Other</a>'
        for feed_exists in (False, True):
            with self.subTest(feed_exists=feed_exists), \
                    patch.object(Path, "rglob", autospec=True,
                                 side_effect=lambda path, pattern: [page] if pattern == "*.html" else []), \
                    patch.object(Path, "read_text", autospec=True, return_value=document), \
                    patch.object(Path, "is_dir", autospec=True, return_value=False), \
                    patch.object(Path, "is_file", autospec=True,
                                 side_effect=lambda path: path != target or feed_exists), \
                    patch("builtins.print"):
                errors = check.check_site(root)
            if feed_exists:
                self.assertEqual(errors, [])
            else:
                self.assertEqual(len(errors), 1)
                self.assertIn("collegamento locale non trovato", errors[0])
                self.assertIn(own_feed, errors[0])

    def test_invalid_default_or_session_times_are_rejected(self):
        invalid_pairs = (
            ("9:00", "12:00"), ("24:00", "12:00"), ("10:60", "12:00"),
            ("10:00", "10:00"), ("11:00", "10:00"), ("23:00", "01:00"),
            (None, "12:00"), ("10:00", 1200),
        )
        for location in ("calendar", "session"):
            for start, end in invalid_pairs:
                with self.subTest(location=location, start=start, end=end):
                    changed = copy.deepcopy(self.seminar)
                    target = changed["calendar"] if location == "calendar" else changed["sessions"][1]
                    target.update(start_time=start, end_time=end)
                    with self.assertRaises(ValueError):
                        update_calendar.validate_calendar(changed)

    def test_published_sessions_require_unique_safe_persistent_ids(self):
        missing = copy.deepcopy(self.seminar)
        del missing["sessions"][0]["calendar_id"]
        duplicate = copy.deepcopy(self.seminar)
        duplicate["sessions"][0]["calendar_id"] = duplicate["sessions"][1]["calendar_id"]
        for label, changed in (("missing", missing), ("duplicate", duplicate)):
            with self.subTest(case=label), self.assertRaises(ValueError):
                update_calendar.validate_calendar(changed)
        for identifier in ("", "Uppercase", "path/escape", "../escape", "has_underscore", "x" * 101, 42):
            changed = copy.deepcopy(self.seminar)
            changed["sessions"][0]["calendar_id"] = identifier
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                update_calendar.validate_calendar(changed)

    def test_invalid_calendar_timezone_dates_and_cancellation_types_are_rejected(self):
        edits = (
            ("timezone", "UTC"), ("date", "2026-02-30"), ("date", "1996-12-31"),
            ("cancelled", "true"), ("cancelled", 1),
        )
        for field, value in edits:
            changed = copy.deepcopy(self.seminar)
            target = changed["calendar"] if field == "timezone" else changed["sessions"][1]
            target[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                update_calendar.validate_calendar(changed)

    def test_feed_uses_crlf_and_folds_utf8_lines_without_splitting_characters(self):
        self.seminar["sessions"][1]["talks"][0]["title"] = "Équations, transport; 東京 🌍 " * 15
        revised = update_calendar.update_state(self.seminar, self.state, now=NEXT_REVISION)
        feed = self.feed(revised)
        self.assertTrue(feed.endswith(b"END:VCALENDAR\r\n"))
        remaining = feed.replace(b"\r\n", b"")
        self.assertNotIn(b"\n", remaining)
        self.assertNotIn(b"\r", remaining)
        for line in feed.split(b"\r\n"):
            self.assertLessEqual(len(line), 75)
            line.decode("utf-8")
        self.assertIn("Équations\\, transport\\; 東京 🌍", unfold(feed))
        original = "SUMMARY:" + "é東京🌍" * 40
        folded = (update_calendar.fold_line(original) + "\r\n").encode("utf-8")
        self.assertEqual(unfold(folded), original + "\r\n")

    def test_text_escaping_prevents_newline_property_or_event_injection(self):
        injected = "Scientific: result, with; delimiters \\ proof\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nX-INJECTED:yes"
        self.seminar["sessions"][1]["talks"][0]["abstract"] = [injected]
        revised = update_calendar.update_state(self.seminar, self.state, now=NEXT_REVISION)
        feed = self.feed(revised)
        document = unfold(feed)
        events = event_components(feed)
        self.assertEqual(document.split("\r\n").count("BEGIN:VEVENT"), 3)
        self.assertEqual(document.split("\r\n").count("END:VEVENT"), 3)
        self.assertFalse(any(line.startswith("X-INJECTED:") for line in document.split("\r\n")))
        target = next(event for event in events if event["UID"].startswith("session-beta@"))
        self.assertIn(injected.replace("\r\n", "\n"), decode_text(target["DESCRIPTION"]))
        self.assertEqual(update_calendar.escape_text("a:b,c;d\\e\r\nf"), "a:b\\,c\\;d\\\\e\\nf")
        self.assertEqual(target["URL"], "https://parma-inria.github.io/gdt-ot-pde-ml/")

    def test_embedded_paris_timezone_expresses_winter_and_summer_offsets(self):
        document = unfold(self.feed())
        timezone_block = re.search(r"BEGIN:VTIMEZONE\r\n(.*?)\r\nEND:VTIMEZONE", document, re.DOTALL)[1]
        self.assertIn("TZID:Europe/Paris", timezone_block)
        observances = {}
        for kind in ("DAYLIGHT", "STANDARD"):
            body = re.search(r"BEGIN:" + kind + r"\r\n(.*?)\r\nEND:" + kind, timezone_block, re.DOTALL)[1]
            observances[kind] = dict(line.split(":", 1) for line in body.split("\r\n"))
        daylight, standard = observances["DAYLIGHT"], observances["STANDARD"]
        self.assertEqual(daylight["TZOFFSETFROM"], "+0100")
        self.assertEqual(daylight["TZOFFSETTO"], "+0200")
        self.assertEqual(standard["TZOFFSETFROM"], "+0200")
        self.assertEqual(standard["TZOFFSETTO"], "+0100")
        for rule, month in ((daylight, 3), (standard, 10)):
            values = dict(part.split("=", 1) for part in rule["RRULE"].split(";"))
            self.assertEqual(values, {"FREQ": "YEARLY", "BYMONTH": str(month), "BYDAY": "-1SU"})
        self.assertTrue(daylight["DTSTART"].endswith("T020000"))
        self.assertTrue(standard["DTSTART"].endswith("T030000"))

        # Evaluate the exported last-Sunday rules independently for fixture dates.
        def last_sunday(year, month):
            last = date(year, month, calendar.monthrange(year, month)[1])
            return last - timedelta(days=(last.weekday() + 1) % 7)

        for local_day, expected_utc_hour in ((date(2026, 1, 20), 9), (date(2026, 7, 20), 8)):
            in_summer = last_sunday(local_day.year, 3) < local_day < last_sunday(local_day.year, 10)
            offset = (daylight if in_summer else standard)["TZOFFSETTO"]
            utc_hour = 10 - int(offset[:3])
            self.assertEqual(utc_hour, expected_utc_hour)
        for event in event_components(self.feed()):
            self.assertIn("DTSTART;TZID=Europe/Paris", event)
            self.assertIn("DTEND;TZID=Europe/Paris", event)

    def test_whole_feed_retains_multiple_years_and_sorts_dates(self):
        much_later = update_calendar.update_state(
            self.seminar, self.state, now=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        events = event_components(self.feed(much_later))
        self.assertEqual([event["DTSTART;TZID=Europe/Paris"][:8] for event in events],
                         ["20250120", "20261116", "20270621"])
        self.assertEqual(state_bytes(much_later), state_bytes(self.state))


if __name__ == "__main__":
    unittest.main()
