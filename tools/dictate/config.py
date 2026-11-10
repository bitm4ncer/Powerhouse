"""Configuration for the dictate push-to-talk dictation tool.

The on-disk format is JSON with camelCase keys; the in-memory representation is a
frozen dataclass with snake_case fields. Unknown keys in the file are ignored so a
config written by a newer version of dictate still loads in an older one.

Example:

    from config import ensure_config, load_config
    from pathlib import Path

    cfg = ensure_config(Path.home() / "dictate" / "dictate.config.json")
    print(cfg.language)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

# Allowed values per field. Anything outside these sets is rejected by load_config.
MOUSE_BUTTONS = ("XButton1", "XButton2", "Middle")
INSERT_MODES = ("sendinput", "clipboard")
DEVICES = ("auto", "cuda", "cpu")
MIN_RECORD_SECONDS = 5
MAX_RECORD_SECONDS = 600


def _camel_case(field_name: str) -> str:
    """mouse_button -> mouseButton, max_record_seconds -> maxRecordSeconds."""
    head, *rest = field_name.split("_")
    return head + "".join(part.capitalize() for part in rest)


@dataclass(frozen=True)
class Config:
    """Immutable user settings; build modified copies via dataclasses.replace."""

    mouse_button: str = "XButton1"
    mic_device: str = ""
    model: str = "large-v3-turbo"
    language: str = "de"
    device: str = "auto"
    max_record_seconds: int = 120
    insert_mode: str = "sendinput"
    beep: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the camelCase JSON shape used by the config file."""
        return {JSON_KEY_BY_FIELD[name]: getattr(self, name) for name in _FIELD_NAMES}


DEFAULT_CONFIG = Config()

_FIELD_NAMES = tuple(f.name for f in fields(Config))
JSON_KEY_BY_FIELD = {name: _camel_case(name) for name in _FIELD_NAMES}
FIELD_BY_JSON_KEY = {key: name for name, key in JSON_KEY_BY_FIELD.items()}


def _invalid(key: str, value: Any, allowed: str) -> ValueError:
    return ValueError(f"Invalid value for '{key}': {value!r}. Allowed values: {allowed}")


@dataclass(frozen=True)
class _Rule:
    """Declarative validation rule for a single Config field.

    kind     - the checker to run, one of CHECKERS
    values   - allowed values for the "choice" kind
    low/high - inclusive bounds for the "int_range" kind
    """

    kind: str
    values: tuple[str, ...] = ()
    low: int = 0
    high: int = 0


def _check_choice(key: str, value: Any, rule: _Rule) -> None:
    if not isinstance(value, str) or value not in rule.values:
        raise _invalid(key, value, ", ".join(rule.values))


def _check_int_range(key: str, value: Any, rule: _Rule) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not rule.low <= value <= rule.high:
        raise _invalid(key, value, f"an integer between {rule.low} and {rule.high}")


def _check_bool(key: str, value: Any, rule: _Rule) -> None:
    if not isinstance(value, bool):
        raise _invalid(key, value, "true or false")


def _check_text(key: str, value: Any, rule: _Rule) -> None:
    if not isinstance(value, str):
        raise _invalid(key, value, "a string")


def _check_nonempty(key: str, value: Any, rule: _Rule) -> None:
    if not isinstance(value, str) or not value:
        raise _invalid(key, value, "a non-empty string")


CHECKERS = {
    "choice": _check_choice,
    "int_range": _check_int_range,
    "bool": _check_bool,
    "text": _check_text,
    "nonempty": _check_nonempty,
}

# Exactly one rule per Config field. There is deliberately no catch-all rule: a
# field added here without its own entry is caught by _assert_rules_are_complete
# at import time instead of silently inheriting the wrong validator.
FIELD_RULES: dict[str, _Rule] = {
    "mouse_button": _Rule("choice", MOUSE_BUTTONS),
    "mic_device": _Rule("text"),  # "" is legal and means "system default input device"
    "model": _Rule("nonempty"),
    "language": _Rule("nonempty"),
    "device": _Rule("choice", DEVICES),
    "max_record_seconds": _Rule("int_range", low=MIN_RECORD_SECONDS, high=MAX_RECORD_SECONDS),
    "insert_mode": _Rule("choice", INSERT_MODES),
    "beep": _Rule("bool"),
}


def _assert_rules_are_complete() -> None:
    """Fail loudly at import if the rule table and the Config fields disagree."""
    problems = []
    if missing := sorted(set(_FIELD_NAMES) - set(FIELD_RULES)):
        problems.append(f"fields without a validation rule: {missing}")
    if stale := sorted(set(FIELD_RULES) - set(_FIELD_NAMES)):
        problems.append(f"rules for unknown fields: {stale}")
    if unknown := sorted({r.kind for r in FIELD_RULES.values()} - set(CHECKERS)):
        problems.append(f"unknown rule kinds: {unknown}")
    if problems:
        raise RuntimeError("invalid FIELD_RULES - " + "; ".join(problems))


_assert_rules_are_complete()


def _validate(overrides: dict[str, Any]) -> None:
    """Raise ValueError naming the JSON key and its allowed values on bad input.

    Every field is looked up in FIELD_RULES; there is no else branch, so a value
    cannot be checked by a validator that was meant for a different field.
    """
    for name, value in overrides.items():
        rule = FIELD_RULES[name]
        CHECKERS[rule.kind](JSON_KEY_BY_FIELD[name], value, rule)


def load_config(path: Path) -> Config:
    """Return the config stored at path, merged onto the defaults.

    A missing file yields DEFAULT_CONFIG. Unknown keys are ignored; a known key
    with an out-of-range value raises ValueError.

    Files are read as utf-8-sig, so a BOM-prefixed config (PowerShell 5.1,
    legacy Notepad) loads exactly like a plain UTF-8 one.
    """
    path = Path(path)
    if not path.exists():
        return DEFAULT_CONFIG
    # utf-8-sig also accepts plain UTF-8, and additionally tolerates the BOM that
    # PowerShell 5.1 and legacy Notepad put on hand-edited files.
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError(
            f"Config file {path} must contain a JSON object, got {type(raw).__name__}"
        )
    overrides = {
        FIELD_BY_JSON_KEY[key]: value
        for key, value in raw.items()
        if key in FIELD_BY_JSON_KEY
    }
    _validate(overrides)
    return replace(DEFAULT_CONFIG, **overrides)


def ensure_config(path: Path) -> Config:
    """Create the config file with the defaults if missing, then load it."""
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(DEFAULT_CONFIG.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return load_config(path)