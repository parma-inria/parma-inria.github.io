"""Generate public/ from editable content, HTML templates and static assets.

Uses Python's standard library only. Run from any folder:
    python tools/build.py
    python tools/build.py --output path/to/preview

Templates use string.Template placeholders ($name or ${name}). JSON text is
escaped before insertion; only generated HTML fragments are inserted as HTML.
"""

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path, PurePosixPath
from datetime import date
from string import Template
from textwrap import indent
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
DEFAULT_OUTPUT = ROOT / "public"
PAGE_IDS = {"home", "team", "seminar", "contact"}
MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
)


class BuildError(Exception):
    """An editable source is missing or invalid."""


def read_text(path):
    """Read a source file and explain missing files in Italian."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise BuildError(f"File sorgente mancante: {path}") from error


def read_json(name):
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
    for index, organizer in enumerate(seminar["organizers"]):
        where = f"{location} → organizers[{index}]"
        require_fields(organizer, where, {
            "name": str, "email": str, "url": (str, type(None)),
        })
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", organizer["email"]):
            raise BuildError(f"{where}.email: inserisci un indirizzo email valido.")
        if organizer["url"]:
            require_web_url(organizer["url"], where + ".url")
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


def escape(value):
    return html.escape(str(value), quote=True)


def escaped_fields(data):
    """Prepare an object whose values are plain text for an HTML template."""
    return {key: escape(value) for key, value in data.items()}


def text_lines(lines):
    """Explicit line breaks in headings and addresses, without editable HTML."""
    return "<br>".join(escape(line) for line in lines)


def render_template(template_name, **values):
    path = TEMPLATES / template_name
    try:
        return Template(read_text(path)).substitute(values).rstrip()
    except (KeyError, ValueError) as error:
        raise BuildError(f"Modello non valido: {path}. Segnaposto: {error}") from error


def render_header(page_id, prefix, site):
    links = []
    for page in site["pages"]:
        current = ' aria-current="page"' if page["id"] == page_id else ""
        links.append(f'<a href="{escape(prefix + page["path"])}"{current}>{escape(page["title"])}</a>')
    return render_template(
        "partials/header.html",
        prefix=prefix,
        site_name=escape(site["name"]),
        brand_caption=escape(site["brand_caption"]),
        skip_label=escape(site["skip_label"]),
        menu_label=escape(site["menu_label"]),
        navigation_label=escape(site["navigation_label"]),
        navigation_links=indent("\n".join(links), "      "),
    )


def render_hero(page, prefix, home):
    actions = ""
    if page["id"] == "home":
        actions = indent(render_template(
            "partials/hero-actions.html", prefix=prefix,
            **escaped_fields(home["hero_actions"]),
        ), "    ")
    hero = page["hero"]
    return render_template(
        "partials/hero.html",
        hero_class="hero hero-home" if page["id"] == "home" else "hero",
        eyebrow=escape(hero["eyebrow"]),
        title=text_lines(hero["title_lines"]),
        lead=escape(hero["lead"]),
        actions=actions,
    )


def render_footer(prefix, site):
    footer = site["footer"]
    links = [
        f'<a href="{escape(link["url"])}">{escape(link["label"])}</a>'
        for link in footer["links"]
    ]
    return render_template(
        "partials/footer.html",
        prefix=prefix, site_name=escape(site["name"]),
        tagline=escape(footer["tagline"]), note=escape(footer["note"]),
        links_label=escape(footer["links_label"]),
        institutional_links=indent("\n".join(links), "      "),
    )


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


def render_home(prefix, home, seminar, plan):
    paragraphs = []
    for index, paragraph in enumerate(home["introduction"]):
        style = ' class="lead"' if index == 0 else ""
        paragraphs.append(f"<p{style}>{escape(paragraph)}</p>")
    cards = [
        render_template("partials/research-card.html", number=f"{index:02}", **escaped_fields(feature))
        for index, feature in enumerate(home["research"], start=1)
    ]
    next_session = plan["next"]
    labels = seminar["labels"]
    talks = []
    if next_session:
        for talk in next_session["talks"]:
            meta = " · ".join(value for value in (talk["time"], talk["speaker"]) if value)
            talks.append(render_template(
                "partials/next-session-talk.html", meta=escape(meta),
                title="<br>" + escape(talk["title"]) if talk["title"] else "",
            ))
        if not talks:
            talks.append(f'<p>{escape(labels["empty_programme"])}</p>')
    else:
        talks.append(f'<p>{escape(labels["empty_next_session"])}</p>')
    next_session_date = (
        f'<p class="session-date">{escape(session_date_label(next_session, labels, home=True))}</p>'
        if next_session else ""
    )
    home_seminar = home["seminar"]
    return render_template(
        "pages/home.html",
        prefix=prefix,
        about_eyebrow=escape(home["about_eyebrow"]),
        about_title=text_lines(home["about_title_lines"]),
        introduction=indent("\n".join(paragraphs), "    "),
        logo_alt=escape(home["logo_alt"]), logo_caption=escape(home["logo_caption"]),
        research_title=escape(home["research_title"]),
        research_cards=indent("\n".join(cards), "    "),
        seminar_eyebrow=escape(home_seminar["eyebrow"]), seminar_title=escape(home_seminar["title"]),
        seminar_description=escape(home_seminar["description"]),
        seminar_link_label=escape(home_seminar["link_label"]),
        next_session_date=indent(next_session_date, "    "),
        next_session_title=escape(labels["home_next_session"]),
        next_session_talks=indent("\n".join(talks), "    "),
    )


def render_seminar_talk(talk, labels):
    meta_parts = []
    if talk["time"]:
        meta_parts.append(f'<strong>{escape(talk["time"])}</strong>')
    if talk["speaker"]:
        meta_parts.append(f'<span>{escape(talk["speaker"])}</span>')
    meta = f'<p class="talk-meta">{" ".join(meta_parts)}</p>' if meta_parts else ""
    title = f'<p class="talk-title">{escape(talk["title"])}</p>' if talk["title"] else ""
    abstract = ""
    if talk["abstract"]:
        paragraphs = "<br><br>".join(escape(paragraph) for paragraph in talk["abstract"])
        abstract = (
            f'<span class="abstract-label">{escape(labels["abstract"])}</span>\n'
            f'<div class="abstract-text">{paragraphs}</div>'
        )
    return render_template(
        "partials/seminar-talk.html", meta=indent(meta, "  "),
        title=indent(title, "  "), abstract=indent(abstract, "  "),
    )


def render_seminar_session(session, labels, upcoming=False):
    talks = [render_seminar_talk(talk, labels) for talk in session["talks"]]
    if not talks:
        talks.append(f'<p>{escape(labels["empty_programme"])}</p>')
    return render_template(
        "partials/seminar-session.html",
        upcoming=' data-upcoming="true"' if upcoming else "",
        heading_level=3 if upcoming else 4,
        date=escape(session_date_label(session, labels)),
        talks=indent("\n".join(talks), "  "),
    )


def render_seminar(seminar, plan):
    labels = seminar["labels"]
    organizers = []
    for organizer in seminar["organizers"]:
        name = escape(organizer["name"])
        if organizer["url"]:
            name = f'<a href="{escape(organizer["url"])}" target="_blank" rel="noopener noreferrer">{name}</a>'
        organizers.append(render_template(
            "partials/seminar-organizer.html", name=name, email=escape(organizer["email"]),
        ))
    # Show later announced talks too, even when an earlier date has no programme yet.
    upcoming = [
        render_seminar_session(session, labels, upcoming=True)
        for session in plan["upcoming"]
        if session is plan["next"] or session["talks"]
    ]
    if not upcoming:
        upcoming.append(f'<p>{escape(labels["empty_next_session"])}</p>')
    # Two chronological columns keep the established compact calendar layout.
    dates = [date.fromisoformat(session["date"]).strftime("%d/%m/%Y") for session in plan["calendar"]]
    midpoint = (len(dates) + 1) // 2
    rows = []
    for index in range(midpoint):
        right = dates[midpoint + index] if midpoint + index < len(dates) else ""
        rows.append(f"<tr><td>{dates[index]}</td><td>{right}</td></tr>")
    if not rows:
        rows.append(f'<tr><td colspan="2">{escape(labels["empty_next_session"])}</td></tr>')
    years = []
    for index, (year, sessions) in enumerate(plan["history"].items()):
        years.append(render_template(
            "partials/seminar-archive-year.html", archive_id=f"seminar-archive-{index}",
            title=escape(f"{labels['academic_year']} {year} – {year + 1}"),
            sessions=indent("\n\n".join(render_seminar_session(session, labels) for session in sessions), "  "),
        ))
    venue = seminar["venue"]
    year = plan["academic_year"]
    return render_template(
        "pages/seminar.html", introduction=escape(seminar["introduction"]),
        organizers_label=escape(labels["organizers"]),
        organizers=indent("\n".join(organizers), "      "),
        mailing_list_note=escape(seminar["mailing_list_note"]),
        location_label=escape(labels["location"]), venue_name=escape(venue["name"]),
        venue_url=escape(venue["url"]), building=escape(venue["building"]),
        room_label=escape(labels["room"]), room=escape(venue["room"]),
        next_session_label=escape(labels["next_session"]),
        next_sessions=indent("\n\n".join(upcoming), "  "),
        schedule_label=escape(labels["schedule"]),
        schedule_description=escape(f"Seminar dates for academic year {year}–{year + 1}"),
        calendar_rows=indent("\n".join(rows), "      "),
        history_label=escape(labels["history"]), archive_years=indent("\n\n".join(years), "  "),
    )


def render_team(prefix, team):
    sections = []
    for section in team["sections"]:
        cards = []
        for member in section["members"]:
            name = escape(member["name"])
            if member["url"]:
                name = f'<a href="{escape(member["url"])}">{name}</a>'
            name_parts = member["name"].split()
            initials = (name_parts[0][0] + (name_parts[-1][0] if len(name_parts) > 1 else "")).upper() if name_parts else ""
            portrait = (
                '<span class="member-photo" aria-hidden="true">'
                f'<span class="member-initials">{escape(initials)}</span>'
            )
            if member.get("photo"):
                photo = member["photo"]
                photo_url = prefix + photo if photo.startswith("assets/images/members/") else photo
                portrait += (
                    f'<img class="member-portrait" data-member-portrait="{escape(member["name"])}" '
                    f'src="{escape(photo_url)}" '
                    'alt="" width="64" height="64" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
                )
            portrait += '</span>'
            search_text = " ".join([member["name"], member["affiliation"], section["title"]])
            cards.append(render_template(
                "partials/member-card.html", name=name,
                portrait=portrait,
                affiliation=escape(member["affiliation"]), search_text=escape(search_text),
            ))
        # Former members use the same visible section as every other category.
        sections.append(render_template(
            "partials/member-section.html", section_id=escape(section["id"]),
            title=escape(section["title"]), member_cards=indent("\n".join(cards), "    "),
        ))
    search = team["search"]
    return render_template(
        "pages/team.html", introduction=escape(team["introduction"]),
        search_label=escape(search["label"]), search_placeholder=escape(search["placeholder"]),
        count_label=escape(search["count_label"]), empty_message=escape(search["empty_message"]),
        member_count=sum(len(section["members"]) for section in team["sections"]),
        member_sections="\n\n".join(sections),
    )


def render_contact(prefix, contact):
    cards = [
        render_template("partials/contact-card.html", **escaped_fields(person))
        for person in contact["contacts"]
    ]
    location = contact["location"]
    return render_template(
        "pages/contact.html", prefix=prefix,
        introduction=escape(contact["introduction"]),
        contact_cards=indent("\n".join(cards), "  "),
        location_eyebrow=escape(location["eyebrow"]), location_title=escape(location["title"]),
        address=text_lines(location["address_lines"]), location_url=escape(location["url"]),
        location_link_label=escape(location["link_label"]),
        seminar_venue_title=escape(location["seminar_venue_title"]),
        seminar_venue=escape(location["seminar_venue"]),
        seminar_link_label=escape(location["seminar_link_label"]),
    )


def render_document(page, prefix, sources, seminar_html, seminar_plan):
    page_id = page["id"]
    if page_id == "home":
        body = render_home(prefix, sources["home"], sources["seminar"], seminar_plan)
    elif page_id == "team":
        body = render_team(prefix, sources["team"])
    elif page_id == "contact":
        body = render_contact(prefix, sources["contact"])
    else:
        body = seminar_html.rstrip()
    site = sources["site"]
    return render_template(
        "layout.html", prefix=prefix,
        language=escape(site["language"]), page_title=escape(page["title"]),
        site_name=escape(site["name"]), description=escape(page["description"]),
        theme_color=escape(site["theme_color"]),
        header=indent(render_header(page_id, prefix, site), "    "),
        hero=indent(render_hero(page, prefix, sources["home"]), "    "),
        body=indent(body, "      "), footer=indent(render_footer(prefix, site), "    "),
    ) + "\n"


def build(output=DEFAULT_OUTPUT, today=None):
    """Build eight entry points. Existing files are overwritten, never deleted."""
    output = Path(output).resolve()
    protected = [ROOT, CONTENT, TEMPLATES, ROOT / "tools", ROOT / "assets"]
    if output == ROOT or any(output.is_relative_to(path) for path in protected[1:]):
        raise BuildError("La cartella di output deve essere separata dai file sorgente, per esempio public/.")
    sources = {name: read_json(name) for name in ("site", "home", "team", "contact", "seminar")}
    validate_content(sources)
    seminar_plan = plan_seminar(sources["seminar"], today)
    seminar_html = render_seminar(sources["seminar"], seminar_plan)
    if not (ROOT / "assets").is_dir():
        raise BuildError(f"Cartella sorgente mancante: {ROOT / 'assets'}")

    # Render everything before writing, so template errors leave the output intact.
    documents = []
    for page in sources["site"]["pages"]:
        path = page["path"]
        depth = len(PurePosixPath(path).parts)
        prefix = "../" * depth if depth else "./"
        documents.append((Path(path) / "index.html", render_document(page, prefix, sources, seminar_html, seminar_plan)))
        english_prefix = "../" * (depth + 1)
        documents.append((Path("en") / path / "index.html", render_document(page, english_prefix, sources, seminar_html, seminar_plan)))

    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "assets", output / "assets", dirs_exist_ok=True)
    for relative_path, document in documents:
        destination = output / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(document, encoding="utf-8")
    (output / ".nojekyll").write_text("", encoding="utf-8")
    count = sum(len(section["members"]) for section in sources["team"]["sections"])
    print(f"Sito generato in: {output}")
    print(f"4 pagine + 4 alias inglesi; {count} membri, compresi gli ex membri sempre visibili.")
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description="Genera il sito ParMA dai contenuti e dai modelli HTML.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Cartella di destinazione (default: public/).")
    arguments = parser.parse_args(argv)
    try:
        build(arguments.output)
    except (BuildError, OSError, UnicodeError) as error:
        print(f"Errore: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
