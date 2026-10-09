"""Check publication identity, ordering and failure recovery without network calls."""

import copy
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import update_publications as publications


def record(identifier, published, title="A paper", author="Thomas O. Gallouët", **extra):
    return {
        "halId_s": identifier, "version_i": 1, "docType_s": "ART",
        "title_s": [title], "authFullName_s": [author],
        "journalTitle_s": "Example journal", "publicationDate_s": published,
        **extra,
    }


class PublicationTests(unittest.TestCase):
    def test_dates_keep_precision_and_reject_invalid_or_in_press_values(self):
        self.assertEqual(publications.date_label("2026"), "2026")
        self.assertEqual(publications.date_label("2026-04"), "April 2026")
        self.assertEqual(publications.date_label("2026-04-03"), "3 April 2026")
        for value in ("0", "In press", "2026-02-30", "2026-13", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                publications.date_parts(value)

    def test_hal_order_includes_preprints_and_excludes_future_dates(self):
        # Input order is the official HAL search order, not a local date sort.
        documents = [
            record("hal-4", "2027-01", title="Future"),
            record("hal-5", "2026-10-01", title="Preprint", docType_s="UNDEFINED", journalTitle_s=""),
            record("hal-1", "2026-09-01", title="September", author="New ParMA member"),
            record("hal-2", "2026-08", title="August", docType_s="COMM", proceedings_s="1"),
            record("hal-3", "2026", title="Year-only"),
            record("hal-7", "0", title="Missing date"),
        ]
        selected = publications.select_publications(documents, date(2026, 10, 9))
        self.assertEqual([item["id"] for item in selected], ["hal-5", "hal-1", "hal-2"])
        self.assertEqual(selected[0]["venue"], "Preprint")
        self.assertEqual(selected[2]["date"], "2026-08")

    def test_search_matches_the_shared_hal_list(self):
        from urllib.parse import parse_qs, urlsplit

        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *arguments):
                pass

        with patch.object(publications, "urlopen", return_value=Response()) as request, \
                patch.object(publications.json, "load", return_value={"response": {"numFound": 0, "docs": []}}):
            self.assertEqual(publications.fetch_records(1184761), [])
        parameters = parse_qs(urlsplit(request.call_args.args[0].full_url).query)
        self.assertEqual(parameters["q"], ["*"])
        self.assertEqual(parameters["fq"], ["structId_i:1184761"])
        self.assertEqual(parameters["sort"], ["publicationDate_tdate desc"])

    def test_versions_dois_and_same_title_with_distinct_dois(self):
        documents = [
            record("hal-1", "2026-09-01", title="Same title", doiId_s="https://doi.org/10.1234/A"),
            record("hal-1", "2026-09-01", title="Same title", doiId_s="10.1234/a", version_i=2),
            record("hal-2", "2026-09-01", title="Same title", doiId_s="10.1234/B"),
            record("hal-3", "2026-08", title="Duplicate alias", doiId_s="10.1234/a"),
            record("hal-4", "2026-07", title="Third paper"),
        ]
        selected = publications.select_publications(documents, date(2026, 10, 9))
        self.assertEqual({item["id"] for item in selected}, {"hal-1", "hal-2", "hal-4"})
        self.assertEqual(next(item["doi"] for item in selected if item["id"] == "hal-1"), "10.1234/a")

    def test_insufficient_results_do_not_replace_a_valid_snapshot(self):
        settings = json.loads(publications.SNAPSHOT.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "publications.json"
            snapshot.write_text(json.dumps(settings), encoding="utf-8")
            original = snapshot.read_bytes()
            with patch.object(publications, "fetch_records", return_value=[]):
                self.assertFalse(publications.refresh(snapshot=snapshot, allow_stale=True, today=date(2026, 10, 10)))
                self.assertEqual(snapshot.read_bytes(), original)
                with self.assertRaises(publications.UpdateUnavailable):
                    publications.refresh(snapshot=snapshot, allow_stale=False, today=date(2026, 10, 10))
            corrupt = copy.deepcopy(settings)
            corrupt["hal_structure_id"] = "not-an-ID"
            snapshot.write_text(json.dumps(corrupt), encoding="utf-8")
            with self.assertRaises(ValueError):
                publications.refresh(snapshot=snapshot, allow_stale=True)

    def test_monthly_record_and_new_cards_are_saved_without_daily_commit_noise(self):
        previous = {"items": ["A", "B", "C"], "updated_on": "2026-10-09"}
        self.assertFalse(publications.needs_saved_snapshot(previous, {**previous, "updated_on": "2026-10-10"}))
        self.assertTrue(publications.needs_saved_snapshot(previous, {**previous, "updated_on": "2026-11-01"}))
        self.assertTrue(publications.needs_saved_snapshot(previous, {**previous, "items": ["D", "B", "C"]}))

    def test_git_saving_is_not_available_in_the_local_preview(self):
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(ValueError):
            publications.save_snapshot_to_git()


if __name__ == "__main__":
    unittest.main()
