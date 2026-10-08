"""Build the ParMA website. Python 3 standard library only."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = json.loads((ROOT / 'data/site.json').read_text(encoding='utf-8'))
MEMBERS = json.loads((ROOT / 'data/members.json').read_text(encoding='utf-8'))


def esc(value):
    return html.escape(str(value), quote=True)


PAGES = [('home', '', 'Presentation'), ('team', 'team-members/', 'Team'),
         ('seminar', 'francais-gdt-edp-ot-ml/', 'GdT OT–PDE–ML'), ('contact', 'contact/', 'Contact')]


def header(key, prefix):
    nav = ''.join(f'<a href="{prefix}{path}"' + (' aria-current="page"' if page == key else '')
                  + f'>{label}</a>' for page, path, label in PAGES)
    return f'''<a class="skip-link" href="#main">Skip to content</a>
<header class="site-header"><div class="container header-row">
<a class="brand" href="{prefix}"><span class="brand-mark">ParMA<span class="brand-dot" aria-hidden="true">.</span></span><span class="brand-caption">Optimal transport &amp; particle methods</span></a>
<button class="menu-toggle" type="button" aria-controls="site-navigation" aria-expanded="false" hidden>Menu</button>
<nav id="site-navigation" class="site-navigation" aria-label="Main navigation">{nav}</nav>
</div></header>'''


def hero(key, prefix):
    eyebrow, title, lead = {
        'home': ('INRIA SACLAY · CNRS · UNIVERSITÉ PARIS-SACLAY',
                 'Optimal transport.<br>From theory to particles.',
                 'Exploring the geometry of probability distributions and the motion of particles.'),
        'team': ('THE PEOPLE BEHIND ParMA', 'Team members',
                 'Researchers, engineers and PhD students working across mathematics and scientific computing.'),
        'seminar': ('OPTIMAL TRANSPORT · PDE · MACHINE LEARNING', 'GdT OT–PDE–ML',
                    'A research seminar at the crossroads of transport, equations and learning.'),
        'contact': ('GET IN TOUCH', 'Contact ParMA',
                    'Find the team at the Institut de Mathématique d’Orsay, Université Paris-Saclay.')
    }[key]
    actions = f'<div class="hero-actions"><a class="button" href="{prefix}team-members/">Meet the team</a><a class="button button-secondary" href="{prefix}francais-gdt-edp-ot-ml/">Explore the seminar</a></div>' if key == 'home' else ''
    return f'<section class="hero {"hero-home" if key == "home" else ""}" aria-labelledby="page-title"><div class="container hero-content"><p class="eyebrow">{eyebrow}</p><h1 id="page-title">{title}</h1><p class="hero-lead">{lead}</p>{actions}</div></section>'


def footer(prefix):
    return f'''<footer class="site-footer"><div class="container footer-grid"><div><a class="brand-mark" href="{prefix}">ParMA.</a><p>Optimal transport and motion of particles</p><p class="footer-note">A research team at Inria Saclay, in partnership with CNRS and Université Paris-Saclay.</p></div><nav class="footer-links" aria-label="Institutional links"><a href="https://www.inria.fr/en/inria-saclay-centre">Inria Saclay</a><a href="https://www.imo.universite-paris-saclay.fr/">Institut de Mathématique d’Orsay</a><a href="https://www.cnrs.fr/en">CNRS</a><a href="https://www.universite-paris-saclay.fr/en">Université Paris-Saclay</a><a href="https://team.inria.fr/parma/">Original Inria website</a></nav></div></footer>'''


def document(key, body, prefix):
    title = next(label for page, _, label in PAGES if page == key)
    description = {'home': SITE['description'], 'team': 'Meet the ParMA research team: permanent researchers, engineers, postdoctoral researchers, PhD students and former members.', 'seminar': 'Program, abstracts and archives of the ParMA GdT OT–PDE–ML seminar at the Institut de Mathématique d’Orsay.', 'contact': 'Contact the ParMA team at Inria Saclay and Université Paris-Saclay.'}[key]
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(title)} · ParMA</title><meta name="description" content="{esc(description)}"><meta name="theme-color" content="#06365a"><link rel="icon" href="{prefix}assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="{prefix}assets/site.css"><script src="{prefix}assets/site.js" defer></script></head><body>
{header(key, prefix)}{hero(key, prefix)}<main id="main" class="container content-container">{body}</main>{footer(prefix)}
</body></html>\n'''


def home(prefix):
    paragraphs = ''.join(f'<p{chr(32) + "class=\"lead\"" if i == 0 else ""}>{esc(p)}</p>' for i, p in enumerate(SITE['introduction']))
    features = ''.join(f'<article class="feature-card"><span class="feature-number" aria-hidden="true">0{i+1}</span><h3>{esc(f["title"])}</h3><p>{esc(f["text"])}</p></article>' for i, f in enumerate(SITE['research']))
    return f'''<div class="home-grid"><section class="home-copy" aria-labelledby="about-title"><p class="eyebrow">RESEARCH IN MOTION</p><h2 id="about-title" class="section-heading">Optimal transport theory<br>and applications</h2>{paragraphs}</section><aside class="home-visual"><img class="parma-logo" src="{prefix}assets/parma-logo.png" width="1024" height="437" alt="ParMA logo formed by a cloud of particles"><p>Geometry, probability and computation.</p></aside></div>
<section aria-labelledby="research-title"><h2 id="research-title" class="section-heading">From mathematical ideas to computational tools</h2><div class="feature-grid">{features}</div></section>
<section class="home-seminar" aria-labelledby="seminar-title"><div><p class="eyebrow">OUR RESEARCH SEMINAR</p><h2 id="seminar-title" class="section-heading">GdT OT–PDE–ML</h2><p>Recent theoretical and numerical developments in optimal transport, partial differential equations and machine learning.</p><a class="small-link" href="{prefix}francais-gdt-edp-ot-ml/">Program and session archive <span aria-hidden="true">→</span></a></div><article class="info-card"><p class="session-date">12 October 2026 · Room 3L15</p><h3>Next session</h3><p><strong>10:00 · Hugo Koubbi</strong><br>Homogenized Transformers</p><p><strong>11:00 · Alice Le Brigant</strong><br>On the Wasserstein Geodesic Principal Component Analysis of probability measures</p></article></section>'''


def team(prefix):
    sections = []
    for index, section in enumerate(MEMBERS):
        cards = []
        for person in section['members']:
            name = esc(person['name'])
            if person.get('url'):
                name = f'<a href="{esc(person["url"])}">{name}</a>'
            search = esc(person['name'] + ' ' + person['affiliation'] + ' ' + section['title'])
            cards.append(f'<li class="member-card" data-search="{search}"><p class="member-name">{name}</p><p class="member-affiliation">{esc(person["affiliation"])}</p></li>')
        slug = 'former-members' if section['title'] == 'Former members' else 'member-section-' + str(index)
        sections.append(f'<section class="member-section" aria-labelledby="{slug}"><h2 id="{slug}" class="section-heading">{esc(section["title"])}</h2><ul class="member-grid">{"".join(cards)}</ul></section>')
    count = sum(len(section['members']) for section in MEMBERS)
    return f'''<p class="intro-callout">Meet the ParMA team: permanent researchers, research engineers, postdoctoral researchers and PhD students.</p><div class="members-toolbar" hidden><div><label for="member-search">Find a team member</label><input id="member-search" type="search" placeholder="Search by name, affiliation or role" autocomplete="off"></div><p id="member-count" aria-live="polite">{count} members</p></div><p class="empty-state" hidden>No members match your search.</p>{"".join(sections)}'''


def contact(prefix):
    cards = ''.join(f'<article class="info-card"><p class="contact-role">{esc(p["role"])}</p><h2 class="contact-name">{esc(p["name"])}</h2><a href="mailto:{esc(p["email"])}">{esc(p["email"])}</a></article>' for p in SITE['contacts'])
    address = '<br>'.join(esc(line) for line in SITE['address'])
    return f'''<p class="intro-callout">For research enquiries, collaborations and information about ParMA, contact the team below.</p><div class="info-grid">{cards}</div><section class="address-card" aria-labelledby="location-title"><div><p class="eyebrow">VISIT THE TEAM</p><h2 id="location-title" class="section-heading">Institut de Mathématique d’Orsay</h2><address>{address}</address><a class="small-link" href="https://www.imo.universite-paris-saclay.fr/">Institut de Mathématique d’Orsay <span aria-hidden="true">↗</span></a></div><div class="location-note"><h3>Seminar venue</h3><p>Building 307 · Room 3L15</p><a href="{prefix}francais-gdt-edp-ot-ml/">See the seminar program</a></div></section>'''


def build():
    seminar = (ROOT / 'content/seminar.html').read_text(encoding='utf-8')
    bodies = {'home': home, 'team': team, 'seminar': lambda prefix: seminar, 'contact': contact}
    for key, path, _ in PAGES:
        folder = ROOT / path
        folder.mkdir(parents=True, exist_ok=True)
        prefix = './' if key == 'home' else '../'
        (folder / 'index.html').write_text(document(key, bodies[key](prefix), prefix), encoding='utf-8')
        # Preserve the site's existing English entry points without separate stale copies.
        en_folder = ROOT / 'en' / path
        en_folder.mkdir(parents=True, exist_ok=True)
        en_prefix = '../' if key == 'home' else '../../'
        (en_folder / 'index.html').write_text(document(key, bodies[key](en_prefix), en_prefix), encoding='utf-8')
    (ROOT / '.nojekyll').touch()
    print(f'Built 4 pages + 4 English aliases. {sum(len(s["members"]) for s in MEMBERS)} members preserved.')


if __name__ == '__main__':
    build()
