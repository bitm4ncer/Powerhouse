"""Tests for the text inserter.

The first five tests are the ones the task brief specifies verbatim. The rest
pin project constraints the brief states in prose but does not test - above all
that no Enter/Return key press is ever synthesized.
"""

import ctypes
import inspect

import pytest

import inserter
from inserter import build_unicode_inputs, insert_clipboard, insert_text

# Every Win32 constant is asserted against its documented ABI value, declared here
# rather than imported from the module under test. Importing them would let a
# wrong value in inserter.py satisfy its own assertion: renaming VK_CONTROL to
# 0x12 would turn the paste into Alt+V and still pass.
VK_CONTROL = 0x11
VK_V = 0x56
VK_RETURN = 0x0D
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

# sizeof(INPUT) is fixed by the Win32 ABI: a DWORD type followed by the union of
# KEYBDINPUT, MOUSEINPUT and HARDWAREINPUT, aligned to the pointer size. Derived
# from the platform, never from ctypes.sizeof(inserter.INPUT) - computing it that
# way shrinks both sides together and stays green while every real SendInput call
# fails on the cbSize mismatch.
_EXPECTED_INPUT_SIZE = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28


# --- tests from the brief ----------------------------------------------------

def test_ascii_gives_two_units_per_char():
    pairs = build_unicode_inputs("Ab")
    assert [s for _, s in pairs] == [ord("A"), ord("b")]
    assert all(vk == 0 for vk, _ in pairs)


def test_german_umlauts_and_sharp_s():
    pairs = build_unicode_inputs("äöüß")
    assert [s for _, s in pairs] == [0x00E4, 0x00F6, 0x00FC, 0x00DF]


def test_surrogate_pair_for_non_bmp():
    pairs = build_unicode_inputs("😀")
    assert len(pairs) == 2  # one surrogate pair
    assert all(0xD800 <= s <= 0xDFFF for _, s in pairs)


def test_newline_is_preserved():
    pairs = build_unicode_inputs("a\nb")
    assert [s for _, s in pairs] == [ord("a"), 0x0A, ord("b")]


def test_empty_text_yields_no_events():
    assert build_unicode_inputs("") == []


# --- helpers -----------------------------------------------------------------

def _capture_send_inputs(monkeypatch):
    """Record every batch handed to the Win32 SendInput call."""
    batches = []

    def fake_send_inputs(events):
        batches.append(list(events))
        return len(events)

    monkeypatch.setattr(inserter, "_send_inputs", fake_send_inputs)
    return batches


def _fake_clipboard(monkeypatch, previous, paste_error=None):
    """Replace the clipboard primitives with recorders and return the call log."""
    log = []

    def read():
        log.append(("read", None))
        return previous

    def write(text):
        log.append(("write", text))

    def clear():
        log.append(("clear", None))

    def paste():
        log.append(("paste", None))
        if paste_error is not None:
            raise paste_error

    monkeypatch.setattr(inserter, "_read_clipboard_text", read)
    monkeypatch.setattr(inserter, "_write_clipboard_text", write)
    monkeypatch.setattr(inserter, "_clear_clipboard", clear)
    monkeypatch.setattr(inserter, "_send_paste_keystroke", paste)
    return log


def _record_sleep(monkeypatch, log):
    """Make the settle wait show up in the call log instead of really waiting."""
    monkeypatch.setattr(inserter, "_sleep",
                        lambda seconds: log.append(("sleep", seconds)))
    return log


# --- no synthesized Enter, in any code path ----------------------------------

def test_unicode_inputs_never_carry_a_virtual_key():
    # Every pair is (wVk=0, wScan=<utf-16 code unit>): a character to type, not a
    # key to press. A literal CR in the text is still only code unit 0x0D typed as
    # a character; it never becomes the VK_RETURN virtual key.
    pairs = build_unicode_inputs("a\r\n")
    assert {vk for vk, _ in pairs} == {0}


def test_insert_text_never_synthesizes_a_return_key_press(monkeypatch):
    # Hard product requirement: dictate types the text and leaves sending to the
    # user. A synthesized Return could only come from a real virtual-key event or
    # a scan-code event, so requiring wVk == 0 plus KEYEVENTF_UNICODE on every
    # single event rules it out - including for text that contains CR or LF.
    batches = _capture_send_inputs(monkeypatch)
    insert_text("Hallo\r\nWelt")
    events = batches[0]
    assert events
    for event in events:
        assert event.type == INPUT_KEYBOARD
        assert event.ki.wVk == 0, "a non-zero wVk would be a real key press"
        assert not event.ki.dwFlags & KEYEVENTF_SCANCODE, "a scan code is a key press"
        assert event.ki.dwFlags & KEYEVENTF_UNICODE, "every event must type a character"


def test_paste_keystroke_is_ctrl_v_and_never_enter(monkeypatch):
    batches = _capture_send_inputs(monkeypatch)
    inserter._send_paste_keystroke()
    events = batches[0]
    assert [event.ki.wVk for event in events] == [VK_CONTROL, VK_V, VK_V, VK_CONTROL]
    assert [bool(event.ki.dwFlags & KEYEVENTF_KEYUP) for event in events] == [
        False, False, True, True
    ]
    assert all(event.type == INPUT_KEYBOARD for event in events)
    assert VK_RETURN not in [event.ki.wVk for event in events]


# --- sendinput mode ----------------------------------------------------------

def test_insert_text_sends_one_batch_of_keydown_and_keyup_pairs(monkeypatch):
    batches = _capture_send_inputs(monkeypatch)
    insert_text("äöü")
    assert len(batches) == 1, "SendInput must be called once with the whole batch"
    events = batches[0]
    assert len(events) == 2 * len(build_unicode_inputs("äöü"))
    scans = [event.ki.wScan for event in events]
    assert scans[0::2] == [0x00E4, 0x00F6, 0x00FC]
    assert scans[1::2] == scans[0::2], "every character needs its own keyup"
    flags = [event.ki.dwFlags for event in events]
    assert flags[0::2] == [KEYEVENTF_UNICODE] * 3
    assert flags[1::2] == [KEYEVENTF_UNICODE | KEYEVENTF_KEYUP] * 3


def test_insert_text_with_empty_text_sends_nothing(monkeypatch):
    batches = _capture_send_inputs(monkeypatch)
    insert_text("")
    assert batches == []


def test_input_struct_has_the_size_win32_expects():
    # A union missing MOUSEINPUT shrinks INPUT to 32 bytes and every real
    # SendInput call then fails on the cbSize mismatch, returning 0.
    assert ctypes.sizeof(inserter.INPUT) == _EXPECTED_INPUT_SIZE, (
        f"INPUT is {ctypes.sizeof(inserter.INPUT)} bytes, "
        f"the Win32 ABI requires {_EXPECTED_INPUT_SIZE} on this platform")


def test_input_union_carries_all_three_win32_members():
    # The size assertion alone cannot see HARDWAREINPUT go: it is never the
    # largest union member on either platform (MOUSEINPUT is), so dropping it
    # leaves sizeof(INPUT) unchanged. The union has to be pinned by name, or
    # "cleanup" can delete it and quietly shrink the struct.
    assert [name for name, _ in inserter._INPUTUNION._fields_] == ["ki", "mi", "hi"]


def test_send_inputs_hands_win32_the_whole_batch_and_the_struct_size(monkeypatch):
    # Proves the ctypes marshalling without calling the real SendInput: the batch
    # has to arrive as a readable INPUT array and cbSize has to be the size the
    # Win32 ABI requires, otherwise Windows rejects the call and nothing is typed.
    seen = {}

    class FakeUser32:
        @staticmethod
        def SendInput(count, array, cb_size):
            seen["count"] = count
            seen["cb_size"] = cb_size
            seen["scans"] = [array[i].ki.wScan for i in range(count)]
            return count

    monkeypatch.setattr(inserter, "_user32", FakeUser32)
    events = inserter._build_input_events([(0, 65), (0, 0x00FC)])
    assert inserter._send_inputs(events) == 4
    assert seen == {"count": 4, "cb_size": _EXPECTED_INPUT_SIZE,
                    "scans": [65, 65, 0x00FC, 0x00FC]}


def test_insert_text_reports_a_send_that_was_only_partially_delivered(monkeypatch):
    # SendInput returns how many events it queued. A short count means something
    # (a foreground-window/UIPI block, for instance) swallowed the rest, and the
    # dictation would otherwise vanish without a word.
    monkeypatch.setattr(inserter, "_send_inputs", lambda events: len(events) - 1)
    with pytest.raises(RuntimeError):
        insert_text("Hallo")


# --- mode selection ----------------------------------------------------------

def test_insert_text_routes_to_the_requested_mode(monkeypatch):
    seen = []
    monkeypatch.setattr(inserter, "insert_clipboard", lambda text: seen.append(text))
    insert_text("Hallo", mode="clipboard")
    assert seen == ["Hallo"]


def test_insert_text_rejects_an_unknown_mode():
    with pytest.raises(ValueError, match="clipboard"):
        insert_text("Hallo", mode="typeo")


# --- clipboard mode ----------------------------------------------------------

def test_insert_clipboard_saves_pastes_settles_and_restores(monkeypatch):
    # The order is the whole point: the paste has to be sent, then given time to
    # land, and only then is the user's clipboard text put back. Restoring before
    # the wait would race the target application, which may still be reading it.
    log = _record_sleep(monkeypatch, _fake_clipboard(monkeypatch, "vorher"))
    insert_clipboard("Hallo Welt")
    assert log == [
        ("read", None),
        ("write", "Hallo Welt"),
        ("paste", None),
        ("sleep", inserter._PASTE_SETTLE_SECONDS),
        ("write", "vorher"),
    ]


def test_insert_clipboard_restores_the_previous_text_when_pasting_fails(monkeypatch):
    log = _record_sleep(
        monkeypatch,
        _fake_clipboard(monkeypatch, "vorher", paste_error=RuntimeError("no focus")),
    )
    with pytest.raises(RuntimeError):
        insert_clipboard("Hallo Welt")
    assert log == [
        ("read", None),
        ("write", "Hallo Welt"),
        ("paste", None),
        ("sleep", inserter._PASTE_SETTLE_SECONDS),
        ("write", "vorher"),
    ]


def test_insert_clipboard_clears_the_clipboard_when_it_was_empty(monkeypatch):
    # Privacy: starting from an empty clipboard must not leave the dictated text
    # behind for the next copy to pick up.
    log = _record_sleep(monkeypatch, _fake_clipboard(monkeypatch, None))
    insert_clipboard("Geheimnis")
    assert log == [
        ("read", None),
        ("write", "Geheimnis"),
        ("paste", None),
        ("sleep", inserter._PASTE_SETTLE_SECONDS),
        ("clear", None),
    ]


def test_settle_is_keyword_only_and_defaults_to_the_module_constant():
    parameter = inspect.signature(inserter.insert_clipboard).parameters["settle"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inserter._PASTE_SETTLE_SECONDS
    assert inserter._PASTE_SETTLE_SECONDS == 0.12


def test_settle_interval_can_be_overridden(monkeypatch):
    log = _record_sleep(monkeypatch, _fake_clipboard(monkeypatch, "vorher"))
    insert_clipboard("Hallo Welt", settle=0.0)
    assert ("sleep", 0.0) in log


# --- encoding ----------------------------------------------------------------

def test_lone_surrogates_are_rejected():
    # A lone surrogate has no character to type. Encoding strictly raises instead
    # of quietly inserting mojibake into the user's document.
    with pytest.raises(UnicodeEncodeError):
        build_unicode_inputs("\ud800")


def test_code_units_round_trip_back_to_the_original_text():
    # The pairs are what Win32 receives; putting them back together as UTF-16 has
    # to give the original text back, surrogate pair and newline included.
    text = "Grüße \U0001F600\n"
    raw = b"".join(scan.to_bytes(2, "little")
                   for _, scan in build_unicode_inputs(text))
    assert raw.decode("utf-16-le") == text
