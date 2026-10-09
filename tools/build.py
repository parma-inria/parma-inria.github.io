"""Build the site from four complete HTML pages and JSON content.

All HTML belongs in pages/. This tool only validates data, prepares dates and
paths, and expands {{ field.path }}, {% for ... %} and {% if ... %} blocks.
Uses the Python standard library; no packages need to be installed.
"""

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path, PurePosixPath
from datetime import date
from urllib.parse import urlsplit

# Source folders and shared date labels
ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
PAGES = ROOT / "pages"
DEFAULT_OUTPUT = ROOT / "public"
PAGE_IDS = {"home", "team", "seminar", "contact"}
MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
)


class BuildError(Exception):
    """An editable source is missing or invalid."""


# Load and validate editable JSON content


def read_text(path):
    """Read a source file and explain missing files in Italian."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise BuildError(f"File sorgente mancante: {path}") from error


def read_json(name):
    """Read a content file and require a JSON object at its root."""
    path = CONTENT / f"{name}.json"
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as error:
        raise BuildError(
            f"JSON non valido in {path}, riga {error.lineno}, "
            f"colonna {error.colno}: {error.msg}"
        ) from error
    if not isinstance(data, dict):
        raise BuildError(f"{path}: il contenuto deve essere un oggetto JSON.")
    return data


def require_fields(data, location, fields):
    """Check the small set of fields used by a template."""
    if not isinstance(data, dict):
        raise BuildError(f"{location}: deve essere un oggetto JSON.")
    for field, expected_type in fields.items():
        if field not in data:
            raise BuildError(f"{location}: manca il campo '{field}'.")
        if not isinstance(data[field], expected_type):
            raise BuildError(f"{location}: il tipo del campo '{field}' non è valido.")


def require_text_list(items, location):
    """Require at least one paragraph or heading line."""
    if not items or not all(isinstance(item, str) for item in items):
        raise BuildError(f"{location}: inserisci un elenco non vuoto di testi.")


def require_web_url(url, location):
    """Allow personal/institutional links; an empty member URL means no link."""
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise BuildError(f"{location}: usa un indirizzo completo http:// o https://.")


def validate_content(sources):
    """Catch common editing mistakes before writing any generated pages."""
    site, home, team, contact = (sources[key] for key in ("site", "home", "team", "contact"))

    # Shared navigation, page banners and footer
    require_fields(site, "content/site.json", {
        "name": str, "language": str, "theme_color": str, "brand_caption": str,
        "skip_label": str, "menu_label": str, "navigation_label": str,
        "pages": list, "footer": dict,
    })
    page_ids = []
    for index, page in enumerate(site["pages"]):
        location = f"content/site.json → pages[{index}]"
        require_fields(page, location, {
            "id": str, "path": str, "title": str, "description": str, "hero": dict,
        })
        path = page["path"]
        if ".." in PurePosixPath(path).parts or path.startswith("/") or "\\" in path or ":" in path:
            raise BuildError(f"{location}: 'path' deve essere un percorso relativo al sito.")
        require_fields(page["hero"], location + " → hero", {
            "eyebrow": str, "title_lines": list, "lead": str,
        })
        require_text_list(page["hero"]["title_lines"], location + " → hero.title_lines")
        page_ids.append(page["id"])
    if set(page_ids) != PAGE_IDS or len(page_ids) != len(PAGE_IDS):
        raise BuildError("content/site.json: mantieni una pagina per home, team, seminar e contact.")
    if len({page["path"] for page in site["pages"]}) != len(page_ids):
        raise BuildError("content/site.json: i percorsi delle pagine devono essere diversi.")
    require_fields(site["footer"], "content/site.json → footer", {
        "tagline": str, "note": str, "links_label": str, "links": list,
    })
    for link in site["footer"]["links"]:
        require_fields(link, "content/site.json → footer.links", {"label": str, "url": str})
        require_web_url(link["url"], "content/site.json → footer.links.url")

    # Home introduction, research topics and seminar summary
    require_fields(home, "content/home.json", {
        "hero_actions": dict, "about_eyebrow": str, "about_title_lines": list,
        "introduction": list, "logo_alt": str, "logo_caption": str,
        "research_title": str, "research": list, "seminar": dict,
    })
    require_text_list(home["about_title_lines"], "content/home.json → about_title_lines")
    require_text_list(home["introduction"], "content/home.json → introduction")
    require_fields(home["hero_actions"], "content/home.json → hero_actions", {
        "team_label": str, "seminar_label": str,
    })
    for feature in home["research"]:
        require_fields(feature, "content/home.json → research", {"title": str, "text": str})
    require_fields(home["seminar"], "content/home.json → seminar", {
        "eyebrow": str, "title": str, "description": str, "link_label": str,
    })

    # Member groups, personal websites and optional portraits
    require_fields(team, "content/team.json", {
        "introduction": str, "search": dict, "sections": list,
    })
    require_fields(team["search"], "content/team.json → search", {
        "label": str, "placeholder": str, "count_label": str, "empty_message": str,
    })
    section_ids = []
    for section in team["sections"]:
        require_fields(section, "content/team.json → sections", {
            "id": str, "title": str, "members": list,
        })
        section_ids.append(section["id"])
        for member in section["members"]:
            require_fields(member, f"content/team.json → {section['title']}", {
                "name": str, "affiliation": str, "url": (str, type(None)),
            })
            if member["url"]:
                require_web_url(member["url"], f"content/team.json → {member['name']}.url")
            validate_member_photo(member)
    if len(set(section_ids)) != len(section_ids):
        raise BuildError("content/team.json: gli id delle sezioni devono essere diversi.")

    # Contact cards and the postal address
    require_fields(contact, "content/contact.json", {
        "introduction": str, "contacts": list, "location": dict,
    })
    for person in contact["contacts"]:
        require_fields(person, "content/contact.json → contacts", {
            "role": str, "name": str, "email": str,
        })
    require_fields(contact["location"], "content/contact.json → location", {
        "eyebrow": str, "title": str, "address_lines": list, "url": str,
        "link_label": str, "seminar_venue_title": str, "seminar_venue": str,
        "seminar_link_label": str,
    })
    require_text_list(contact["location"]["address_lines"], "content/contact.json → location.address_lines")
    require_web_url(contact["location"]["url"], "content/contact.json → location.url")
    validate_seminar(sources["seminar"])


def validate_member_photo(member):
    """Prefer live HTTPS portraits; allow a local copy when direct loading fails."""
    photo = member.get("photo")
    location = f"content/team.json → {member['name']}.photo"
    if photo is None:
        return
    message = f"{location}: usa un indirizzo completo https:// senza credenziali, un'immagine in assets/images/members/ oppure null."
    if not isinstance(photo, str):
        raise BuildError(message)
    if photo.startswith("assets/images/members/"):
        path = PurePosixPath(photo)
        if (".." in path.parts or any(character in photo for character in "\\:%?#")
                or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}):
            raise BuildError(message)
        try:
            image = (ROOT / path).resolve()
            image_folder = (ROOT / "assets/images/members").resolve()
            if not image.is_relative_to(image_folder):
                raise BuildError(message)
            if not image.is_file():
                raise BuildError(f"{location}: immagine non trovata: {photo}")
        except (OSError, ValueError, RuntimeError) as error:
            raise BuildError(message) from error
        return
    if re.search(r"\s", photo) or "\\" in photo:
        raise BuildError(message)
    try:
        parts = urlsplit(photo)
        valid = (parts.scheme == "https" and parts.hostname
                 and parts.username is None and parts.password is None)
        parts.port  # Reject malformed or out-of-range ports as well.
    except ValueError as error:
        raise BuildError(message) from error
    if not valid:
        raise BuildError(message)


# Seminar dates and derived views


def parse_session_date(value, location):
    """Require an unambiguous, valid calendar date such as 2026-10-12."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise BuildError(f"{location}: usa il formato YYYY-MM-DD, per esempio 2026-10-12.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise BuildError(f"{location}: la data '{value}' non esiste nel calendario.") from error


def validate_seminar(seminar):
    """Keep the calendar, home summary and archive on one validated source."""
    location = "content/seminar.json"
    require_fields(seminar, location, {
        "introduction": str, "organizers": list, "mailing_list_note": str,
        "venue": dict, "labels": dict, "sessions": list,
    })
    require_fields(seminar["venue"], location + " → venue", {
        "name": str, "url": str, "building": str, "room": str,
    })
    require_web_url(seminar["venue"]["url"], location + " → venue.url")
    require_fields(seminar["labels"], location + " → labels", dict.fromkeys((
        "organizers", "location", "next_session", "schedule", "history",
        "academic_year", "abstract", "room", "home_next_session",
        "empty_next_session", "empty_programme",
    ), str))

    # Organizer links and email addresses
    for index, organizer in enumerate(seminar["organizers"]):
        where = f"{location} → organizers[{index}]"
        require_fields(organizer, where, {
            "name": str, "email": str, "url": (str, type(None)),
        })
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", organizer["email"]):
            raise BuildError(f"{where}.email: inserisci un indirizzo email valido.")
        if organizer["url"]:
            require_web_url(organizer["url"], where + ".url")

    # A date appears once; multiple talks belong to that same session.
    seen_dates = set()
    for index, session in enumerate(seminar["sessions"]):
        where = f"{location} → sessions[{index}]"
        require_fields(session, where, {"date": str, "room": str, "talks": list})
        session_date = parse_session_date(session["date"], where + ".date")
        if session_date in seen_dates:
            raise BuildError(f"{where}.date: la data {session['date']} è già presente; aggiungi gli interventi alla stessa sessione.")
        seen_dates.add(session_date)
        for talk_index, talk in enumerate(session["talks"]):
            talk_where = f"{where} → talks[{talk_index}]"
            require_fields(talk, talk_where, {
                "time": str, "speaker": str, "title": str, "abstract": list,
            })
            if talk["time"] and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", talk["time"]):
                raise BuildError(f"{talk_where}.time: usa un orario HH:MM, per esempio 10:00, oppure un testo vuoto.")
            if not all(isinstance(paragraph, str) for paragraph in talk["abstract"]):
                raise BuildError(f"{talk_where}.abstract: usa un elenco di paragrafi di testo, oppure [].")


def academic_year_start(day):
    """An academic year runs from 1 September through 31 August."""
    return day.year if day.month >= 9 else day.year - 1


def plan_seminar(seminar, today=None):
    """Derive every view from the same dates; an explicit date makes checks repeatable."""
    today = today or date.today()
    sessions = sorted(seminar["sessions"], key=lambda session: session["date"])
    upcoming = [session for session in sessions if date.fromisoformat(session["date"]) >= today]
    year = academic_year_start(today)
    calendar = [
        session for session in sessions
        if academic_year_start(date.fromisoformat(session["date"])) == year
    ]
    history = {}
    for session in reversed(sessions):
        session_day = date.fromisoformat(session["date"])
        if session_day < today and session["talks"]:
            history.setdefault(academic_year_start(session_day), []).append(session)
    return {
        "next": upcoming[0] if upcoming else None,
        "upcoming": upcoming,
        "calendar": calendar,
        "academic_year": year,
        "history": history,
    }


def session_date_label(session, labels, home=False):
    """Format one date and room label for the home or seminar page."""
    day = date.fromisoformat(session["date"])
    if home:
        text = f"{day.day} {MONTH_NAMES[day.month - 1]} {day.year}"
        separator = " · "
    else:
        text = day.strftime("%d/%m/%Y")
        separator = " — "
    if session["room"]:
        text += separator + labels["room"] + " " + session["room"]
    return text


# HTML template parsing and rendering
# The template language is deliberately small: dictionary keys, loops and if.
# It never evaluates Python, calls functions, or inserts unescaped JSON as HTML.
FIELD = r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*"
TOKENS = re.compile(r"({{.*?}}|{%.*?%})", re.DOTALL)


def field_value(expression, context):
    """Resolve a dotted field name through dictionaries, without executing code."""
    if not re.fullmatch(FIELD, expression):
        raise BuildError(f"Invalid template field: {expression!r}")
    value = context
    for key in expression.split("."):
        if not isinstance(value, dict) or key not in value:
            raise BuildError(f"Unknown template field: {expression}")
        value = value[key]
    return value


def parse_template(source):
    """Parse the supported fields, loops and conditions into nested nodes."""
    tokens = TOKENS.split(source)
    cursor = 0

    def parse_block(stops=()):
        nonlocal cursor
        nodes = []
        while cursor < len(tokens):
            token = tokens[cursor]
            cursor += 1
            if token.startswith("{{") and token.endswith("}}"):
                field = token[2:-2].strip()
                if not re.fullmatch(FIELD, field):
                    raise BuildError(f"Invalid template field: {field!r}")
                nodes.append(("field", field))
            elif token.startswith("{%") and token.endswith("%}"):
                command = token[2:-2].strip()
                if command in stops:
                    return nodes, command
                loop = re.fullmatch(rf"for ([A-Za-z][A-Za-z0-9_]*) in ({FIELD})", command)
                condition = re.fullmatch(rf"if ({FIELD})", command)
                if loop:
                    children, ending = parse_block(("endfor",))
                    if ending != "endfor":
                        raise BuildError("A template for block is missing {% endfor %}.")
                    nodes.append(("for", loop[1], loop[2], children))
                elif condition:
                    yes, ending = parse_block(("else", "endif"))
                    no = []
                    if ending == "else":
                        no, ending = parse_block(("endif",))
                    if ending != "endif":
                        raise BuildError("A template if block is missing {% endif %}.")
                    nodes.append(("if", condition[1], yes, no))
                else:
                    raise BuildError(f"Unsupported or misplaced template command: {command!r}")
            else:
                if "{{" in token or "{%" in token:
                    raise BuildError("Unclosed template placeholder or command.")
                nodes.append(("text", token))
        return nodes, None

    nodes, _ = parse_block()
    return nodes


def render_nodes(nodes, context):
    """Render parsed nodes, escaping every value inserted into HTML."""
    output = []
    for node in nodes:
        kind = node[0]
        if kind == "text":
            output.append(node[1])
        elif kind == "field":
            value = field_value(node[1], context)
            if isinstance(value, (dict, list)):
                raise BuildError(f"Template field must be text: {node[1]}")
            output.append(html.escape("" if value is None else str(value), quote=True))
        elif kind == "if":
            branch = node[2] if field_value(node[1], context) else node[3]
            output.append(render_nodes(branch, context))
        elif kind == "for":
            values = field_value(node[2], context)
            if not isinstance(values, list):
                raise BuildError(f"Template loop must use a list: {node[2]}")
            for index, value in enumerate(values):
                local = dict(context)
                local[node[1]] = value
                local["loop"] = {
                    "first": index == 0, "last": index == len(values) - 1,
                    "index": index + 1,
                }
                output.append(render_nodes(node[3], local))
    return "".join(output)


def render_html(source, context):
    """Expand one complete HTML page with its prepared data."""
    return render_nodes(parse_template(source), context)


# Prepare page data without generating HTML markup


def prepare_programme(seminar, plan):
    """Prepare display labels, calendar columns and archive groups for the HTML."""
    labels = seminar["labels"]

    def session_data(session):
        return {
            **session,
            "date_label": session_date_label(session, labels),
            "date_home_label": session_date_label(session, labels, home=True),
            "talks": [
                {**talk, "meta": " · ".join(
                    text for text in (talk["time"], talk["speaker"]) if text
                )}
                for talk in session["talks"]
            ],
        }

    # Split the academic-year calendar into two columns.
    dates = [date.fromisoformat(session["date"]).strftime("%d/%m/%Y")
             for session in plan["calendar"]]
    midpoint = (len(dates) + 1) // 2
    year = plan["academic_year"]
    return {
        "next": session_data(plan["next"]) if plan["next"] else None,
        "upcoming": [
            session_data(session) for session in plan["upcoming"]
            if session is plan["next"] or session["talks"]
        ],
        "calendar": [
            {"left": dates[index],
             "right": dates[midpoint + index] if midpoint + index < len(dates) else ""}
            for index in range(midpoint)
        ],
        "academic_year": year,
        "schedule_description": f"Seminar dates for academic year {year}–{year + 1}",
        "history": [
            {
                "id": f"seminar-archive-{index}",
                "title": f"{labels['academic_year']} {archive_year} – {archive_year + 1}",
                "sessions": [session_data(session) for session in sessions],
            }
            for index, (archive_year, sessions) in enumerate(plan["history"].items())
        ],
    }


def prepare_team(team, prefix):
    """Prepare initials, portrait paths and searchable member text."""
    sections = []
    for section in team["sections"]:
        members = []
        for member in section["members"]:
            parts = member["name"].split()
            initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper() if parts else ""
            photo = member.get("photo") or ""
            members.append({
                **member, "initials": initials,
                "photo_url": prefix + photo if photo.startswith("assets/images/members/") else photo,
                "search_text": " ".join((member["name"], member["affiliation"], section["title"])),
            })
        sections.append({**section, "members": members})
    return {**team, "sections": sections,
            "member_count": sum(len(section["members"]) for section in sections)}


def page_context(page, prefix, sources, seminar_plan):
    """Collect page data; all HTML markup remains in pages/."""
    site = sources["site"]
    home = sources["home"]
    return {
        **sources,
        "site": site, "page": page, "prefix": prefix,
        "navigation": [
            {"title": item["title"], "href": prefix + item["path"],
             "is_current": item["id"] == page["id"]}
            for item in site["pages"]
        ],
        "home": {**home, "research": [
            {**feature, "number": f"{index:02}"}
            for index, feature in enumerate(home["research"], start=1)
        ]},
        "team": prepare_team(sources["team"], prefix),
        "programme": prepare_programme(sources["seminar"], seminar_plan),
    }


def render_document(page, prefix, sources, seminar_plan):
    """Render a source page and include its filename in any template error."""
    path = PAGES / f"{page['id']}.html"
    try:
        return render_html(read_text(path), page_context(page, prefix, sources, seminar_plan))
    except BuildError as error:
        raise BuildError(f"{path}: {error}") from error


# Generate the public/ folder used by the preview and GitHub Pages


def build(output=DEFAULT_OUTPUT, today=None):
    """Render four pages and their existing English aliases before writing."""
    output = Path(output).resolve()
    protected = [CONTENT, PAGES, ROOT / "tools", ROOT / "assets", ROOT / "tests",
                 ROOT / "docs", ROOT / ".github", ROOT / ".vscode", ROOT / ".git"]
    if ROOT.is_relative_to(output) or any(output.is_relative_to(path) for path in protected):
        raise BuildError("Output must be separate from the source files, for example public/.")

    # Validate all data before generating any files.
    sources = {name: read_json(name) for name in ("site", "home", "team", "contact", "seminar")}
    validate_content(sources)
    seminar_plan = plan_seminar(sources["seminar"], today)
    if not (ROOT / "assets").is_dir():
        raise BuildError(f"Missing source folder: {ROOT / 'assets'}")

    # Render both the main routes and the existing English aliases.
    documents = []
    for page in sources["site"]["pages"]:
        route = page["path"]
        depth = len(PurePosixPath(route).parts)
        prefix = "../" * depth if depth else "./"
        documents.append((Path(route) / "index.html",
                          render_document(page, prefix, sources, seminar_plan)))
        documents.append((Path("en") / route / "index.html",
                          render_document(page, "../" * (depth + 1), sources, seminar_plan)))

    # Write only after every page has rendered successfully.
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "assets", output / "assets", dirs_exist_ok=True)
    for relative_path, document in documents:
        destination = output / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(document, encoding="utf-8")
    (output / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Site generated in: {output}")
    print("4 complete HTML pages + 4 English aliases; former members remain visible.")
    return output


# Command-line entry point


def main(argv=None):
    """Read command-line options and report build errors."""
    parser = argparse.ArgumentParser(description="Build ParMA from pages/ and content/.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Output folder (default: public/).")
    arguments = parser.parse_args(argv)
    try:
        build(arguments.output)
    except (BuildError, OSError, UnicodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
