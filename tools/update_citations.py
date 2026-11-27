"""Refresh team citation counts from OpenAlex for the complete ParMA HAL list."""

import argparse
import json
import os
import re
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from update_publications import (
    FIELDS, SNAPSHOT as PUBLICATIONS, UpdateUnavailable, date_parts, fetch_records,
    normalize, normalize_doi,
)


SNAPSHOT = PUBLICATIONS.with_name("citations.json")
OPENALEX = "https://api.openalex.org/works"
OPENALEX_FIELDS = (
    "id,display_name,alternate_titles,publication_year,authorships,"
    "cited_by_count,counts_by_year"
)
COUNTS = ("works_total", "works_matched", "citations_total", "citations_this_year")


def nonnegative_integer(value):
    return type(value) is int and value >= 0


def validate_snapshot(data):
    """Check the snapshot shipped to the offline site builder."""
    if not isinstance(data, dict) or not isinstance(data.get("updated_on"), str):
        raise ValueError("citations.json: updated_on must be a date or an empty string.")
    if not all(nonnegative_integer(data.get(key)) for key in COUNTS):
        raise ValueError("citations.json: all counts must be non-negative integers.")
    if data["works_matched"] > data["works_total"] or data["citations_this_year"] > data["citations_total"]:
        raise ValueError("citations.json: partial counts cannot exceed their totals.")
    if data["updated_on"]:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["updated_on"]) or not data["works_matched"]:
            raise ValueError("citations.json: a dated snapshot needs a matched work and an ISO date.")
        date.fromisoformat(data["updated_on"])
    elif any(data[key] for key in COUNTS):
        raise ValueError("citations.json: a snapshot without a date must be empty.")


def normalize_arxiv(value):
    if not isinstance(value, str):
        return ""
    value = re.sub(
        r"^(?:arxiv:\s*|https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/|10\.48550/arxiv\.)",
        "", value.strip().lower(),
    )
    value = re.sub(r"(?:v\d+)?(?:\.pdf)?$", "", value)
    return value if re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z.-]+/\d{7})", value) else ""


def group_hal_records(records):
    """Group versions and aliases sharing a HAL ID, DOI or arXiv ID."""
    groups = {}
    by_identifier = {}
    for position, record in enumerate(records):
        hal_id = record.get("halId_s")
        if not isinstance(hal_id, str) or not re.fullmatch(r"[a-z][a-z0-9]*-\d+", hal_id):
            continue
        identifiers = [("hal", hal_id)]
        doi = normalize_doi(record.get("doiId_s"))
        arxiv = normalize_arxiv(record.get("arxivId_s")) or normalize_arxiv(doi)
        if doi:
            identifiers.append(("doi", doi))
        if arxiv:
            identifiers.append(("arxiv", arxiv))

        # A record with two identifiers can connect previously separate groups.
        existing = {by_identifier[key] for key in identifiers if key in by_identifier}
        group_id = min(existing, default=position)
        group = groups.setdefault(group_id, {"records": [], "identifiers": set()})
        for other_id in sorted(existing - {group_id}):
            other = groups.pop(other_id)
            group["records"].extend(other["records"])
            group["identifiers"].update(other["identifiers"])
        group["records"].append(record)
        group["identifiers"].update(identifiers)
        for key in group["identifiers"]:
            by_identifier[key] = group_id
    return list(groups.values())


def openalex_json(path="", parameters=None, allow_missing=False):
    request = Request(
        OPENALEX + path + "?" + urlencode({"select": OPENALEX_FIELDS, **(parameters or {})}),
        headers={"User-Agent": "ParMA-website-citations/1.0", "Accept": "application/json"},
    )
    for attempt in range(3):
        try:
            with urlopen(request, timeout=15) as response:
                result = json.load(response)
            if isinstance(result, dict):
                return result
            raise UpdateUnavailable("OpenAlex returned an invalid response.")
        except HTTPError as error:
            if error.code == 404 and allow_missing:
                return None
            if error.code != 429 and not 500 <= error.code < 600:
                raise UpdateUnavailable(f"OpenAlex request failed (HTTP {error.code}).") from error
            retry_delay = error.headers.get("Retry-After", "")
            delay = min(int(retry_delay), 15) if retry_delay.isdecimal() else attempt + 1
            if attempt == 2:
                raise UpdateUnavailable(f"OpenAlex request failed (HTTP {error.code}).") from error
            time.sleep(delay)
        except (OSError, ValueError) as error:
            if attempt == 2:
                raise UpdateUnavailable(f"OpenAlex request failed: {error}") from error
            time.sleep(attempt + 1)


def work_id(work):
    if not isinstance(work, dict):
        raise UpdateUnavailable("OpenAlex returned an invalid work.")
    identifier = work.get("id")
    if not isinstance(identifier, str) or not re.fullmatch(r"https://openalex\.org/W[0-9]+", identifier):
        raise UpdateUnavailable("OpenAlex returned a work without a valid identifier.")
    return identifier


def latest_hal_records(records):
    """Use the newest descriptive metadata for each HAL identifier."""
    latest = {}
    for record in records:
        identifier = record["halId_s"]
        version = record.get("version_i", 1)
        version = version if type(version) is int else 1
        if identifier not in latest or version > latest[identifier][0]:
            latest[identifier] = (version, record)
    return [record for _, record in latest.values()]


def search_by_title(record):
    titles = record.get("title_s")
    authors = record.get("authFullName_s")
    if not (isinstance(titles, list) and titles and isinstance(titles[0], str)
            and isinstance(authors, list) and authors and isinstance(authors[0], str)):
        return None
    title = normalize(titles[0])
    first_author = normalize(authors[0], name=True)
    try:
        year = date_parts(record.get("publicationDate_s"))[0]
    except ValueError:
        return None
    if not title or not first_author:
        return None

    # Verify title, first author and year even when search returns a strong hit.
    years = "|".join(str(value) for value in range(year - 1, year + 2))
    answer = openalex_json(parameters={
        "search": title,
        "filter": f"publication_year:{years}",
        "per_page": 25,
    })
    candidates = answer.get("results")
    if not isinstance(candidates, list) or not all(isinstance(work, dict) for work in candidates):
        raise UpdateUnavailable("OpenAlex returned an invalid search result.")
    matches = {}
    for work in candidates:
        year_found = work.get("publication_year")
        if type(year_found) is not int or abs(year - year_found) > 1:
            continue
        alternate_titles = work.get("alternate_titles")
        title_options = [work.get("display_name")]
        if isinstance(alternate_titles, list):
            title_options.extend(alternate_titles)
        if not any(isinstance(option, str) and normalize(option) == title for option in title_options):
            continue
        byline = work.get("authorships")
        if not isinstance(byline, list) or not byline or not isinstance(byline[0], dict):
            continue
        author = byline[0]
        profile = author.get("author")
        if not isinstance(profile, dict):
            profile = {}
        name_options = (author.get("raw_author_name"), profile.get("display_name"))
        if any(isinstance(option, str) and normalize(option, name=True) == first_author for option in name_options):
            matches[work_id(work)] = work
    return next(iter(matches.values())) if len(matches) == 1 else None


def match_work(group):
    # Prefer the published DOI, then arXiv, before relying on descriptive evidence.
    identifiers = group["identifiers"]
    doi_ids = sorted(value for kind, value in identifiers if kind == "doi" and not normalize_arxiv(value))
    arxiv_ids = sorted(value for kind, value in identifiers if kind == "arxiv")
    for sources, prefix in ((doi_ids, "doi"), (arxiv_ids, "arxiv")):
        matches = {}
        for identifier in sources:
            work = openalex_json("/" + prefix + ":" + quote(identifier, safe="/"), allow_missing=True)
            if work is not None:
                matches[work_id(work)] = work
        if matches:
            return next(iter(matches.values())) if len(matches) == 1 else None

    matches = {}
    for record in latest_hal_records(group["records"]):
        work = search_by_title(record)
        if work is not None:
            matches[work_id(work)] = work
    return next(iter(matches.values())) if len(matches) == 1 else None


def count_citations(work, year):
    total = work.get("cited_by_count")
    annual = work.get("counts_by_year")
    if not nonnegative_integer(total) or not isinstance(annual, list):
        raise UpdateUnavailable("OpenAlex returned incomplete citation counts.")
    counts_by_year = {}
    for entry in annual:
        if (not isinstance(entry, dict) or type(entry.get("year")) is not int
                or not nonnegative_integer(entry.get("cited_by_count")) or entry["year"] in counts_by_year):
            raise UpdateUnavailable("OpenAlex returned invalid annual citation counts.")
        counts_by_year[entry["year"]] = entry["cited_by_count"]
    this_year = counts_by_year.get(year, 0)
    if this_year > total:
        raise UpdateUnavailable("OpenAlex returned an annual count above the total.")
    return total, this_year


def collect_citations(records, today):
    groups = group_hal_records(records)
    matched = {}
    unmatched = 0
    for group in groups:
        work = match_work(group)
        if work is None:
            unmatched += 1
        else:
            identifier = work_id(work)
            matched[identifier] = count_citations(work, today.year)
    if not matched:
        raise UpdateUnavailable("No ParMA works could be matched to OpenAlex.")
    return {
        "updated_on": today.isoformat(),
        "works_total": len(matched) + unmatched,
        "works_matched": len(matched),
        "citations_total": sum(total for total, _ in matched.values()),
        "citations_this_year": sum(annual for _, annual in matched.values()),
    }


def refresh(snapshot=SNAPSHOT, *, weekly=False, allow_stale=False, today=None):
    today = today or date.today()
    path = Path(snapshot)
    previous = json.loads(path.read_text(encoding="utf-8"))
    validate_snapshot(previous)
    if weekly and previous["updated_on"]:
        elapsed = (today - date.fromisoformat(previous["updated_on"])).days
        if 0 <= elapsed < 7:
            print("The saved citation counts were refreshed less than a week ago.")
            return False
    structure = json.loads(PUBLICATIONS.read_text(encoding="utf-8"))["hal_structure_id"]
    try:
        records = fetch_records(structure, fields=FIELDS + ",arxivId_s")
        snapshot_data = collect_citations(records, today)
    except UpdateUnavailable as error:
        if allow_stale:
            print(f"Warning: {error} Keeping the saved citation data.", file=sys.stderr)
            return False
        raise
    validate_snapshot(snapshot_data)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=".citations-", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(snapshot_data, indent=2) + "\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(
        f"Updated OpenAlex citations for {snapshot_data['works_matched']} of "
        f"{snapshot_data['works_total']} ParMA works."
    )
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weekly", action="store_true", help="Skip a successful refresh less than seven days old.")
    parser.add_argument("--allow-stale", action="store_true", help="Keep saved counts if a data source is unavailable.")
    options = parser.parse_args()
    try:
        refresh(weekly=options.weekly, allow_stale=options.allow_stale)
    except (OSError, ValueError, KeyError, UpdateUnavailable) as error:
        print(f"Citation update failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
