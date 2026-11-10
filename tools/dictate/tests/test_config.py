from pathlib import Path
import dataclasses
import json
import pytest
from config import (
    CHECKERS,
    Config,
    DEFAULT_CONFIG,
    FIELD_RULES,
    JSON_KEY_BY_FIELD,
    ensure_config,
    load_config,
)


def test_defaults_when_file_missing(tmp_path: Path):
    assert load_config(tmp_path / "nope.json") == DEFAULT_CONFIG


def test_overrides_from_file(tmp_path: Path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"mouseButton": "Middle", "maxRecordSeconds": 30}), encoding="utf-8")
    cfg = load_config(p)
    assert cfg.mouse_button == "Middle"
    assert cfg.max_record_seconds == 30
    assert cfg.language == "de"  # untouched key keeps the default


def test_invalid_value_raises(tmp_path: Path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"mouseButton": "YButton9"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(p)


def test_ensure_config_writes_defaults(tmp_path: Path):
    p = tmp_path / "sub" / "c.json"
    cfg = ensure_config(p)
    assert p.exists()
    assert json.loads(p.read_text(encoding="utf-8"))["mouseButton"] == "XButton1"


def test_loads_utf8_bom_file(tmp_path: Path):
    """PowerShell 5.1 and legacy Notepad write UTF-8 with a BOM; it must load."""
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"language": "en"}), encoding="utf-8-sig")
    assert p.read_bytes().startswith(b"\xef\xbb\xbf")  # guard: the file really has a BOM
    assert load_config(p).language == "en"


def test_unknown_keys_are_ignored(tmp_path: Path):
    p = tmp_path / "c.json"
    p.write_text(
        json.dumps({"language": "en", "futureOption": True, "maxRecordseconds": 30}),
        encoding="utf-8",
    )
    cfg = load_config(p)
    assert cfg == dataclasses.replace(DEFAULT_CONFIG, language="en")
    assert cfg.max_record_seconds == 120  # near-miss key ignored, default kept


@pytest.mark.parametrize(
    "payload, pattern",
    [
        ({"mouseButton": "YButton9"}, r"'mouseButton'.*XButton1, XButton2, Middle"),
        ({"insertMode": "paste"}, r"'insertMode'.*sendinput, clipboard"),
        ({"device": "tpu"}, r"'device'.*auto, cuda, cpu"),
        ({"maxRecordSeconds": 0}, r"'maxRecordSeconds'.*an integer between 5 and 600"),
        ({"beep": "yes"}, r"'beep'.*true or false"),
        ({"model": ""}, r"'model'.*a non-empty string"),
        ({"language": ""}, r"'language'.*a non-empty string"),
        ({"micDevice": 3}, r"'micDevice'.*a string"),
    ],
)
def test_error_names_key_and_allowed_values(tmp_path: Path, payload, pattern):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=pattern):
        load_config(p)


def test_every_field_has_an_explicit_validation_rule():
    """No field may fall through to a default validator: rules, keys and kinds line up."""
    assert set(FIELD_RULES) == set(JSON_KEY_BY_FIELD)
    assert {rule.kind for rule in FIELD_RULES.values()} <= set(CHECKERS)