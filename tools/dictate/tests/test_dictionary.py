from pathlib import Path
from dictionary import (load_vocabulary, build_initial_prompt,
                        load_replacements, apply_replacements)


def test_vocabulary_and_prompt(tmp_path: Path):
    f = tmp_path / "v.txt"
    f.write_text("# comment\nPowerhouse\n\nExample\n", encoding="utf-8")
    terms = load_vocabulary(f)
    assert terms == ["Powerhouse", "Example"]
    assert build_initial_prompt(terms) == "Powerhouse, Example"
    assert len(build_initial_prompt(terms, max_chars=5)) <= 5


def test_replacements_parse_and_skip_malformed(tmp_path: Path):
    f = tmp_path / "r.txt"
    f.write_text("power house => Powerhouse\nbroken line\n", encoding="utf-8")
    assert load_replacements(f) == [("power house", "Powerhouse")]


def test_replacement_is_case_insensitive_and_whole_word():
    rules = [("power house", "Powerhouse")]
    assert apply_replacements("Das power house läuft", rules) == "Das Powerhouse läuft"
    assert apply_replacements("POWER HOUSE läuft", rules) == "Powerhouse läuft"
    assert apply_replacements("powerhousing", rules) == "powerhousing"


def test_longest_match_first():
    rules = [("fund", "F"), ("example term", "Example")]
    assert apply_replacements("das example term", rules) == "das Example"


def test_no_rule_no_change():
    assert apply_replacements("unverändert", []) == "unverändert"


def test_vocabulary_tolerates_a_utf8_bom(tmp_path: Path):
    # A Windows editor stamps a BOM onto a hand-edited file. The loader must strip
    # it, or the BOM is silently glued to the first term and poisons the prompt.
    f = tmp_path / "v.txt"
    f.write_bytes(b"\xef\xbb\xbfPowerhouse\nExample\n")
    assert f.read_bytes().startswith(b"\xef\xbb\xbf")  # the fixture really is BOM-prefixed
    terms = load_vocabulary(f)
    assert terms == ["Powerhouse", "Example"]
    assert "\ufeff" not in terms[0]


def test_replacements_tolerate_a_utf8_bom(tmp_path: Path):
    f = tmp_path / "r.txt"
    f.write_text("power house => Powerhouse\n", encoding="utf-8-sig")
    assert f.read_bytes().startswith(b"\xef\xbb\xbf")  # the fixture really is BOM-prefixed
    assert load_replacements(f) == [("power house", "Powerhouse")]


def test_replacement_is_inserted_literally():
    # A string template would expand \1 as a group reference (or reject a trailing
    # backslash outright), so the replacement must reach the text verbatim.
    assert apply_replacements("hallo welt", [("welt", r"a\1b")]) == r"hallo a\1b"
    assert apply_replacements("hallo welt", [("welt", "a\\")]) == "hallo a\\"
