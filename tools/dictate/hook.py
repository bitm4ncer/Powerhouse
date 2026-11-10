"""Push-to-talk capture for dictate: the mouse button that starts and stops it.

The button the user holds is also a button their applications already use: the
thumb-back button navigates back in Chrome and Explorer and switches tabs in
several editors. dictate therefore never merely *watches* the button - it
**swallows** it. The low-level mouse callback returns a non-zero value for every
event of the configured button, so the focused application is not told the
button happened at all.

Two layers, deliberately separated:

* :class:`HookState` is the whole behaviour of one button session and is a pure
  function of ``(kind, now)``. It holds no Win32 handle, no callback and no
  clock, so every transition can be tested exhaustively without Windows.
* :class:`MouseHook` is the thin Win32 wrapper around it: it installs
  ``WH_MOUSE_LL``, turns mouse messages into ``"down"`` / ``"up"`` / ``None``,
  feeds :class:`HookState`, swallows the button and pumps the message loop.

Example:

    from hook import MouseHook

    hook = MouseHook("XButton1", on_press=recorder.start,
                     on_release=recorder.stop, max_seconds=120)
    hook.run(on_ready=lambda: print("listening"))

:mod:`config` owns the user-facing names; this module takes them as plain
parameters, so nothing here depends on the configuration file.

The real ``SetWindowsHookExW`` call happens in :meth:`MouseHook.run` and nowhere
else - never at import time, and never in anything but the entry point a human
starts. A live ``WH_MOUSE_LL`` hook swallows the user's actual side button
system-wide, so the test suite reaches the whole Win32 surface through a
replaceable ``user32``/``kernel32`` seam instead.
"""

from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from typing import Callable

# The button names Config.mouse_button accepts. Duplicated here on purpose: this
# module takes a plain parameter and must not import the configuration module.
MOUSE_BUTTONS = ("XButton1", "XButton2", "Middle")

# --- Win32 constants ---------------------------------------------------------

# WH_MOUSE_LL is the only mouse hook that can see (and cancel) an event before
# the window it was aimed at ever hears about it.
WH_MOUSE_LL = 14
# HC_ACTION is the nCode of a real mouse event; anything else is not ours to read.
HC_ACTION = 0
WM_QUIT = 0x0012
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MBUTTONDBLCLK = 0x0209
WM_MOUSEWHEEL = 0x020A
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_XBUTTONDBLCLK = 0x020D
# The two X buttons, as they appear in the high word of MSLLHOOKSTRUCT.mouseData.
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002
PM_REMOVE = 0x0001

# Returning a non-zero value from a low-level mouse hook stops the event: the
# window it was aimed at never sees it. This is the whole reason for the hook.
SWALLOW_EVENT = 1

# --- Win32 structures --------------------------------------------------------

# ULONG_PTR is pointer-sized; ctypes.wintypes does not expose it.
_ULONG_PTR = ctypes.c_size_t

# LRESULT is a 32-bit LONG on Windows, even in a 64-bit process. WPARAM and LPARAM
# are pointer-sized, so c_void_p is what they marshal as.
_LRESULT = ctypes.c_long

# The signature of a WH_MOUSE_LL callback. WINFUNCTYPE, not CFUNCTYPE: the
# __stdcall calling convention is required, and ctypes defaults to cdecl on
# 32-bit Windows, where the two disagree about who cleans the stack.
HOOKPROC = ctypes.WINFUNCTYPE(
    _LRESULT, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p
)


class MSG(ctypes.Structure):
    """Win32 MSG - one message, as read by GetMessage."""

    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
        ("lPrivate", wintypes.DWORD),
    ]


class MSLLHOOKSTRUCT(ctypes.Structure):
    """Win32 MSLLHOOKSTRUCT - the mouse event a low-level hook receives.

    Only ``mouseData`` is read, and only its high word: that is where the X
    button identity (XBUTTON1 = 1, XBUTTON2 = 2) lives. The wheel uses the same
    field for a delta, which is why the message has to match too.
    """

    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


# --- Win32 API ---------------------------------------------------------------

# use_last_error keeps GetLastError meaningful: SetWindowsHookExW reports a
# failed installation by returning NULL, which is otherwise indistinguishable
# from a deliberate zero.
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD
]
_user32.SetWindowsHookExW.restype = wintypes.HHOOK
_user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
_user32.UnhookWindowsHookEx.restype = wintypes.BOOL
_user32.CallNextHookEx.argtypes = [
    wintypes.HHOOK, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p
]
_user32.CallNextHookEx.restype = _LRESULT
_user32.GetMessageW.argtypes = [
    ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT
]
_user32.GetMessageW.restype = wintypes.BOOL
_user32.PeekMessageW.argtypes = [
    ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT
]
_user32.PeekMessageW.restype = wintypes.BOOL
# PostThreadMessage lives in user32, next to the message queue it feeds.
_user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
]
_user32.PostThreadMessageW.restype = wintypes.BOOL

_kernel32.GetCurrentThreadId.argtypes = []
_kernel32.GetCurrentThreadId.restype = wintypes.DWORD

# --- clock -------------------------------------------------------------------

# One place reads the clock. It has to be monotonic: a wall-clock jump (an NTP
# correction, a daylight-saving change) must not fake a held button or shorten
# a recording.


def _now() -> float:
    """The current monotonic time in seconds."""
    return time.monotonic()


# --- event classification ----------------------------------------------------

# Down and up are the only messages that change the session. A double click is
# ours - it has to be swallowed or the application navigates back - but it opens
# nothing: the press/release pair around it does that.
_MIDDLE_MESSAGES = {
    WM_MBUTTONDOWN: "down",
    WM_MBUTTONUP: "up",
    WM_MBUTTONDBLCLK: None,
}
_XBUTTON_MESSAGES = {
    WM_XBUTTONDOWN: "down",
    WM_XBUTTONUP: "up",
    WM_XBUTTONDBLCLK: None,
}
_XBUTTON_HIGH_WORD = {"XButton1": XBUTTON1, "XButton2": XBUTTON2}


def _classify(message: int, mouse_data: int, button: str) -> tuple[str | None, bool]:
    """Decide what one hook event means, in two independent ways.

    Returns ``(kind, ours)``:

    * ``kind`` is ``"down"``, ``"up"`` or ``None`` - the transition to feed to
      :class:`HookState`. ``None`` means "this event changes nothing".
    * ``ours`` says whether the event belongs to the configured button at all,
      and therefore whether it has to be swallowed.

    The two are deliberately not the same thing. A release that arrives after
    the watchdog already cut the session off is ``None``/``ignore`` as a
    transition, and still ``ours`` - the application must not see it either, or
    Chrome navigates back a moment after the recording stopped. The same goes for
    the double-click message of the configured button.

    The message and the button identity are both required. A wheel event carries
    a value in ``mouseData`` too, and an X-button event identifies itself in the
    high word only, so either check alone would swallow the wrong hardware. Every
    other message - a movement, a click, the wheel - is simply not in the tables
    and is chained on unchanged.
    """
    if button == "Middle":
        if message not in _MIDDLE_MESSAGES:
            return None, False
        return _MIDDLE_MESSAGES[message], True
    if (mouse_data >> 16) != _XBUTTON_HIGH_WORD.get(button):
        return None, False
    if message not in _XBUTTON_MESSAGES:
        return None, False
    return _XBUTTON_MESSAGES[message], True


# --- the Win32 layer ---------------------------------------------------------

# How often the watchdog thread looks, in seconds. Bounded so a short limit
# still ends on time and a long one does not wake the thread thousands of times
# for nothing.
_WATCHDOG_MIN_INTERVAL = 0.02
_WATCHDOG_MAX_INTERVAL = 0.5


def _watchdog_interval(max_seconds: float) -> float:
    """Return how often the watchdog thread should check the limit."""
    return max(_WATCHDOG_MIN_INTERVAL,
               min(_WATCHDOG_MAX_INTERVAL, float(max_seconds) / 10.0))


def _install(proc: HOOKPROC):
    """Install the global low-level mouse hook and return its handle.

    hMod is NULL and the thread id is 0, which is what a low-level hook running
    in the installing process wants: the hook is global (every process, every
    thread) and needs no DLL of its own. Returns NULL on failure - see
    :meth:`MouseHook.run`.
    """
    return _user32.SetWindowsHookExW(WH_MOUSE_LL, proc, None, 0)


def _pump_messages() -> None:
    """Run the message loop until WM_QUIT arrives.

    A low-level hook is called on the thread that installed it, so that thread
    has to keep a message loop running - this is it. Messages are fetched and
    dropped: the hook sees mouse input directly, not through the queue, and
    nothing here has a window to dispatch to. GetMessageW returning 0 means
    WM_QUIT, i.e. stop() was called.
    """
    message = MSG()
    while _user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
        pass
    # WM_QUIT stays in the queue until it is removed; leaving it there means the
    # next message loop on this thread quits immediately.
    while _user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
        pass


class HookState:
    """The state of one push-to-talk session: idle, or recording.

    The whole behaviour is :meth:`handle`, a pure function of the event kind and
    the current time - no clock, no Win32, no side effects. What comes back is
    the action the caller has to take:

    * ``"start"`` - the button went down while idle; begin recording.
    * ``"stop"`` - the button was released, or the watchdog cut the session off.
    * ``"ignore"`` - nothing to do.

    Two properties matter and are both deliberate:

    * A second press while recording is ``"ignore"``. A button that auto-repeats
      (or a hand that rests on it) must never start a second recording.
    * A release that arrives *after* the watchdog already stopped is ``"ignore"``.
      The session is over; stopping again would close a recording that is no
      longer open.

    The watchdog is checked before anything else, so a held button is cut off at
    ``max_seconds`` even if it is never released, and the check happens on every
    event - including the ones unrelated to this button.
    """

    def __init__(self, max_seconds: float) -> None:
        self._max_seconds = float(max_seconds)
        self._started_at: float | None = None

    @property
    def recording(self) -> bool:
        """True while a session is open, i.e. the button is considered held."""
        return self._started_at is not None

    def handle(self, kind: str | None, now: float) -> str:
        """Feed one event in and return ``"start"``, ``"stop"`` or ``"ignore"``.

        ``kind`` is ``"down"`` for a press of the configured button, ``"up"`` for
        its release and ``None`` for every other mouse event. ``now`` is a
        monotonic timestamp in seconds; the same clock has to be used for every
        call, because only differences between calls are ever looked at.
        """
        started = self._started_at
        if started is not None:
            # The limit is inclusive: a session that has reached max_seconds is
            # over. Anything else would let a recording run past the configured
            # maximum until the very next event arrived.
            if now - started >= self._max_seconds:
                self._started_at = None
                return "stop"
            if kind == "up":
                self._started_at = None
                return "stop"
            return "ignore"
        if kind == "down":
            self._started_at = now
            return "start"
        return "ignore"

    def reset(self) -> bool:
        """Force the machine back to idle and report whether one was open.

        Used when the hook shuts down. A half-open session would make the next
        press look like a repeated one, so the next recording would never start.
        """
        was_recording = self._started_at is not None
        self._started_at = None
        return was_recording


class MouseHook:
    """Captures one mouse button system-wide and swallows it.

    ``button`` is one of :data:`MOUSE_BUTTONS`, ``on_press`` is called when the
    user starts holding it and ``on_release`` when they let go or when the
    watchdog cuts a too-long session off. ``max_seconds`` is that watchdog limit.

    Every event of ``button`` is swallowed, so the focused application - a
    browser, the editor, Explorer - never sees the button at all and never
    navigates back. That is what the Win32 layer is for; what the button *means*
    is :class:`HookState`.

    :meth:`run` is the only place that installs the real hook; it blocks pumping
    the message loop until :meth:`stop` is called, so it normally runs on its own
    thread. :meth:`stop` may be called from any thread.

    Example:

        hook = MouseHook("XButton1", recorder.start, recorder.stop, 120)
        thread = threading.Thread(target=hook.run, daemon=True)
        thread.start()
        ...
        hook.stop()

    A callback that raises must not take the hook down with it - the exception
    is recorded in :attr:`error` and the button is still swallowed. That is why
    nothing in the callback raises.
    """

    def __init__(
        self,
        button: str,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
        max_seconds: float,
    ) -> None:
        if button not in MOUSE_BUTTONS:
            raise ValueError(
                f"Unknown mouse button: {button!r}. "
                f"Allowed values: {', '.join(MOUSE_BUTTONS)}"
            )
        self.button = button
        self.error: str | None = None
        self._on_press = on_press
        self._on_release = on_release
        self._max_seconds = float(max_seconds)
        self._state = HookState(max_seconds=max_seconds)
        # The hook callback runs on the thread that installed it, while stop()
        # and the watchdog run elsewhere, so the state is shared.
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self._thread_id: int | None = None
        # Set once and never replaced while the hook is live: see _make_callback.
        self._proc: HOOKPROC | None = None

    @property
    def recording(self) -> bool:
        """True while a session is open; mirrors the state machine."""
        return self._state.recording

    # --- lifecycle -----------------------------------------------------------

    def run(self, on_ready: Callable[[], None] | None = None) -> None:
        """Install the hook and pump messages until :meth:`stop` is called.

        ``on_ready`` is called once the hook is live, so the caller can report
        "listening" without polling. It is *not* called if the installation
        fails: a silent failure here would look like a dead push-to-talk button,
        so that case raises instead.

        Installing and uninstalling happen exactly once each, whatever the
        message loop does in between.
        """
        if self._stopped.is_set():
            # stop() arrived before the hook ever started: there is nothing to
            # install and nothing to clean up.
            return
        proc = self._make_callback()
        handle = _install(proc)
        if not handle:
            # NULL is the only way SetWindowsHookExW reports failure, and it is
            # also the documented "no hook" value - refuse to run a dictation
            # tool whose button would silently do nothing.
            raise RuntimeError(
                f"The {self.button} push-to-talk hook could not be installed "
                f"(Windows error {ctypes.get_last_error()})"
            )
        # Publish the thread id before the second check, not after it. A stop()
        # arriving anywhere below this line can post WM_QUIT and the pump will
        # return it; a stop() arriving above it is caught by the check below.
        # The other order leaves a window with neither guarantee.
        self._thread_id = int(_kernel32.GetCurrentThreadId())
        if self._stopped.is_set():
            # stop() landed while the hook was being installed. It could not post
            # WM_QUIT - there was no thread id yet - so without this check the
            # pump would start, block forever, and leave a live global hook
            # swallowing the user's button with no way to stop it.
            self._uninstall(handle)
            return
        watchdog = threading.Thread(
            target=self._watch, name="dictate-hook-watchdog", daemon=True
        )
        try:
            watchdog.start()
            if on_ready is not None:
                on_ready()
            _pump_messages()
        finally:
            self._stopped.set()      # ends the watchdog thread
            self._uninstall(handle)
            if self._state.reset():
                # A session that was still open must not leave a microphone
                # recording: the user stopped the tool, not the utterance.
                self._call("on_release", self._on_release)
            if self.error is not None:
                raise RuntimeError(self.error)

    def stop(self) -> None:
        """Ask the message loop to end and mark the hook as stopped.

        Safe from any thread and safe to call twice, and safe to call before
        :meth:`run` - in which case :meth:`run` installs nothing at all, and also
        safe to call while :meth:`run` is still starting up. The hook itself is
        uninstalled by :meth:`run`, so it is removed exactly once.
        """
        self._stopped.set()
        with self._lock:
            thread_id = self._thread_id
        if thread_id is None:
            return
        # GetMessageW only returns when there is something to return, so a
        # message that is already in the queue is not enough: WM_QUIT is what
        # wakes the loop.
        _user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)

    # --- internals -----------------------------------------------------------

    def _make_callback(self) -> HOOKPROC:
        """Build the ctypes callback and keep it alive for the hook's lifetime.

        The reference is stored on the instance on purpose. A ctypes callback
        that gets garbage collected while Windows still holds its pointer makes
        the *next* mouse event jump into freed memory - the process dies without
        a traceback.
        """
        if self._proc is None:
            self._proc = HOOKPROC(self._callback)
        return self._proc

    def _callback(self, code: int, wparam: int, lparam: int) -> int:
        """The Win32 hook procedure. Runs on the thread that installed it.

        Returns 1 for every event of the configured button - the event is
        swallowed and the focused application never learns of it - and chains
        everything else on unchanged.
        """
        if code != HC_ACTION or not lparam:
            return self._chain(code, wparam, lparam)
        info = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        kind, ours = _classify(wparam, info.mouseData, self.button)
        if not ours:
            return self._chain(code, wparam, lparam)
        self._call("the mouse hook", self._dispatch, kind)
        return SWALLOW_EVENT

    def _chain(self, code: int, wparam: int, lparam: int) -> int:
        """Pass one event on to the next hook in the chain, untouched."""
        return int(_user32.CallNextHookEx(None, code, wparam, lparam))

    def _dispatch(self, kind: str | None) -> str:
        """Hand one event to the state machine and run the action it returns.

        The state machine is only touched under the lock, never while it is held
        are the user's callbacks - a callback that calls back into the hook would
        deadlock, and a slow one must not block the watchdog.
        """
        with self._lock:
            action = self._state.handle(kind, _now())
        if action == "start":
            self._call("on_press", self._on_press)
        elif action == "stop":
            self._call("on_release", self._on_release)
        return action

    def _watch(self) -> None:
        """End a too-long session even if the mouse never moves again.

        The state machine checks the limit on every event, which is enough while
        the user moves the mouse - and nothing at all while they hold the button
        perfectly still. This thread feeds it the events it would otherwise never
        see. It is the same ``None`` kind the hook passes for a mouse move, so
        there is exactly one rule for what ends a session.
        """
        interval = _watchdog_interval(self._max_seconds)
        while not self._stopped.wait(interval):
            self._call("the watchdog", self._dispatch, None)

    def _uninstall(self, handle) -> None:
        """Remove the hook; the one and only place that does."""
        _user32.UnhookWindowsHookEx(handle)

    def _call(self, label: str, function: Callable, *args) -> None:
        """Run one of our callbacks, recording the first failure instead of raising.

        Raising out of the hook procedure is not an option: the exception would
        cross back into Win32, and the button would be neither swallowed nor
        handled. Only the first problem is kept - the rest are consequences of
        it - and :meth:`run` raises it once the message loop has ended.
        """
        try:
            function(*args)
        except Exception as exc:
            if self.error is None:
                self.error = f"{label} failed: {exc}"
