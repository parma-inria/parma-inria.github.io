"""Refresh the three newest ParMA publications from the official HAL API.

Settings and the saved snapshot live in content/publications.json. The build
uses this snapshot offline; GitHub refreshes it before its daily publication.
"""

import argparse
import json
import os
import re
import sys
import subprocess
import tempfile
import time
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


# Keep requests on HAL; no credentials or extra Python packages are required.
ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "content/publications.json"
API = "https://api.hal.science/search/"
FIELDS = (
    "halId_s,version_i,title_s,authFullName_s,publicationDate_s,"
    "journalTitle_s,conferenceTitle_s,bookTitle_s,"
    "proceedings_s,doiId_s,docType_s"
)
MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


class UpdateUnavailable(Exception):
    """HAL failed to provide enough valid publications for a complete update."""


# Normalize titles and author names only when detecting duplicate records.
def normalize(value, name=False):
    value = unicodedata.normalize("NFD", value.casefold())
    value = "".join(character for character in value if not unicodedata.combining(character))
    words = re.sub(r"[^a-z0-9]+", " ", value).split()
    if name:
        words = [word for word in words if len(word) > 1]
    return " ".join(words)


def date_parts(value):
    """Validate ISO dates while retaining year-only and month-only precision."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", value):
        raise ValueError("Publication dates must use YYYY, YYYY-MM or YYYY-MM-DD.")
    parts = tuple(int(part) for part in value.split("-"))
    date(parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1)
    return parts


def date_label(value):
    """Show only the day and month actually supplied by HAL."""
    parts = date_parts(value)
    if len(parts) == 1:
        return str(parts[0])
    if len(parts) == 2:
        return f"{MONTHS[parts[1] - 1]} {parts[0]}"
    return f"{parts[2]} {MONTHS[parts[1] - 1]} {parts[0]}"


def validate_data(data):
    """Reject local configuration mistakes before trying the network."""
    for key in ("title", "source_name", "source_url", "link_label", "empty_message", "updated_on"):
        if not isinstance(data.get(key), str):
            raise ValueError(f"publications.json: {key} must be text.")
    structure = data.get("hal_structure_id")
    if type(structure) is not int or structure <= 0:
        raise ValueError("publications.json: hal_structure_id must be a positive integer.")
    source = urlsplit(data["source_url"])
    if source.scheme != "https" or not source.netloc or source.username or source.password:
        raise ValueError("publications.json: source_url must be a complete HTTPS URL.")
    if data["updated_on"]:
        date.fromisoformat(data["updated_on"])
    items = data.get("items")
    if not isinstance(items, list) or len(items) not in (0, 3):
        raise ValueError("publications.json: save either an empty initial list or exactly three papers.")
    if len({item.get("id") for item in items if isinstance(item, dict)}) != len(items):
        raise ValueError("publications.json: paper IDs must be distinct.")
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("publications.json: papers must be JSON objects.")
        for key in ("id", "title", "venue", "date", "url", "doi"):
            if not isinstance(item.get(key), str) or (key != "doi" and not item[key]):
                raise ValueError(f"publications.json: each paper needs {key}.")
        authors = item.get("authors")
        if not isinstance(authors, list) or not authors or not all(isinstance(author, str) and author for author in authors):
            raise ValueError("publications.json: each paper needs an author list.")
        date_parts(item["date"])
        parts = urlsplit(item["url"])
        if parts.scheme != "https" or not parts.netloc or parts.username or parts.password:
            raise ValueError("publications.json: paper links must be complete HTTPS URLs.")


# Fetch all pages so filtering or duplicate records cannot hide eligible papers.
def fetch_records(structure):
    documents = []
    start = 0
    while True:
        parameters = {
            "q": "*",
            "fq": f"structId_i:{structure}",
            "sort": "publicationDate_tdate desc",
            "rows": 200, "start": start, "wt": "json", "fl": FIELDS,
        }
        request = Request(API + "?" + urlencode(parameters), headers={
            "User-Agent": "ParMA-website-publications/1.0",
            "Accept": "application/json",
        })
        payload = None
        for attempt in range(3):
            try:
                with urlopen(request, timeout=15) as response:
                    payload = json.load(response)
                break
            except (OSError, ValueError) as error:
                if attempt == 2:
                    raise UpdateUnavailable(f"HAL request failed: {error}") from error
                time.sleep(attempt + 1)
        result = payload.get("response") if isinstance(payload, dict) else None
        if not isinstance(result, dict) or not isinstance(result.get("docs"), list):
            raise UpdateUnavailable("HAL returned an invalid response.")
        count = result.get("numFound")
        if type(count) is not int or not 0 <= count <= 10000:
            raise UpdateUnavailable("HAL returned an invalid or unexpectedly large result count.")
        batch = result["docs"]
        if not all(isinstance(item, dict) for item in batch):
            raise UpdateUnavailable("HAL returned an invalid document list.")
        documents.extend(batch)
        start += len(batch)
        if start >= count:
            return documents
        if not batch:
            raise UpdateUnavailable("HAL pagination stopped before all records were received.")


def normalize_doi(value):
    if not isinstance(value, str):
        return ""
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value.strip(), flags=re.IGNORECASE)
    return value.casefold() if re.fullmatch(r"10\.\d{4,9}/\S+", value) else ""


# Follow HAL search order; its date also covers preprints and working papers.
def select_publications(records, today):
    by_hal_id = {}
    for position, record in enumerate(records):
        authors = record.get("authFullName_s")
        if not isinstance(authors, list) or not authors or not all(isinstance(author, str) for author in authors):
            continue
        # Skip missing dates and records dated after today.
        published = record.get("publicationDate_s")
        try:
            parts = date_parts(published)
        except ValueError:
            continue
        earliest = date(parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1)
        if earliest > today:
            continue
        titles = record.get("title_s")
        identifier = record.get("halId_s")
        venue = record.get("journalTitle_s") or record.get("bookTitle_s") or record.get("conferenceTitle_s")
        if not venue:
            venue = {
                "UNDEFINED": "Preprint", "ART": "Journal article",
                "COMM": "Conference contribution", "THESE": "Thesis",
                "REPORT": "Report", "OUV": "Book", "COUV": "Book chapter",
            }.get(record.get("docType_s"), "HAL publication")
        version = record.get("version_i", 1)
        if (not isinstance(titles, list) or not titles or not isinstance(titles[0], str)
                or not titles[0].strip() or not isinstance(venue, str) or not venue.strip()
                or not isinstance(identifier, str) or not re.fullmatch(r"[a-z][a-z0-9]*-\d+", identifier)
                or type(version) is not int):
            continue
        paper = {
            "id": identifier, "title": titles[0].strip(), "authors": authors,
            "venue": venue.strip(), "date": published,
            "url": "https://hal.science/" + identifier,
            "doi": normalize_doi(record.get("doiId_s", "")),
            "_version": version, "_position": position,
        }
        previous = by_hal_id.get(identifier)
        if previous is None or version > previous["_version"]:
            if previous is not None:
                paper["_position"] = previous["_position"]
            by_hal_id[identifier] = paper

    # Versions and DOI aliases count once. Different known DOIs stay distinct.
    selected = []
    for paper in sorted(by_hal_id.values(), key=lambda item: item["_position"]):
        title_key = (normalize(paper["title"]), normalize(paper["authors"][0], name=True))
        duplicate = False
        for previous in selected:
            same_doi = paper["doi"] and paper["doi"] == previous["doi"]
            previous_title = (normalize(previous["title"]), normalize(previous["authors"][0], name=True))
            fallback_match = title_key == previous_title and not (paper["doi"] and previous["doi"])
            if same_doi or fallback_match:
                duplicate = True
                break
        if not duplicate:
            selected.append(paper)
        if len(selected) == 3:
            break
    if len(selected) != 3:
        raise UpdateUnavailable(f"HAL supplied {len(selected)} eligible unique papers; three are required.")
    return [{key: value for key, value in paper.items() if not key.startswith("_")} for paper in selected]


def refresh(snapshot=SNAPSHOT, allow_stale=False, today=None):
    """Replace the snapshot atomically only after a complete, valid update."""
    today = today or date.today()
    snapshot = Path(snapshot)
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    validate_data(data)
    try:
        records = fetch_records(data["hal_structure_id"])
        items = select_publications(records, today)
    except UpdateUnavailable as error:
        if allow_stale and len(data["items"]) == 3:
            print(f"Warning: {error} Keeping the saved publications from {data['updated_on']}.", file=sys.stderr)
            return False
        raise
    replacement = {**data, "updated_on": today.isoformat(), "items": items}
    validate_data(replacement)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=snapshot.parent, prefix=".publications-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(replacement, ensure_ascii=False, indent=2) + "\n")
        os.replace(temporary, snapshot)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(f"Updated three ParMA publications from HAL ({today.isoformat()}).")
    return True


def needs_saved_snapshot(previous, current):
    """Save new cards immediately and record a successful check once a month."""
    return (previous["items"] != current["items"]
            or previous["updated_on"][:7] != current["updated_on"][:7])


def save_snapshot_to_git():
    """In GitHub Actions, save only publication data to the default branch."""
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME") not in {"push", "schedule", "workflow_dispatch"}):
        raise ValueError("Saving to Git is available only in the main-branch GitHub workflow.")
    current = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    validate_data(current)
    previous = json.loads(subprocess.check_output(
        ["git", "show", "HEAD:content/publications.json"], cwd=ROOT, text=True, encoding="utf-8",
    ))
    if not needs_saved_snapshot(previous, current):
        print("The saved publication cards are already current.")
        return
    commands = [
        ["git", "config", "user.name", "github-actions[bot]"],
        ["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"],
        ["git", "add", "--", "content/publications.json"],
        ["git", "commit", "--only", "-m", "Update recent ParMA publications", "--", "content/publications.json"],
        ["git", "push", "origin", "HEAD:main"],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)


# This tool is separate from build.py so local previews also work offline.
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group()
    options.add_argument("--allow-stale", action="store_true", help="Keep a valid saved snapshot when HAL is unavailable.")
    options.add_argument("--save-to-git", action="store_true", help="Save updated publication data from the main GitHub workflow.")
    arguments = parser.parse_args(argv)
    try:
        if arguments.save_to_git:
            save_snapshot_to_git()
        else:
            refresh(allow_stale=arguments.allow_stale)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError, UpdateUnavailable) as error:
        print(f"Publication update failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
