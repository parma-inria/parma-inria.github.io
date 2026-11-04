"""Verify fixed Paris-time seminar reminders independently of live site data."""

import copy
import json
import re
import unittest
from datetime import date, timedelta
from unittest.mock import Mock

from test_calendar_feeds import (
    FIRST_REVISION, NEXT_REVISION, empty_state, event_components, seminar_fixture,
    state_bytes, unfold, update_calendar,
)


def reminder_fixture(from_date="2026-11-04"):
    seminar = seminar_fixture()
    seminar["calendar"]["reminders"] = {
        "friday_time": "09:00", "event_day_time": "07:00", "from_date": from_date,
    }
    return seminar


def alarm_components(payload):
    return [
        dict(line.split(":", 1) for line in body.split("\r\n"))
        for body in re.findall(r"BEGIN:VALARM\r\n(.*?)\r\nEND:VALARM", unfold(payload), re.DOTALL)
    ]


class CalendarReminderTests(unittest.TestCase):
    def setUp(self):
        self.seminar = reminder_fixture()
        self.state = update_calendar.update_state(self.seminar, empty_state(), now=FIRST_REVISION)

    def feed(self, state=None, identifiers=None):
        state = self.state if state is None else state
        return update_calendar.render_feed(
            state, list(state["events"]) if identifiers is None else identifiers, "Fixture seminar",
        )

    def payload_for(self, day, all_day=False, from_date="1997-01-01"):
        seminar = reminder_fixture(from_date)
        session = seminar["sessions"][1]
        session.update(date=day, all_day=all_day)
        return update_calendar.event_payload(seminar, session)

    def test_paris_utc_converts_each_reminder_in_its_own_dst_period(self):
        cases = (
            ("2027-03-26", "09:00", "20270326T080000Z"),
            ("2027-03-29", "07:00", "20270329T050000Z"),
            ("2026-10-23", "09:00", "20261023T070000Z"),
            ("2026-10-26", "07:00", "20261026T060000Z"),
            # At these morning times, the transition Sunday already uses the new offset.
            ("2027-03-28", "07:00", "20270328T050000Z"),
            ("2026-10-25", "07:00", "20261025T060000Z"),
        )
        for day, clock, expected in cases:
            with self.subTest(day=day, clock=clock):
                self.assertEqual(update_calendar.paris_utc(date.fromisoformat(day), clock), expected)

    def test_custom_reminders_reject_nonexistent_or_ambiguous_transition_hours(self):
        for day in ("2027-03-28", "2026-10-25"):
            with self.subTest(day=day), self.assertRaises(ValueError):
                update_calendar.paris_utc(date.fromisoformat(day), "02:30")

    def test_reminder_pairs_cross_the_spring_and_autumn_clock_changes(self):
        cases = (
            ("2027-03-29", ["20270326T080000Z", "20270329T050000Z"]),
            ("2026-10-26", ["20261023T070000Z", "20261026T060000Z"]),
            ("2026-11-16", ["20261113T080000Z", "20261116T060000Z"]),
            ("2027-06-21", ["20270618T070000Z", "20270621T050000Z"]),
        )
        for day, expected in cases:
            with self.subTest(day=day):
                self.assertEqual(self.payload_for(day)["reminders"], expected)

    def test_previous_friday_is_strictly_earlier_even_for_friday_and_new_year(self):
        cases = (
            ("2026-11-06", "20261030T080000Z", "20261106T060000Z"),
            ("2026-11-07", "20261106T080000Z", "20261107T060000Z"),
            ("2026-11-08", "20261106T080000Z", "20261108T060000Z"),
            ("2026-11-09", "20261106T080000Z", "20261109T060000Z"),
            ("2027-01-01", "20261225T080000Z", "20270101T060000Z"),
        )
        for day, friday, morning in cases:
            with self.subTest(day=day):
                self.assertEqual(self.payload_for(day)["reminders"], [friday, morning])

    def test_all_day_events_have_the_same_local_morning_reminders(self):
        for day in ("2027-03-29", "2026-10-26"):
            with self.subTest(day=day):
                self.assertEqual(self.payload_for(day, all_day=True)["reminders"],
                                 self.payload_for(day, all_day=False)["reminders"])

    def test_from_date_is_inclusive_and_does_not_move_with_build_time(self):
        self.assertNotIn("reminders", self.payload_for("2026-11-03", from_date="2026-11-04"))
        self.assertEqual(self.payload_for("2026-11-04", from_date="2026-11-04")["reminders"],
                         ["20261030T080000Z", "20261104T060000Z"])
        # All reminders are now in the past, but the saved calendar is unchanged.
        much_later = update_calendar.update_state(
            self.seminar, self.state, now=FIRST_REVISION + timedelta(days=2000),
        )
        self.assertEqual(state_bytes(much_later), state_bytes(self.state))
        self.assertEqual(self.feed(much_later), self.feed())

    def test_absent_policy_keeps_legacy_calendar_without_alarms(self):
        for explicitly_disabled in (False, True):
            with self.subTest(explicit_null=explicitly_disabled):
                seminar = seminar_fixture()
                if explicitly_disabled:
                    seminar["calendar"]["reminders"] = None
                state = update_calendar.update_state(seminar, empty_state(), now=FIRST_REVISION)
                for event in state["events"].values():
                    self.assertNotIn("reminders", event["payload"])
                self.assertEqual(alarm_components(self.feed(state)), [])

    def test_reminder_configuration_rejects_wrong_shapes_times_and_dates(self):
        for invalid in (False, "09:00", [], 9):
            changed = copy.deepcopy(self.seminar)
            changed["calendar"]["reminders"] = invalid
            with self.subTest(reminders=invalid), self.assertRaises(ValueError):
                update_calendar.validate_calendar(changed)
        for field in ("friday_time", "event_day_time"):
            for invalid in (None, 9, True, "9:00", "24:00", "09:60", "07:00:00"):
                changed = copy.deepcopy(self.seminar)
                changed["calendar"]["reminders"][field] = invalid
                with self.subTest(field=field, value=invalid), self.assertRaises(ValueError):
                    update_calendar.validate_calendar(changed)
        for missing in ("friday_time", "event_day_time", "from_date"):
            changed = copy.deepcopy(self.seminar)
            del changed["calendar"]["reminders"][missing]
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                update_calendar.validate_calendar(changed)
        for invalid in (None, 20261104, "yesterday", "2026-02-30", "2026-13-01"):
            changed = copy.deepcopy(self.seminar)
            changed["calendar"]["reminders"]["from_date"] = invalid
            with self.subTest(from_date=invalid), self.assertRaises(ValueError):
                update_calendar.validate_calendar(changed)

    def test_rendered_alarms_are_independent_display_components_with_utc_triggers(self):
        alarms = alarm_components(self.feed(identifiers=["session-beta"]))
        self.assertEqual(len(alarms), 2)
        self.assertEqual([alarm["TRIGGER;VALUE=DATE-TIME"] for alarm in alarms],
                         ["20261113T080000Z", "20261116T060000Z"])
        for alarm in alarms:
            self.assertEqual(alarm["ACTION"], "DISPLAY")
            self.assertTrue(alarm["DESCRIPTION"].strip())
            self.assertNotIn("REPEAT", alarm)
            self.assertNotIn("DURATION", alarm)
            self.assertFalse(any("TZID" in key or "RELATED" in key for key in alarm))
        self.assertEqual(len(alarm_components(self.feed())), 4)
        # A nested alarm description must never replace the event's own description.
        event = event_components(self.feed(identifiers=["session-beta"]))[0]
        self.assertIn("Original talk title", event["DESCRIPTION"])

    def test_alarm_descriptions_are_escaped_and_cannot_inject_components(self):
        changed = copy.deepcopy(self.seminar)
        changed["calendar"]["name"] = "Research, transport; \\ proof\r\nX-INJECTED:yes"
        revised = update_calendar.update_state(changed, self.state, now=NEXT_REVISION)
        payload = self.feed(revised, ["session-beta"])
        document = unfold(payload)
        self.assertEqual(document.split("\r\n").count("BEGIN:VALARM"), 2)
        self.assertFalse(any(line.startswith("X-INJECTED:") for line in document.split("\r\n")))
        for alarm in alarm_components(payload):
            description = alarm["DESCRIPTION"]
            self.assertTrue(description.strip())
            index = 0
            while index < len(description):
                character = description[index]
                if character == "\\":
                    index += 1
                    self.assertLess(index, len(description))
                    self.assertIn(description[index], "nN,;\\")
                else:
                    self.assertNotIn(character, ",;\r\n")
                index += 1

    def test_reschedule_updates_alarms_and_revision_without_changing_subscription(self):
        changed = copy.deepcopy(self.seminar)
        changed["sessions"][1]["date"] = "2027-03-29"
        before_url = update_calendar.feed_url(self.seminar["sessions"][1])
        before_uid = event_components(self.feed(identifiers=["session-beta"]))[0]["UID"]
        revised = update_calendar.update_state(changed, self.state, now=NEXT_REVISION)
        after = event_components(self.feed(revised, ["session-beta"]))[0]
        self.assertEqual(after["UID"], before_uid)
        self.assertEqual(update_calendar.feed_url(changed["sessions"][1]), before_url)
        self.assertEqual(after["SEQUENCE"], "1")
        self.assertEqual(revised["events"]["session-beta"]["payload"]["reminders"],
                         ["20270326T080000Z", "20270329T050000Z"])
        for identifier in ("session-alpha", "session-gamma"):
            self.assertEqual(revised["events"][identifier], self.state["events"][identifier])

    def test_editing_event_clock_times_does_not_shift_the_requested_alarms(self):
        changed = copy.deepcopy(self.seminar)
        changed["sessions"][1].update(start_time="08:30", end_time="11:45")
        revised = update_calendar.update_state(changed, self.state, now=NEXT_REVISION)
        self.assertEqual(revised["events"]["session-beta"]["payload"]["reminders"],
                         self.state["events"]["session-beta"]["payload"]["reminders"])
        self.assertEqual(revised["events"]["session-beta"]["sequence"], 1)

    def test_policy_change_only_revises_events_eligible_for_reminders(self):
        changed = copy.deepcopy(self.seminar)
        changed["calendar"]["reminders"]["friday_time"] = "08:00"
        revised = update_calendar.update_state(changed, self.state, now=NEXT_REVISION)
        self.assertEqual(revised["events"]["session-alpha"], self.state["events"]["session-alpha"])
        for identifier in ("session-beta", "session-gamma"):
            self.assertEqual(revised["events"][identifier]["sequence"], 1)
            old_alarms = self.state["events"][identifier]["payload"]["reminders"]
            new_alarms = revised["events"][identifier]["payload"]["reminders"]
            self.assertNotEqual(new_alarms[0], old_alarms[0])
            self.assertEqual(new_alarms[1], old_alarms[1])

    def test_old_state_migrates_once_without_revising_archive_events(self):
        legacy = update_calendar.update_state(seminar_fixture(), empty_state(), now=FIRST_REVISION)
        self.assertTrue(all("reminders" not in event["payload"] for event in legacy["events"].values()))
        saved = Mock()
        saved.exists.return_value = True
        saved.read_text.return_value = json.dumps(legacy)
        self.assertEqual(update_calendar.read_state(saved), legacy)
        migrated = update_calendar.update_state(self.seminar, legacy, now=NEXT_REVISION)
        self.assertEqual(migrated["events"]["session-alpha"], legacy["events"]["session-alpha"])
        self.assertEqual(migrated["events"]["session-beta"]["sequence"], 1)
        self.assertEqual(migrated["events"]["session-gamma"]["sequence"], 1)
        again = update_calendar.update_state(self.seminar, migrated, now=NEXT_REVISION + timedelta(days=1))
        self.assertEqual(state_bytes(again), state_bytes(migrated))
        self.assertEqual(self.feed(again), self.feed(migrated))

    def test_cancelled_and_removed_events_never_render_alarms(self):
        explicit = copy.deepcopy(self.seminar)
        explicit["sessions"][1]["cancelled"] = True
        cancelled = update_calendar.update_state(explicit, self.state, now=NEXT_REVISION)
        self.assertNotIn("reminders", cancelled["events"]["session-beta"]["payload"])
        self.assertEqual(alarm_components(self.feed(cancelled, ["session-beta"])), [])

        removed = copy.deepcopy(self.seminar)
        removed["sessions"].pop(1)
        tombstone = update_calendar.update_state(removed, self.state, now=NEXT_REVISION)
        # Even a cancellation carrying old saved triggers must remain silent.
        tombstone["events"]["session-beta"]["payload"]["reminders"] = [
            "20261113T080000Z", "20261116T060000Z",
        ]
        feed = self.feed(tombstone, ["session-beta"])
        self.assertEqual(alarm_components(feed), [])
        self.assertEqual(event_components(feed)[0]["STATUS"], "CANCELLED")


if __name__ == "__main__":
    unittest.main()
