"""Translate complete prose while keeping immutable spans out of model input.

The model may reorder opaque markers to produce natural target-language grammar.
If it damages a marker, the affected plan uses the older fragment-based strategy.
"""

import re


def _checked_output(translator, requests):
    """Validate the entire response before making any translation available."""
    output = translator(list(requests))
    if not isinstance(output, (list, tuple)) or len(output) != len(requests):
        raise ValueError("Translator must return one result per source text.")
    if any(not isinstance(value, str) or not value.strip() for value in output):
        raise ValueError("Translator returned an empty or invalid translation.")
    return {source: target.strip() for source, target in zip(requests, output)}


def _marker_namespace(plans):
    """Choose a marker prefix which cannot collide with source content."""
    source_content = "\n".join(text for plan in plans.values() for _, text in plan).casefold()
    prefix = "ZXQ"
    while prefix.casefold() in source_content:
        prefix = "Z" + prefix
    # Also reject markers which the model changed in case or split with spaces.
    separator = r"[\s_\-\u2013\u2014]*"
    marker_hint = re.compile(separator.join(map(re.escape, prefix)), re.IGNORECASE)
    return prefix, marker_hint


def _restore_markers(target, replacements, marker_hint):
    """Return None unless every known marker occurs exactly once and no others remain."""
    remainder = target
    for marker in replacements:
        if target.count(marker) != 1:
            return None
        remainder = remainder.replace(marker, "", 1)
    if marker_hint.search(remainder):
        return None
    # A single substitution pass prevents a restored value from being treated as a marker.
    matcher = re.compile("|".join(map(re.escape, replacements)))
    return matcher.sub(lambda match: replacements[match.group()], target)


def translate_plans(plans, translator, needs_translation, prose_piece):
    """Translate protected-span plans without mutating plans or translator responses.

    ``plans`` maps source identifiers to sequences of ``(protected, text)`` pairs.
    ``prose_piece`` returns the leading whitespace, body and trailing whitespace.
    Context requests and any necessary fallback requests are deduplicated in batches.
    Malformed model response shapes raise ValueError; damaged markers use fallback.
    """
    if not isinstance(plans, dict):
        raise ValueError("Translation plans must be a dictionary.")
    normalized = {}
    for source, plan in plans.items():
        if not isinstance(source, str) or not isinstance(plan, (list, tuple)):
            raise ValueError("A translation plan must have a string key and a span sequence.")
        spans = []
        for span in plan:
            if (not isinstance(span, (list, tuple)) or len(span) != 2
                    or not isinstance(span[0], bool) or not isinstance(span[1], str)):
                raise ValueError("Translation spans must contain a boolean and text.")
            spans.append((span[0], span[1]))
        normalized[source] = tuple(spans)

    prefix, marker_hint = _marker_namespace(normalized)
    contexts = {}
    results = {}
    requests = []
    for source, plan in normalized.items():
        if not any(not protected and needs_translation(prose_piece(text)[1])
                   for protected, text in plan):
            results[source] = "".join(text for _, text in plan)
            continue
        replacements = {}
        masked_parts = []
        for protected, text in plan:
            if protected and text:
                marker = f"{prefix}{len(replacements)}{prefix}"
                replacements[marker] = text
                masked_parts.append(marker)
            else:
                masked_parts.append(text)
        left, body, right = prose_piece("".join(masked_parts))
        contexts[source] = (left, body, right, replacements)
        requests.append(body)

    translated = _checked_output(translator, list(dict.fromkeys(requests))) if requests else {}
    fallback_sources = []
    for source, (left, body, right, replacements) in contexts.items():
        target = translated[body]
        restored = _restore_markers(target, replacements, marker_hint) if replacements else target
        if restored is None:
            fallback_sources.append(source)
        else:
            results[source] = left + restored + right

    fallback_requests = []
    for source in fallback_sources:
        for protected, text in normalized[source]:
            body = prose_piece(text)[1]
            if not protected and needs_translation(body) and body not in translated:
                fallback_requests.append(body)
    if fallback_requests:
        translated.update(_checked_output(translator, list(dict.fromkeys(fallback_requests))))

    for source in fallback_sources:
        parts = []
        for protected, text in normalized[source]:
            left, body, right = prose_piece(text)
            parts.append(left + translated[body] + right
                         if not protected and needs_translation(body) else text)
        results[source] = "".join(parts)

    # Preserve source insertion order even when some plans did not require inference.
    return {source: results[source] for source in plans}
