"""Vocabulary prompt and post-correction rules for dictate.

Two plain-text tables, both living next to the config file and both hand-editable:

* ``vocabulary.txt`` - one term per line. The terms are joined into an initial
  prompt that biases the speech recognizer towards the names this user actually
  says (project names, tools, jargon).
* ``replacements.txt`` - one ``wrong => right`` rule per line. The rules repair
  the recognizer's spelling of those same names after transcription.

Both files are read as utf-8-sig, so a BOM-prefixed file (PowerShell 5.1, legacy
Notepad) behaves exactly like a plain UTF-8 one. Callers pass the paths in; this
module never resolves them itself.

Example:

    from dictionary import (apply_replacements, build_initial_prompt,
                            load_replacements, load_vocabulary)
    from pathlib import Path

    prompt = build_initial_prompt(load_vocabulary(Path("vocabulary.txt")))
    text = apply_replacements(text, load_replacements(Path("replacements.txt")))
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

# Separator between the misheard text and the correct one in replacements.txt.
SEPARATOR = "=>"

# Both dictionary files are read with utf-8-sig: it accepts plain UTF-8 and
# additionally tolerates the BOM that Windows editors add to hand-edited files.
_ENCODING = "utf-8-sig"

# Marker for a whole-line comment. It is honoured by load_vocabulary only.
# load_replacements does not consult it: see the note on that function.
_COMMENT = "#"


def load_vocabulary(path: Path) -> list[str]:
    """Return the terms listed in the vocabulary file at path.

    One term per line. Blank lines and lines starting with '#' are ignored; every
    surviving line is stripped and kept in file order, duplicates included.
    """
    lines = Path(path).read_text(encoding=_ENCODING).splitlines()
    terms: list[str] = []
    for raw in lines:
        term = raw.strip()
        if not term or term.startswith(_COMMENT):
            continue
        terms.append(term)
    return terms


def build_initial_prompt(terms: Sequence[str], max_chars: int = 800) -> str:
    """Join terms into a comma-separated recognizer prompt.

    Terms are added in order until the next one would push the prompt past
    max_chars; the cut is always made at a term boundary, so the result is never
    a partial term. An empty term list, or one whose first term already exceeds
    max_chars, yields an empty string.
    """
    kept: list[str] = []
    length = 0
    for term in terms:
        # Every term after the first costs the ", " that precedes it.
        needed = len(term) if not kept else length + 2 + len(term)
        if needed > max_chars:
            break
        kept.append(term)
        length = needed
    return ", ".join(kept)


def load_replacements(path: Path) -> list[tuple[str, str]]:
    """Return the (pattern, replacement) rules listed in the file at path.

    Each line has the form ``wrong => right``. Lines without the separator, and
    lines whose pattern or replacement is empty after stripping, are malformed and
    are skipped rather than raising, so one bad edit cannot break dictation. Only
    the first separator counts, so a replacement may itself contain "=>".

    There is no comment syntax here, unlike in the vocabulary file: every line is
    parsed for a separator, and ``_COMMENT`` is deliberately not consulted. A bare
    "# note" line is skipped as malformed because it has no separator, but a
    commented-out rule such as "# power house => Powerhouse" *does* contain one and
    therefore loads as a live rule. Comment rules out by deleting the line.
    """
    lines = Path(path).read_text(encoding=_ENCODING).splitlines()
    rules: list[tuple[str, str]] = []
    for raw in lines:
        line = raw.strip()
        if not line or SEPARATOR not in line:
            continue
        pattern, _, replacement = line.partition(SEPARATOR)
        pattern, replacement = pattern.strip(), replacement.strip()
        if not pattern or not replacement:
            continue
        rules.append((pattern, replacement))
    return rules


def apply_replacements(text: str, rules: Sequence[tuple[str, str]]) -> str:
    """Rewrite every occurrence of a rule's pattern in text with its replacement.

    Matching is case-insensitive and restricted to whole words, so a rule for
    "power house" fixes "Radio Dock" but leaves "powerhousing" alone. Rules are
    applied longest pattern first, so a specific "example term => Example" wins over
    a generic "fund => F" no matter which order the file lists them in.

    The replacement is inserted literally: a backslash or a group reference in the
    replacement text is inserted as written instead of being read as regex syntax.
    """
    ordered = sorted(rules, key=lambda rule: len(rule[0]), reverse=True)
    for pattern, replacement in ordered:
        regex = re.compile(rf"(?<!\w){re.escape(pattern)}(?!\w)", re.IGNORECASE)
        # The lambda keeps the replacement literal; a str template would expand
        # backslashes and \1-style group references in the user's replacement.
        # Safe without a default binding: sub() invokes this before the next loop
        # iteration rebinds `replacement`.
        text = regex.sub(lambda _match: replacement, text)
    return text
