"""Check generated views with fixtures, independently of editable site content.

Run from the project folder: python -m unittest discover -s tests
"""

import copy
import sys
import tempfile
import unittest
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build


def talk(speaker="Sample speaker", title="Sample talk"):
    return {"time": "10:00", "speaker": speaker, "title": title, "abstract": ["First paragraph."]}


def seminar_fixture():
    return {
        "introduction": "A sample research seminar.",
        "organizers": [{"name": "Sample organizer", "email": "organizer@example.org", "url": None}],
        "mailing_list_note": "Contact the organizers.",
        "venue": {"name": "Sample institute", "url": "https://example.org/", "building": "1", "room": "A"},
        "labels": {
            "organizers": "Organizers", "location": "Location", "next_session": "Next Session",
            "schedule": "Schedule", "history": "History", "academic_year": "Academic Year",
            "abstract": "Abstract", "room": "Room", "home_next_session": "Next session",
            "empty_next_session": "No upcoming session.", "empty_programme": "Programme to be announced.",
        },
        # Deliberately unordered: rendering must sort dates rather than trust file order.
        "sessions": [
            {"date": "2027-04-05", "room": "A", "talks": []},
            {"date": "2026-10-12", "room": "A", "talks": [talk("Alpha speaker", "Current programme")]},
            {"date": "2026-06-15", "room": "A", "talks": [talk("Earlier speaker")]},
            {"date": "2026-12-14", "room": "A", "talks": [talk("Beta speaker", "Later programme")]},
            {"date": "2026-09-01", "room": "A", "talks": [talk("September speaker")]},
            {"date": "2026-11-16", "room": "A", "talks": []},
            {"date": "2026-08-31", "room": "A", "talks": [talk("August speaker")]},
        ],
    }


def home_fixture():
    return {
        "about_eyebrow": "Research", "about_title_lines": ["Sample team"],
        "introduction": ["Sample introduction."], "logo_alt": "Team logo", "logo_caption": "Sample caption.",
        "seminar": {"eyebrow": "Seminar", "title": "Sample GdT", "description": "Sample description.", "link_label": "Programme"},
    }


def fixture_sources(home=None, seminar=None, team=None):
    sources = {name: build.read_json(name) for name in ("site", "home", "team", "contact", "seminar", "publications")}
    if home is not None:
        sources["home"] = {**sources["home"], **home}
    if seminar is not None:
        sources["seminar"] = seminar
    if team is not None:
        sources["team"] = team
    return sources


def render_page(page_id, prefix, sources, plan):
    page = next(item for item in sources["site"]["pages"] if item["id"] == page_id)
    return build.render_document(page, prefix, sources, plan)


class RenderedElements(HTMLParser):
    """Read output attributes and calendar cells without relying on indentation."""

    def __init__(self, document):
        super().__init__()
        self.elements = []
        self.calendar_cells = []
        self.in_calendar = False
        self.cell_text = None
        self.feed(document)

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        self.elements.append((tag, attributes))
        if tag == "table" and attributes.get("class") == "schedule-table":
            self.in_calendar = True
        if tag == "td" and self.in_calendar:
            self.cell_text = ""

    def handle_data(self, text):
        if self.cell_text is not None:
            self.cell_text += text

    def handle_endtag(self, tag):
        if tag == "td" and self.cell_text is not None:
            self.calendar_cells.append(self.cell_text.strip())
            self.cell_text = None
        if tag == "table":
            self.in_calendar = False


class SeminarTests(unittest.TestCase):
    def setUp(self):
        self.seminar = seminar_fixture()
        self.home = home_fixture()

    def render(self, day):
        plan = build.plan_seminar(self.seminar, day)
        return (
            plan,
            render_page("home", "./", fixture_sources(self.home, self.seminar), plan),
            render_page("seminar", "../", fixture_sources(self.home, self.seminar), plan),
        )

    def test_session_moves_from_next_to_archive_on_following_day(self):
        on_day, home, _ = self.render(date(2026, 10, 12))
        self.assertEqual(on_day["next"]["date"], "2026-10-12")
        self.assertNotIn("2026-10-12", [session["date"] for session in on_day["history"][2026]])
        self.assertIn("12 October 2026", home)
        self.assertIn("Current programme", home)
        after, home, page = self.render(date(2026, 10, 13))
        self.assertEqual(after["next"]["date"], "2026-11-16")
        self.assertEqual(after["history"][2026][0]["date"], "2026-10-12")
        self.assertIn("16 November 2026", home)
        self.assertNotIn("Current programme", home)
        self.assertIn("Current programme", page)

    def test_academic_year_changes_on_first_of_september(self):
        august = build.plan_seminar(self.seminar, date(2026, 8, 31))
        september = build.plan_seminar(self.seminar, date(2026, 9, 1))
        self.assertEqual(august["academic_year"], 2025)
        self.assertEqual(september["academic_year"], 2026)
        self.assertEqual([session["date"] for session in august["calendar"]], ["2026-06-15", "2026-08-31"])
        self.assertEqual(september["calendar"][0]["date"], "2026-09-01")
        self.assertEqual(september["history"][2025][0]["date"], "2026-08-31")

    def test_planned_session_and_no_future_have_clear_messages(self):
        planned, home, page = self.render(date(2026, 10, 13))
        self.assertEqual(planned["next"]["talks"], [])
        self.assertIn("Programme to be announced.", home)
        self.assertIn("Programme to be announced.", page)
        future, home, page = self.render(date(2030, 9, 1))
        self.assertIsNone(future["next"])
        self.assertEqual(future["calendar"], [])
        self.assertIn("No upcoming session.", home)
        self.assertIn("No upcoming session.", page)
        self.assertNotIn('<p class="session-date"></p>', home)

    def test_all_announced_future_talks_and_calendar_dates_stay_visible(self):
        plan, home, page = self.render(date(2026, 10, 9))
        self.assertEqual(plan["next"]["date"], "2026-10-12")
        self.assertIn("Later programme", page)
        self.assertNotIn("Later programme", home)
        elements = RenderedElements(page)
        self.assertEqual(sum(attributes.get("data-upcoming") == "true" for _, attributes in elements.elements), 2)
        expected_dates = [date.fromisoformat(session["date"]).strftime("%d/%m/%Y") for session in plan["calendar"]]
        self.assertEqual(sorted(cell for cell in elements.calendar_cells if cell), sorted(expected_dates))
        self.assertEqual(elements.calendar_cells, ["01/09/2026", "14/12/2026", "12/10/2026", "05/04/2027", "16/11/2026", ""])

    def test_editable_text_is_escaped_and_abstract_paragraphs_remain_separate(self):
        current = next(session for session in self.seminar["sessions"] if session["date"] == "2026-10-12")
        current["talks"][0] = {
            "time": "", "speaker": '<img src=x onerror="bad">',
            "title": "A & B", "abstract": ["x < y", "second & third"],
        }
        build.validate_seminar(self.seminar)
        _, home, page = self.render(date(2026, 10, 9))
        self.assertNotIn('<img src=x', page)
        self.assertIn("&lt;img src=x onerror=&quot;bad&quot;&gt;", page)
        self.assertRegex(page, r'<p class="abstract-text">\s*x &lt; y\s*</p>')
        self.assertRegex(page, r'<p class="abstract-text">\s*second &amp; third\s*</p>')
        self.assertIn("A &amp; B", home)
        self.assertNotIn(" · &lt;img", home)

    def test_invalid_dates_duplicates_times_and_types_are_rejected(self):
        build.validate_seminar(self.seminar)
        for invalid in ("2026-2-01", "2026-02-30", "2026-13-01", "not-a-date", 42):
            with self.subTest(date=invalid), self.assertRaises(build.BuildError):
                build.parse_session_date(invalid, "test.date")
        duplicate = copy.deepcopy(self.seminar)
        duplicate["sessions"].append(copy.deepcopy(duplicate["sessions"][0]))
        with self.assertRaises(build.BuildError):
            build.validate_seminar(duplicate)
        for field, invalid in (("time", "24:00"), ("time", "10:60"), ("time", "9:00"), ("speaker", 42), ("abstract", [42])):
            bad = copy.deepcopy(self.seminar)
            next(session for session in bad["sessions"] if session["talks"])["talks"][0][field] = invalid
            with self.subTest(field=field, value=invalid), self.assertRaises(build.BuildError):
                build.validate_seminar(bad)

    def test_portrait_url_validation(self):
        member = {"name": "Sample Person", "photo": "https://example.org/photo.jpg?version=1&size=large"}
        build.validate_member_photo(member)
        build.validate_member_photo(dict(member, photo=None))
        build.validate_member_photo({"name": "Sample Person"})
        for invalid in (
            42, "", "//example.org/photo.jpg",
            "http://example.org/photo.jpg", "javascript:alert(1)", "https:///photo.jpg",
            "https://user:password@example.org/photo.jpg", "https://user@example.org/photo.jpg",
            "https://example.org:invalid/photo.jpg", "https://example.org:65536/photo.jpg",
            "https://example.org/ photo.jpg", "https://example.org\\photo.jpg", "https://[broken/photo.jpg",
        ):
            with self.subTest(photo=invalid), self.assertRaises(build.BuildError):
                build.validate_member_photo(dict(member, photo=invalid))

    def test_local_portrait_validation(self):
        photo = "assets/images/members/sample.jpg"
        member = {"name": "Sample Person", "photo": photo}
        with tempfile.TemporaryDirectory() as directory, patch.object(build, "ROOT", Path(directory)):
            image = Path(directory) / photo
            image.parent.mkdir(parents=True)
            image.write_bytes(b"fixture")  # Path validation does not decode photographs.
            build.validate_member_photo(member)
            # An existing file outside the allowed folder must still be rejected.
            outside = Path(directory) / "assets/images/outside.jpg"
            outside.write_bytes(b"fixture")
            for invalid in (
                "assets/images/members/missing.jpg", "assets/images/outside.jpg",
                "assets/images/members/../outside.jpg", "assets/images/members/../../outside.jpg",
                "assets/images/members/sample.svg", "assets/images/members/sample.jpg?x=1",
                "assets/images/members/sample.jpg#fragment", "assets/images/members/sample.jpg:stream",
                "assets/images/members/%2e%2e/outside.jpg",
                "assets/images/members/..\\outside.jpg", "/assets/images/members/sample.jpg",
                "C:/assets/images/members/sample.jpg",
            ):
                with self.subTest(photo=invalid), self.assertRaises(build.BuildError):
                    build.validate_member_photo(dict(member, photo=invalid))

    def test_remote_and_local_portraits_on_both_team_routes(self):
        photo = "https://example.org/photo.jpg?version=1&size=large"
        local_photo = "assets/images/members/local.jpg"
        member = {"name": "Sample Person", "affiliation": "Sample institute", "url": "https://example.org/", "photo": photo}
        team = {
            "introduction": "Sample team.",
            "search": {"label": "Search", "placeholder": "Name", "count_label": "members", "empty_message": "No result"},
            "sections": [{"id": "sample", "title": "Sample section", "members": [
                member, dict(member, name="Local Person", photo=local_photo),
                dict(member, name="Another Person", photo=None),
            ]}],
        }
        for prefix in ("../", "../../"):
            with self.subTest(prefix=prefix):
                sources = fixture_sources(team=team, seminar=seminar_fixture())
                plan = build.plan_seminar(sources["seminar"], date(2026, 10, 9))
                document = render_page("team", prefix, sources, plan)
                elements = RenderedElements(document).elements
                portraits = [attributes for tag, attributes in elements if tag == "img"
                            and attributes.get("class") == "member-portrait"]
                self.assertEqual(len(portraits), 2)
                self.assertEqual(portraits[0]["src"], photo)
                self.assertEqual(portraits[1]["src"], prefix + local_photo)
                self.assertEqual(portraits[0]["data-member-portrait"], "Sample Person")
                self.assertEqual(portraits[1]["data-member-portrait"], "Local Person")
                self.assertEqual(portraits[0]["alt"], "")
                self.assertEqual(portraits[0]["loading"], "lazy")
                self.assertEqual(sum(attributes.get("class") == "member-initials" for _, attributes in elements), 3)
                self.assertIn(">SP</span>", document)
                self.assertIn(">LP</span>", document)
                self.assertIn(">AP</span>", document)


if __name__ == "__main__":
    unittest.main()
