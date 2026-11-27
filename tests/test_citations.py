"""Exercise citation identity and fallback behavior without live API calls."""

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import update_citations as citations


TODAY = date(2026, 11, 27)


def hal(identifier, title="Regularized optimal transport", **fields):
    return {
        "halId_s": identifier, "version_i": 1, "title_s": [title],
        "authFullName_s": ["Élise Example", "Alice Example"], "publicationDate_s": "2025-10",
        **fields,
    }


def openalex(number, title="Regularized optimal transport", author="Elise Example", year=2025):
    return {
        "id": f"https://openalex.org/W{number}", "display_name": title,
        "publication_year": year, "authorships": [{"raw_author_name": author}],
        "cited_by_count": 12, "counts_by_year": [{"year": 2026, "cited_by_count": 5}],
    }


class CitationTests(unittest.TestCase):
    def test_preprint_versions_and_openalex_aliases_contribute_once(self):
        records = [
            hal("hal-1", "Old title", arxivId_s="2501.12345v1"),
            hal("hal-1", arxivId_s="2501.12345v2", version_i=2),
            hal("hal-2", doiId_s="10.1234/paper", arxivId_s="2501.12345"),
            hal("hal-3", "An alias in HAL", doiId_s="10.1234/alias"),
            hal("hal-4", "An unindexed work"),
        ]
        work = openalex(1)
        values = {
            "/doi:10.1234/paper": work, "/doi:10.1234/alias": work,
            "": {"results": []},
        }
        with patch.object(citations, "openalex_json", side_effect=lambda path="", **kwargs: values[path]):
            snapshot = citations.collect_citations(records, TODAY)
        self.assertEqual(snapshot, {
            "updated_on": "2026-11-27", "works_total": 2, "works_matched": 1,
            "citations_total": 12, "citations_this_year": 5,
        })

    def test_title_lookup_requires_matching_title_first_author_year_and_unique_id(self):
        record = hal("hal-1")
        same_work = openalex(1, "Regularized Optimal Transport", author="Elise Example", year=2026)
        near_hits = [
            openalex(2, "Regularized optimal transport for images"),
            openalex(3, author="Alice Example"),
            openalex(4, year=2022),
        ]
        near_hits[1]["authorships"][0]["author"] = "malformed profile"
        response = {"results": [same_work, *near_hits]}
        with patch.object(citations, "openalex_json", return_value=response):
            self.assertEqual(citations.search_by_title(record), same_work)
            response["results"].append(openalex(5))
            self.assertIsNone(citations.search_by_title(record))

    def test_weekly_skip_and_failed_refresh_preserve_saved_counts(self):
        snapshot = {
            "updated_on": TODAY.isoformat(), "works_total": 4, "works_matched": 3,
            "citations_total": 12, "citations_this_year": 5,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "citations.json"
            original = json.dumps(snapshot).encode("utf-8")
            path.write_bytes(original)
            with patch.object(citations, "fetch_records", side_effect=citations.UpdateUnavailable("offline")) as fetch:
                self.assertFalse(citations.refresh(path, weekly=True, today=TODAY))
                fetch.assert_not_called()
                self.assertFalse(citations.refresh(path, allow_stale=True, today=TODAY))
                fetch.assert_called_once()
                self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
