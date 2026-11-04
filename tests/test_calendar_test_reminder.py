"""Keep the temporary notification test separate from real seminar reminders."""

import copy
import json
import unittest
from datetime import timedelta
from unittest.mock import Mock

from test_calendar_feeds import FIRST_REVISION, empty_state, event_components, update_calendar
from test_calendar_reminders import alarm_components, reminder_fixture


class TemporaryCalendarReminderTests(unittest.TestCase):
    def setUp(self):
        self.seminar = reminder_fixture()
        self.seminar["calendar"]["test_reminder"] = {
            "session_id": "session-beta",
            "trigger_utc": "20261104T123500Z",
            "expires_utc": "20261104T133500Z",
        }
        self.state = update_calendar.update_state(self.seminar, empty_state(), now=FIRST_REVISION)

    def feed(self, state, identifier):
        return update_calendar.render_feed(state, [identifier], "Fixture seminar")

    def test_before_expiry_only_target_gets_an_extra_alarm_without_moving_the_event(self):
        baseline_source = copy.deepcopy(self.seminar)
        del baseline_source["calendar"]["test_reminder"]
        baseline = update_calendar.update_state(baseline_source, empty_state(), now=FIRST_REVISION)
        for identifier, expected_count in (("session-alpha", 0), ("session-beta", 3), ("session-gamma", 2)):
            with self.subTest(identifier=identifier):
                feed = self.feed(self.state, identifier)
                self.assertEqual(len(alarm_components(feed)), expected_count)
                before_event = event_components(self.feed(baseline, identifier))[0]
                after_event = event_components(feed)[0]
                self.assertEqual(after_event["UID"], before_event["UID"])
                self.assertEqual(after_event["DTSTART;TZID=Europe/Paris"], before_event["DTSTART;TZID=Europe/Paris"])
                self.assertEqual(after_event["DTEND;TZID=Europe/Paris"], before_event["DTEND;TZID=Europe/Paris"])
        payload = self.state["events"]["session-beta"]["payload"]
        self.assertEqual(payload["test_reminder"], "20261104T123500Z")
        self.assertEqual(payload["reminders"], ["20261113T080000Z", "20261116T060000Z"])
        test_alarm = next(alarm for alarm in alarm_components(self.feed(self.state, "session-beta"))
                          if alarm["TRIGGER;VALUE=DATE-TIME"] == "20261104T123500Z")
        self.assertEqual(test_alarm["ACTION"], "DISPLAY")
        self.assertEqual(test_alarm["DESCRIPTION"], "ParMA - reminder test")
        self.assertNotIn("test_reminder", self.state["events"]["session-gamma"]["payload"])

    def test_expiry_removes_only_the_test_alarm_and_preserves_regular_reminders(self):
        # The configured expiry is inclusive; one second later the test disappears.
        expiry = FIRST_REVISION + timedelta(hours=1, minutes=5)
        at_expiry = update_calendar.update_state(self.seminar, self.state, now=expiry)
        self.assertIn("test_reminder", at_expiry["events"]["session-beta"]["payload"])
        expired = update_calendar.update_state(self.seminar, at_expiry, now=expiry + timedelta(seconds=1))
        payload = expired["events"]["session-beta"]["payload"]
        self.assertNotIn("test_reminder", payload)
        self.assertEqual(payload["reminders"], ["20261113T080000Z", "20261116T060000Z"])
        alarms = alarm_components(self.feed(expired, "session-beta"))
        self.assertEqual(len(alarms), 2)
        self.assertEqual([alarm["TRIGGER;VALUE=DATE-TIME"] for alarm in alarms], payload["reminders"])
        self.assertEqual(event_components(self.feed(expired, "session-beta"))[0]["UID"],
                         "session-beta@parma-inria.github.io")
        for identifier in ("session-alpha", "session-gamma"):
            self.assertEqual(expired["events"][identifier], self.state["events"][identifier])

    def test_cancelled_target_is_silent_even_with_stale_saved_test_trigger(self):
        changed = copy.deepcopy(self.seminar)
        changed["sessions"][1]["cancelled"] = True
        cancelled = update_calendar.update_state(changed, self.state, now=FIRST_REVISION)
        self.assertNotIn("test_reminder", cancelled["events"]["session-beta"]["payload"])
        # Simulate a retained tombstone carrying a previous version's trigger.
        cancelled["events"]["session-beta"]["payload"]["test_reminder"] = "20261104T123500Z"
        self.assertEqual(alarm_components(self.feed(cancelled, "session-beta")), [])

    def test_saved_optional_test_trigger_requires_a_valid_utc_timestamp(self):
        saved = Mock()
        saved.exists.return_value = True
        saved.read_text.return_value = json.dumps(self.state)
        self.assertEqual(update_calendar.read_state(saved), self.state)
        for invalid in ("20261104T123500", "20261104T123500+0100", "20260230T123500Z", 123):
            changed = copy.deepcopy(self.state)
            changed["events"]["session-beta"]["payload"]["test_reminder"] = invalid
            saved.read_text.return_value = json.dumps(changed)
            with self.subTest(trigger=invalid), self.assertRaises(ValueError):
                update_calendar.read_state(saved)


if __name__ == "__main__":
    unittest.main()
