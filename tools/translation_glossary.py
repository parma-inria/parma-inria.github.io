"""Apply the team's small English/French/Italian terminology list safely.

The glossary contains reusable terms rather than translations of complete pages.
All matching and validation use the standard library; no model is loaded here.
"""

import copy
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GLOSSARY = ROOT / "content" / "glossary.json"
LANGUAGES = ("en", "fr", "it")
# These tokens belong to immutable source spans, never glossary vocabulary.
IMMUTABLE_TOKEN = re.compile(r"[`$\\{}<>]|https?://|mailto:|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", re.IGNORECASE)


class GlossaryError(ValueError):
    """The terminology list is invalid or a protection callback is inconsistent."""


def validate_glossary(glossary):
    """Return independent, normalized rows and reject ambiguous English terms."""
    if not isinstance(glossary, list):
        raise GlossaryError("The glossary must be a list of en/fr/it terms.")
    validated = []
    seen = set()
    for index, entry in enumerate(glossary):
        if not isinstance(entry, dict) or set(entry) != set(LANGUAGES):
            raise GlossaryError(f"Glossary entry {index + 1} must contain exactly en, fr and it.")
        row = {}
        for language in LANGUAGES:
            value = entry[language]
            if not isinstance(value, str) or not value.strip():
                raise GlossaryError(f"Glossary entry {index + 1} has an empty or invalid {language} term.")
            value = " ".join(value.split())
            if not any(character.isalpha() for character in value) or IMMUTABLE_TOKEN.search(value):
                raise GlossaryError(f"Glossary entry {index + 1} contains unsupported tokens in {language}.")
            row[language] = value
        normalized = row["en"].casefold()
        if normalized in seen:
            raise GlossaryError(f"Duplicate English glossary term: {row['en']}")
        seen.add(normalized)
        validated.append(row)
    return validated


def read_glossary(path=DEFAULT_GLOSSARY):
    """Read the only terminology file intended for routine editorial changes."""
    path = Path(path)

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise GlossaryError(f"Duplicate glossary field {key!r} in {path}.")
            result[key] = value
        return result

    try:
        return validate_glossary(json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys))
    except (OSError, json.JSONDecodeError) as error:
        raise GlossaryError(f"Cannot read glossary {path}: {error}") from error


def glossary_fingerprint(glossary=None, language=None):
    """Hash semantic preferences, independent of JSON layout and row order."""
    if language is not None and language not in LANGUAGES:
        raise GlossaryError(f"Unsupported glossary language: {language}")
    rows = read_glossary() if glossary is None else validate_glossary(glossary)
    fields = LANGUAGES if language is None else ("en", language)
    canonical = sorted(
        ({key: row[key].casefold() if key == "en" else row[key] for key in fields} for row in rows),
        key=lambda row: row["en"],
    )
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def preferred_case(source, target):
    """Mirror capitals and headings without capitalizing an internal eponym."""
    if source.isupper():
        return target.upper()
    if source.istitle():
        return target[:1].upper() + target[1:]
    first_word = source.split()[0] if source.split() else ""
    # "Wasserstein distance" starts with a proper name, even within a sentence.
    if source[:1].isupper() and first_word not in target:
        return target[:1].upper() + target[1:]
    return target


def _preserve_identifiers(target, identifiers):
    """A phrase may cover a protected name only when that name survives intact."""
    for identifier in identifiers:
        match = re.search(r"(?<!\w)" + re.escape(identifier) + r"(?!\w)", target, re.IGNORECASE)
        if match is None:
            return None
        target = target[:match.start()] + identifier + target[match.end():]
    return target


def _matches(text, sources, protected_segments, glossary):
    original = list(protected_segments(text, sources))
    if "".join(part for _, part in original) != text:
        raise GlossaryError("Protected source segments do not reconstruct their source text.")
    spans = []
    cursor = 0
    for protected, part in original:
        if protected:
            spans.append((cursor, cursor + len(part), part))
        cursor += len(part)
    candidates = []
    for entry in glossary:
        expression = r"(?<!\w)" + r"\s+".join(re.escape(word) for word in entry["en"].split()) + r"(?!\w)"
        for match in re.finditer(expression, text, re.IGNORECASE):
            identifiers = []
            allowed = True
            for start, end, part in spans:
                if match.start() < end and start < match.end():
                    if (start < match.start() or end > match.end() or IMMUTABLE_TOKEN.search(part)):
                        allowed = False
                        break
                    identifiers.append(part)
            targets = {
                language: _preserve_identifiers(preferred_case(match.group(), entry[language]), identifiers)
                for language in ("fr", "it")
            }
            if allowed and all(target is not None for target in targets.values()):
                candidates.append((match.start(), match.end(), entry, targets))
    # Resolve overlapping expressions before putting the winners in source order.
    winners = []
    for candidate in sorted(candidates, key=lambda item: (-(item[1] - item[0]), item[0], item[2]["en"].casefold())):
        if not any(candidate[0] < existing[1] and existing[0] < candidate[1] for existing in winners):
            winners.append(candidate)
    return original, spans, sorted(winners, key=lambda item: item[0])


def matched_terms(text, sources, protected_segments, glossary=None):
    """Return each winning term once, in order of its first source occurrence."""
    rows = read_glossary() if glossary is None else validate_glossary(glossary)
    _, _, winners = _matches(text, sources, protected_segments, rows)
    result = []
    seen = set()
    for _, _, entry, _ in winners:
        if entry["en"].casefold() not in seen:
            result.append(copy.deepcopy(entry))
            seen.add(entry["en"].casefold())
    return result


def terminology_segments(text, sources, language, protected_segments, glossary=None):
    """Protect translated vocabulary while preserving the original immutable spans."""
    if language not in LANGUAGES:
        raise GlossaryError(f"Unsupported glossary language: {language}")
    rows = read_glossary() if glossary is None else validate_glossary(glossary)
    original, spans, winners = _matches(text, sources, protected_segments, rows)
    if language == "en" or not winners:
        return original
    events = [(start, end, targets[language]) for start, end, _, targets in winners]
    events.extend(
        (start, end, part) for start, end, part in spans
        if not any(left < end and start < right for left, right, _, _ in winners)
    )
    result = []
    cursor = 0
    for start, end, replacement in sorted(events):
        if start > cursor:
            result.append((False, text[cursor:start]))
        result.append((True, replacement))
        cursor = end
    if cursor < len(text):
        result.append((False, text[cursor:]))
    return result
