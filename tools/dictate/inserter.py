"""Text insertion for dictate: types transcribed text into the focused control.

Two insertion modes are available, both selected by :func:`insert_text`:

* ``sendinput`` (the default) - every UTF-16 code unit of the text is sent as a
  ``KEYEVENTF_UNICODE`` keyboard event via ``SendInput``. The text is typed
  character by character and never needs clipboard access.
* ``clipboard`` - the text is placed on the clipboard and pasted with Ctrl+V.
  Slower, but some controls (terminals, remote desktop sessions, games) ignore
  ``KEYEVENTF_UNICODE`` events and only honour real key presses. The user's
  clipboard is always restored afterwards, after a short settle so the paste can
  land first.

Neither mode ever synthesizes an Enter/Return key press. dictate types into
whatever field has focus and leaves *sending* the message to the user.

The Win32 calls are funnelled through module-level helpers (``_send_inputs``,
``_read_clipboard_text``, ``_write_clipboard_text``, ``_send_paste_keystroke``)
so tests can replace them without touching the real keyboard or the real
clipboard.

Example:

    from inserter import insert_text

    insert_text("Grüße", mode="sendinput")
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

# How long to wait after Ctrl+V before putting the previous clipboard text back.
# The target application consumes a paste asynchronously; restoring the clipboard
# straight away can make it read the old text, or nothing, instead.
_PASTE_SETTLE_SECONDS = 0.12

# --- Win32 constants ---------------------------------------------------------

# INPUT_KEYBOARD selects the keyboard member of the INPUT union.
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
# KEYEVENTF_UNICODE types a code unit as a character. KEYEVENTF_SCANCODE (0x0008)
# is deliberately never combined with it: that combination is a key press rather
# than a character, which is exactly what this module must never do for text.
KEYEVENTF_UNICODE = 0x0004

VK_CONTROL = 0x11
VK_V = 0x56

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

# --- Win32 structures --------------------------------------------------------

# ULONG_PTR is pointer-sized; it is not exposed by ctypes.wintypes.
_ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    """Win32 KEYBDINPUT - a single keyboard event."""

    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    """Not used here; declared so that sizeof(INPUT) matches the Win32 one."""

    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    """Not used here; see MOUSEINPUT."""

    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    """Win32 INPUT - one entry of the array handed to SendInput.

    The union is anonymous, so a keyboard event is read as ``event.ki``.
    """

    _anonymous_ = ("payload",)
    _fields_ = [("type", wintypes.DWORD), ("payload", _INPUTUNION)]


# --- Win32 API ---------------------------------------------------------------

# use_last_error keeps GetLastError meaningful for the calls that only report
# failure through a zero return value.
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
_user32.SendInput.restype = wintypes.UINT
_user32.OpenClipboard.argtypes = [wintypes.HWND]
_user32.OpenClipboard.restype = wintypes.BOOL
_user32.CloseClipboard.argtypes = []
_user32.CloseClipboard.restype = wintypes.BOOL
_user32.EmptyClipboard.argtypes = []
_user32.EmptyClipboard.restype = wintypes.BOOL
_user32.GetClipboardData.argtypes = [wintypes.UINT]
_user32.GetClipboardData.restype = wintypes.HANDLE
_user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
_user32.SetClipboardData.restype = wintypes.HANDLE

_kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
_kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
_kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
_kernel32.GlobalLock.restype = wintypes.LPVOID
_kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
_kernel32.GlobalUnlock.restype = wintypes.BOOL
_kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
_kernel32.GlobalFree.restype = wintypes.HGLOBAL


# --- character events --------------------------------------------------------

def build_unicode_inputs(text: str) -> list[tuple[int, int]]:
    """Return one ``(wVk=0, wScan=code unit)`` pair per UTF-16 code unit of text.

    ``KEYEVENTF_UNICODE`` tells ``SendInput`` to type a code unit as a character
    instead of looking it up as a virtual key, so ``wVk`` stays 0 throughout.
    That is what makes umlauts, sharp s and emoji work without a keyboard layout
    and without a dead-key dance.

    The text is encoded as UTF-16 first because that is what Win32 expects:
    characters outside the basic multilingual plane become a surrogate pair and
    therefore yield two pairs.

    A lone surrogate has no character to type, so the strict encoder raises
    ``UnicodeEncodeError`` rather than inserting mojibake.
    """
    raw = text.encode("utf-16-le")
    return [(0, int.from_bytes(raw[i:i + 2], "little")) for i in range(0, len(raw), 2)]


def _build_input_events(pairs: list[tuple[int, int]]) -> list[INPUT]:
    """Expand ``(wVk, wScan)`` pairs into INPUT events, a keydown plus a keyup.

    The keyup is not optional: leaving a character key down is what makes the
    focused control auto-repeat it.
    """
    events: list[INPUT] = []
    for vk, scan in pairs:
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            event = INPUT(type=INPUT_KEYBOARD)
            event.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0,
                                  dwExtraInfo=0)
            events.append(event)
    return events


def _send_inputs(events: list[INPUT]) -> int:
    """Hand the whole batch to SendInput in one call; return the queued count."""
    if not events:
        return 0
    array = (INPUT * len(events))(*events)
    return _user32.SendInput(len(events), array, ctypes.sizeof(INPUT))


def _send_all(events: list[INPUT]) -> None:
    """Send a batch and fail loudly if Windows queued only part of it.

    SendInput reports how many events it accepted. A short count means something
    - a foreground-window/UIPI block, typically - swallowed the rest, and the
    text would otherwise disappear without a word.
    """
    sent = _send_inputs(events)
    if sent != len(events):
        raise RuntimeError(f"SendInput queued {sent} of {len(events)} input events")


def _send_paste_keystroke() -> None:
    """Press and release Ctrl+V. The only virtual keys this module ever sends.

    The order matters and is fixed by the sequence below: the modifier goes down
    first and comes up last, otherwise the "V" is a plain keystroke, not a paste.
    """
    events: list[INPUT] = []
    for vk, flags in ((VK_CONTROL, 0), (VK_V, 0),
                      (VK_V, KEYEVENTF_KEYUP), (VK_CONTROL, KEYEVENTF_KEYUP)):
        event = INPUT(type=INPUT_KEYBOARD)
        event.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0,
                              dwExtraInfo=0)
        events.append(event)
    _send_all(events)


# --- public API --------------------------------------------------------------

def insert_text(text: str, mode: str = "sendinput") -> None:
    """Type text into whatever control currently has focus.

    ``mode="sendinput"`` types the characters as KEYEVENTF_UNICODE events,
    ``mode="clipboard"`` puts the text on the clipboard and presses Ctrl+V.
    Any other mode raises ``ValueError``.

    No Enter/Return key press is ever synthesized, so the text is typed but not
    sent.
    """
    if mode == "sendinput":
        events = _build_input_events(build_unicode_inputs(text))
        if events:
            _send_all(events)
        return
    if mode == "clipboard":
        return insert_clipboard(text)
    raise ValueError(f"Unknown insert mode: {mode!r}. "
                     "Allowed values: clipboard, sendinput")


def insert_clipboard(text: str, *, settle: float = _PASTE_SETTLE_SECONDS) -> None:
    """Paste text into the focused control via the clipboard and Ctrl+V.

    ``settle`` is how long to wait after Ctrl+V before the clipboard is restored.
    Restoring immediately races the target application, which may not have read
    the clipboard yet, so the wait is what makes the paste actually land.

    The clipboard is restored in a ``finally`` block, so a failed paste cannot eat
    the user's clipboard text. The restore is unconditional: if the clipboard held
    no text before, it is cleared again rather than left holding the dictated
    text.
    """
    previous = _read_clipboard_text()
    try:
        _write_clipboard_text(text)
        _send_paste_keystroke()
    finally:
        _sleep(settle)
        if previous is None:
            _clear_clipboard()
        else:
            _write_clipboard_text(previous)


def _sleep(seconds: float) -> None:
    """Wait for the target application to consume the paste."""
    time.sleep(seconds)


# --- clipboard plumbing ------------------------------------------------------

def _read_clipboard_text() -> str | None:
    """Return the clipboard text, or None when the clipboard holds no text."""
    _open_clipboard()
    try:
        handle = _user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        pointer = _kernel32.GlobalLock(handle)
        if not pointer:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.wstring_at(pointer)
        finally:
            _kernel32.GlobalUnlock(handle)
    finally:
        _user32.CloseClipboard()


def _write_clipboard_text(text: str) -> None:
    """Replace the clipboard contents with text."""
    _open_clipboard()
    try:
        _user32.EmptyClipboard()
        buffer = ctypes.create_unicode_buffer(text)
        handle = _kernel32.GlobalAlloc(GMEM_MOVEABLE, ctypes.sizeof(buffer))
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        pointer = _kernel32.GlobalLock(handle)
        if not pointer:
            _kernel32.GlobalFree(handle)
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            ctypes.memmove(pointer, buffer, ctypes.sizeof(buffer))
        finally:
            _kernel32.GlobalUnlock(handle)
        if not _user32.SetClipboardData(CF_UNICODETEXT, handle):
            # The handle is still ours until SetClipboardData took ownership.
            _kernel32.GlobalFree(handle)
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        _user32.CloseClipboard()


def _clear_clipboard() -> None:
    """Empty the clipboard, leaving no text format behind."""
    _open_clipboard()
    try:
        _user32.EmptyClipboard()
    finally:
        _user32.CloseClipboard()


def _open_clipboard() -> None:
    if not _user32.OpenClipboard(None):
        raise ctypes.WinError(ctypes.get_last_error())
