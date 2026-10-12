"""Check generated pages, images and local links without accessing the Internet."""

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

# Required English routes and the corresponding translated pages
ROOT = Path(__file__).resolve().parents[1]
PAGE_PATHS = (
    'index.html',
    'team-members/index.html',
    'gdt-ot-pde-ml/index.html',
    'resources/index.html',
    'contact/index.html',
)


# Collect links and anchor targets from HTML


class PageLinks(HTMLParser):
    """Collect link targets and section IDs from a generated HTML page."""

    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
        self.external_link_errors = []

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if attributes.get('id'):
            self.ids.add(attributes['id'])
        if tag == 'a':
            url = urlsplit(attributes.get('href', ''))
            if url.scheme in ('http', 'https') or url.netloc:
                rel = set(attributes.get('rel', '').split())
                if attributes.get('target') != '_blank' or not {'noopener', 'noreferrer'} <= rel:
                    self.external_link_errors.append(attributes['href'])
        for name in ('href', 'src'):
            if attributes.get(name):
                self.links.append(attributes[name])


# Check the generated site, never the editable source files


def check_site(output):
    """Return local-link errors without modifying files or checking external sites."""

    output = output.resolve()
    errors = []
    pages = {}

    # Every source page has English root/alias routes and French/Italian routes.
    expected = [prefix + path for prefix in ('', 'en/', 'fr/', 'it/') for path in PAGE_PATHS]
    for path in expected:
        if not (output / path).is_file():
            errors.append(f'Pagina mancante: {path}. Esegui prima la generazione.')

    # Parse every page before resolving cross-page section links.
    for file in output.rglob('*.html'):
        parser = PageLinks()
        parser.feed(file.read_text(encoding='utf-8'))
        pages[file.resolve()] = parser

    link_count = 0
    for file, page in pages.items():
        label = file.relative_to(output).as_posix()
        for link in page.external_link_errors:
            errors.append(f'{label}: external link must open safely in a new tab: {link}')
        for link in page.links:
            url = urlsplit(link)
            # External websites and email links are outside this local check.
            if url.scheme or url.netloc:
                continue
            target = output / unquote(url.path).lstrip('/') if url.path.startswith('/') else file.parent / unquote(url.path)
            if not url.path:
                target = file
            elif target.is_dir():
                target = target / 'index.html'
            target = target.resolve()
            link_count += 1
            label = file.relative_to(output).as_posix()
            if not target.is_relative_to(output) or not target.is_file():
                errors.append(f'{label}: collegamento locale non trovato: {link}')
            elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
                errors.append(f'{label}: sezione non trovata: {link}')

    # CSS images are relative to their stylesheet, rather than the HTML page.
    for file in output.rglob('*.css'):
        for link in re.findall(r'url\([\s\"\']*([^\)\"\']+)[\s\"\']*\)', file.read_text(encoding='utf-8')):
            if urlsplit(link).scheme or link.startswith('//'):
                continue
            target = (file.parent / unquote(urlsplit(link.strip()).path)).resolve()
            if not target.is_relative_to(output) or not target.is_file():
                errors.append(f'{file.relative_to(output)}: immagine CSS non trovata: {link}')

    if not errors:
        print(f'Controllo riuscito: {len(pages)} pagine e {link_count} collegamenti locali. Immagini CSS presenti.')
    return errors


# Command-line entry point


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'public', help='Cartella generata da controllare (default: public).')
    arguments = parser.parse_args()
    errors = check_site(arguments.output)
    for error in errors:
        print(f'Errore: {error}', file=sys.stderr)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
