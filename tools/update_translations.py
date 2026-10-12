"""Create French and Italian caches from English sources on GitHub's CPU runner.

The public build uses only the standard library and these committed JSON caches.
Model libraries are imported lazily: ordinary local builds never download a model.
Names, identifiers, URLs, code, and mathematical notation bypass the translator.
"""

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIRECTORY = ROOT / "content" / "translations"
SCHEMA_VERSION = 1
# Bump when segmentation or generation behavior changes, so old outputs regenerate.
ENGINE_VERSION = 2
MODELS = {
    "fr": {
        "id": "Helsinki-NLP/opus-mt-en-fr",
        "revision": "dd7f6540a7a48a7f4db59e5c0b9c42c8eea67f18",
    },
    "it": {
        "id": "Helsinki-NLP/opus-mt-en-it",
        "revision": "be5a254d936f1a8c8da080406ca582a6615e6658",
    },
}
CONTENT_NAMES = ("site", "home", "team", "seminar", "resources", "contact", "publications")
ENGLISH_MONTHS = (
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
)
# Calendar names are fixed locale formatting, not prose for a language model.
# In isolation, "May" or "March" can otherwise be interpreted as ordinary words.
CALENDAR_MONTHS = {
    "fr": dict(zip(ENGLISH_MONTHS, (
        "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre",
    ))),
    "it": dict(zip(ENGLISH_MONTHS, (
        "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre",
    ))),
}

# This allowlist deliberately excludes people, institutions, addresses, paths,
# affiliations, seminar talk titles, and all bibliographic publication records.
TEXT_PATHS = {
    "site": (
        "brand_caption", "skip_label", "menu_label", "navigation_label",
        "pages.*.title", "pages.*.description", "pages.*.hero.eyebrow",
        "pages.*.hero.title_lines.*", "pages.*.hero.lead",
        "footer.tagline", "footer.note", "footer.links_label", "map.title", "map.link_label",
    ),
    "home": (
        "hero_actions.*", "about_eyebrow", "about_title_lines.*",
        "introduction.*", "logo_alt", "logo_caption", "seminar.eyebrow",
        "seminar.description", "seminar.link_label",
    ),
    "team": ("search.*", "sections.*.title"),
    "seminar": ("mailing_list_note", "labels.*", "sessions.*.talks.*.abstract.*"),
    "resources": (
        "source_name", "repository_label", "sections.*.title", "sections.*.items.*.kind",
        "sections.*.items.*.description", "sections.*.items.*.links.*.label",
    ),
    "publications": ("title", "link_label", "empty_message"),
    "contact": (
        "contacts.*.role", "location.eyebrow", "location.seminar_venue_title",
        "location.seminar_link_label", "location.seminar_venue",
    ),
}
# Keep source text intentionally in its original language when it is not English.
# These are older French abstracts, rather than material authored in English.
FRENCH_MARKERS = {
    "dans", "cadre", "théorème", "contraction", "assure", "caractère", "entre",
    "une", "mesure", "proposons", "nous", "résultats", "régularisation",
    "problème", "transport", "optimal", "lorsque", "hypothèses", "l’application",
}
ENGLISH_MARKERS = {
    "the", "a", "we", "in", "of", "to", "and", "this", "is", "for", "that",
    "with", "which", "our", "by", "on", "from",
}
TECHNICAL_IDENTIFIERS = {
    "ParMA", "ParMa", "Inria", "INRIA", "CNRS", "IMO", "sd-ot", "sdot",
    "pysdot", "Python", "C++", "Conda", "GitHub", "Google Maps", "GdT",
    "OT–PDE–ML", "OT-PDE-ML", "OT", "PDE", "ML", "PCA", "MMD", "EOT",
    "UOT", "JKO", "SGD", "ODEs", "ResNet", "PDEs", "SW", "ISTA",
    "ReLU", "GMM", "MW_2", "W_2", "W₂", "P₂", "CEREMADE", "TSE",
    # Mathematical eponyms and author surnames are identifiers, not prose.
    "Acharya", "Alexandrov", "Baradat", "Benamou", "Brenier",
    "Brascamp-Lieb", "Brenier-McCann", "Brigati", "Brunn-Minkowski",
    "Bures-Wasserstein", "Burgers", "Böröczky", "Caffarelli", "Carlier",
    "Chewi", "Chiarini", "Cordero-Eurasquin", "Delon", "Dirac", "Diskant",
    "Dolbeault", "Euler", "Figalli-Maggi-Pratelli", "Fokker", "Fokker-Planck",
    "Gaussian", "Gozlan", "Greco", "Gromov-Wasserstein", "Hamiltonian",
    "Hausdorff", "Hellinger", "Hellinger-Kantorovich", "Hilbert", "Hilbertian",
    "Hraivoronska", "Kantorovich", "Kimura", "Klartag", "Kähler", "Langevin",
    "Liero", "Lipschitz", "Maas", "Mielke", "Minkowski", "Monge-Ampère",
    "Moran", "Nash", "Otto-Wasserstein", "Pauwels", "Planck",
    "Polyak-Łojasiewicz", "Pooladian", "Prekopa-Leindler", "Prékopa-Leindler",
    "Ramos", "Ricci", "Riemannian", "Riesz", "Santambrogio", "Sasakian",
    "Savaré", "Shahshahani", "Sinkhorn", "Tamanini", "Tanguy", "Wasserstein",
    "Carnegie Mellon", "Dauphine-PSL",
}


class TranslationError(Exception):
    """Translation or cache validation failed; publishing should stop."""


def empty_cache(language):
    if language not in MODELS:
        raise TranslationError(f"Unsupported translation language: {language}")
    return {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "language": language,
        "model": dict(MODELS[language]),
        "translations": {},
    }


def validate_cache(cache, language):
    """Reject corrupted caches; safely invalidate an older model revision."""
    if not isinstance(cache, dict):
        raise TranslationError("Translation cache must be a JSON object.")
    if cache.get("schema_version") != SCHEMA_VERSION or cache.get("language") != language:
        raise TranslationError(f"Invalid cache schema or language for {language}.")
    if not isinstance(cache.get("model"), dict) or not isinstance(cache.get("translations"), dict):
        raise TranslationError(f"Missing model or translations in {language} cache.")
    if cache.get("engine_version") != ENGINE_VERSION or cache["model"] != MODELS[language]:
        return empty_cache(language)
    for source, translated in cache["translations"].items():
        if (not isinstance(source, str) or not source.strip()
                or not isinstance(translated, str) or not translated.strip()):
            raise TranslationError(f"Invalid translation entry in {language} cache.")
        placeholders = r"\{[A-Za-z_][A-Za-z0-9_]*\}"
        if sorted(re.findall(placeholders, source)) != sorted(re.findall(placeholders, translated)):
            raise TranslationError(f"Changed UI placeholders in {language} cache.")
    fingerprint = cache.get("source_sha256")
    if fingerprint is not None and (
        not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint)
    ):
        raise TranslationError(f"Invalid source fingerprint in {language} cache.")
    return copy.deepcopy(cache)


def read_cache(language):
    """Missing caches use English locally; malformed caches remain explicit errors."""
    path = CACHE_DIRECTORY / f"{language}.json"
    if not path.exists():
        return empty_cache(language)
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TranslationError(f"Cannot read {path}: {error}") from error
    return validate_cache(cache, language)


def _matches(path, pattern):
    parts = pattern.split(".")
    return len(path) == len(parts) and all(
        expected == "*" or expected == str(actual)
        for actual, expected in zip(path, parts)
    )


def _text_locations(value, path=()):
    """Walk only explicitly permitted fields and the shared English UI catalogue."""
    if isinstance(value, str):
        if path and (path[0] == "ui" or any(
            _matches(path[1:], pattern)
            for pattern in TEXT_PATHS.get(path[0], ())
        )):
            yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _text_locations(item, path + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _text_locations(item, path + (index,))


def _needs_translation(text):
    stripped = text.strip()
    if not stripped or not re.search(r"[A-Za-z]", stripped):
        return False
    if stripped.startswith("Lorem ipsum") or stripped in {"TBA", "TBD"}:
        return False
    words = set(re.findall(r"[\w’]+", stripped.casefold()))
    # Existing French summaries are original quotations and stay untouched.
    if len(words & FRENCH_MARKERS) >= 4 and len(words & ENGLISH_MARKERS) <= 2:
        return False
    return True


def collect_texts(sources):
    """Deduplicate editable English prose in deterministic source order."""
    return list(dict.fromkeys(
        text for _, text in _text_locations(sources) if _needs_translation(text)
    ))


def localize_sources(sources, language, cache=None):
    """Return a deep copy; cache misses keep English until the next deployment."""
    localized = copy.deepcopy(sources)
    if language == "en":
        return localized
    cache = read_cache(language) if cache is None else validate_cache(cache, language)
    translations = cache["translations"]
    for path, source in _text_locations(localized):
        parent = localized
        for part in path[:-1]:
            parent = parent[part]
        parent[path[-1]] = translations.get(source, source)
    return localized


def _protected_names(sources):
    """Gather exact identifiers from fields which are never translated."""
    names = set(TECHNICAL_IDENTIFIERS)
    site = sources.get("site", {})
    for link in site.get("footer", {}).get("links", []):
        if link.get("label"):
            names.add(link["label"])
    for section in sources.get("team", {}).get("sections", []):
        for member in section.get("members", []):
            if member.get("name"):
                names.add(member["name"])
            for institution in member.get("affiliation", "").split(","):
                if len(institution.strip()) > 3:
                    names.add(institution.strip())
    for person in sources.get("contact", {}).get("contacts", []):
        if person.get("name"):
            names.add(person["name"])
    for person in sources.get("seminar", {}).get("organizers", []):
        if person.get("name"):
            names.add(person["name"])
    for session in sources.get("seminar", {}).get("sessions", []):
        for talk in session.get("talks", []):
            if talk.get("speaker"):
                names.add(talk["speaker"])
    for location in (
        sources.get("seminar", {}).get("venue", {}),
        sources.get("contact", {}).get("location", {}),
    ):
        for key in ("name", "title"):
            if location.get(key):
                names.add(location[key])
        names.update(location.get("address_lines", []))
    names.update({"Université Paris-Saclay", "Inria Saclay", "INRIA SACLAY"})
    return names


def protected_segments(text, sources):
    """Split immutable spans out before inference; no fragile model placeholders."""
    tick = chr(96)
    patterns = [
        r"\$\$[\s\S]*?\$\$", r"\$(?:\\.|[^$])*\$",
        r"\\\([\s\S]*?\\\)", r"\\\[[\s\S]*?\\\]",
        re.escape(tick * 3) + r"[\s\S]*?" + re.escape(tick * 3),
        re.escape(tick) + r"[^" + re.escape(tick) + r"]*" + re.escape(tick),
        r"\\[A-Za-z]+(?:\{[^{}]*\})*",
        r"\{[A-Za-z_][A-Za-z0-9_]*\}",
        r"https?://[^\s<>]+", r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
    ]
    for name in sorted(_protected_names(sources), key=lambda item: (-len(item), item)):
        patterns.append(r"(?<![\w])" + re.escape(name) + r"(?![\w])")
    matcher = re.compile("|".join(patterns), flags=re.IGNORECASE)
    result = []
    cursor = 0
    for match in matcher.finditer(text):
        if match.start() > cursor:
            result.append((False, text[cursor:match.start()]))
        result.append((True, match.group()))
        cursor = match.end()
    if cursor < len(text):
        result.append((False, text[cursor:]))
    return result


def _prose_piece(text):
    """Keep exact surrounding whitespace when joining translated fragments."""
    left = text[:len(text) - len(text.lstrip())]
    right = text[len(text.rstrip()):]
    body = text.strip()
    return left, body, right


class MarianTranslator:
    """CPU-only batched Marian inference, initialized only by the update command."""

    def __init__(self, language, batch_size=8):
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        except ImportError as error:
            raise TranslationError(
                "Install tools/translation-requirements.txt on the GitHub runner."
            ) from error
        self.torch = torch
        self.batch_size = batch_size
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        specification = MODELS[language]
        print(f"{language}: loading pinned CPU translation model", flush=True)
        self.tokenizer = AutoTokenizer.from_pretrained(
            specification["id"], revision=specification["revision"],
            trust_remote_code=False,
        )
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            specification["id"], revision=specification["revision"],
            trust_remote_code=False,
        ).to("cpu").eval()
        self.limit = min(384, int(self.model.config.max_position_embeddings) - 8)

    def _token_count(self, text):
        return len(self.tokenizer.encode(text, add_special_tokens=True))

    def _chunks(self, text):
        """Prefer sentence boundaries; split long sentences by words without truncation."""
        sentences = re.split(r"(?<=[.!?;])\s+(?=[A-ZÀ-Ý])", text)
        chunks = []
        pending = ""
        for sentence in sentences:
            for word in sentence.split():
                candidate = f"{pending} {word}".strip()
                if self._token_count(candidate) <= self.limit:
                    pending = candidate
                    continue
                if pending:
                    chunks.append(pending)
                    pending = ""
                if self._token_count(word) > self.limit:
                    # A single huge token is unusual prose: fail rather than silently cut it.
                    raise TranslationError("A prose word exceeds the model token limit.")
                pending = word
            if pending:
                chunks.append(pending)
                pending = ""
        return chunks

    def __call__(self, texts):
        """Translate prose chunks while retaining immutable punctuation in order."""
        chunks = []
        slots = []
        result = [[] for _ in texts]
        for owner, text in enumerate(texts):
            for chunk in self._chunks(text):
                slot = len(result[owner])
                # Sentence splitting after a protected name can produce "." alone.
                # Passing it to Marian hallucinates prose; keep it verbatim instead.
                if not any(character.isalpha() for character in chunk):
                    result[owner].append(chunk)
                    continue
                result[owner].append(None)
                chunks.append(chunk)
                slots.append((owner, slot))
        for start in range(0, len(chunks), self.batch_size):
            batch = chunks[start:start + self.batch_size]
            encoded = self.tokenizer(
                batch, return_tensors="pt", padding=True, truncation=False,
            )
            with self.torch.inference_mode():
                output = self.model.generate(
                    **encoded, num_beams=4, max_new_tokens=512, do_sample=False,
                )
            # Forced EOS at the generation cap can hide a truncated paragraph.
            # Stop publication rather than silently accepting a cut translation.
            if output.shape[-1] >= 513:
                raise TranslationError("A translation reached the generation token limit.")
            translated = self.tokenizer.batch_decode(output, skip_special_tokens=True)
            if len(translated) != len(batch) or any(not value.strip() for value in translated):
                raise TranslationError("The translation model returned an incomplete batch.")
            for (owner, slot), value in zip(slots[start:start + len(batch)], translated):
                result[owner][slot] = value.strip()
            print(f"Translation chunks: {min(start + len(batch), len(chunks))}/{len(chunks)}", flush=True)
        return [" ".join(parts) for parts in result]


def update_cache(sources, language, translator=None, cache=None):
    """Translate only cache misses; reject bad output before changing any cache file."""
    cache = read_cache(language) if cache is None else validate_cache(cache, language)
    texts = collect_texts(sources)
    # Apply canonical month formatting only when the English UI uses that month.
    # This also repairs a previous cache produced before calendar overrides existed.
    ui_months = sources.get("ui", {}).get("months", [])
    for english, localized in CALENDAR_MONTHS[language].items():
        if english in ui_months:
            cache["translations"][english] = localized
    missing = [text for text in texts if text not in cache["translations"]]
    print(f"{language}: {len(texts)} source texts, {len(missing)} new or changed", flush=True)
    if missing:
        plans = {text: protected_segments(text, sources) for text in missing}
        pieces = list(dict.fromkeys(
            _prose_piece(part)[1]
            for plan in plans.values()
            for protected, part in plan
            if not protected and _needs_translation(_prose_piece(part)[1])
        ))
        if translator is None and pieces:
            translator = MarianTranslator(language)
        output = translator(pieces) if pieces else []
        if not isinstance(output, list) or len(output) != len(pieces):
            raise TranslationError("Translator must return one result per source fragment.")
        if any(not isinstance(value, str) or not value.strip() for value in output):
            raise TranslationError("Translator returned an empty or invalid translation.")
        lookup = dict(zip(pieces, output))
        for text, plan in plans.items():
            parts = []
            for protected, part in plan:
                left, body, right = _prose_piece(part)
                parts.append(part if protected or body not in lookup else left + lookup[body].strip() + right)
            cache["translations"][text] = "".join(parts)
    cache["source_sha256"] = hashlib.sha256(
        json.dumps(texts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    require_complete(sources, language, cache)
    return cache


def require_complete(sources, language, cache=None):
    """CI must never deploy a locale with untranslated cache misses."""
    cache = read_cache(language) if cache is None else validate_cache(cache, language)
    missing = [text for text in collect_texts(sources) if text not in cache["translations"]]
    if missing:
        raise TranslationError(f"{language}: {len(missing)} source texts have no cached translation.")
    return True


def save_caches(caches):
    """Only called once both languages have translated successfully."""
    CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for language, cache in caches.items():
        target = CACHE_DIRECTORY / f"{language}.json"
        payload = json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if target.exists() and target.read_text(encoding="utf-8") == payload:
            continue
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(target)


def save_to_git():
    """Create a cache-only commit for CI; push/branch decisions belong to the workflow."""
    paths = ["content/translations/fr.json", "content/translations/it.json"]
    git = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]
    subprocess.run(git + ["add", "--", *paths], cwd=ROOT, check=True)
    unchanged = subprocess.run(git + ["diff", "--cached", "--quiet", "--", *paths], cwd=ROOT)
    if unchanged.returncode == 0:
        print("Translation cache unchanged; no commit needed.", flush=True)
        return
    if unchanged.returncode != 1:
        raise TranslationError("Cannot inspect the staged translation caches.")
    subprocess.run(
        git + ["-c", "user.name=github-actions[bot]", "-c",
               "user.email=41898282+github-actions[bot]@users.noreply.github.com",
               "commit", "--only", "-m", "Update automatic translations", "--", *paths],
        cwd=ROOT, check=True,
    )


def load_sources():
    """Use the same English sources and UI catalogue as the page builder."""
    import build
    sources = {name: build.read_json(name) for name in CONTENT_NAMES}
    return build.translation_sources(sources)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate complete caches without loading models.")
    parser.add_argument("--save-to-git", action="store_true", help="Commit only the generated cache files in CI.")
    arguments = parser.parse_args(argv)
    try:
        sources = load_sources()
        if arguments.check:
            for language in MODELS:
                require_complete(sources, language)
            print("French and Italian caches are complete.", flush=True)
            return 0
        # Never save a half-generated pair when the second language fails.
        caches = {
            language: update_cache(sources, language)
            for language in MODELS
        }
        save_caches(caches)
        if arguments.save_to_git:
            save_to_git()
        return 0
    except (TranslationError, OSError, subprocess.CalledProcessError) as error:
        print(f"Translation update failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
