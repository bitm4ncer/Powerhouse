"""Tests for the push-to-talk mouse hook.

The first five tests are the ones the task brief specifies verbatim. The rest
pin constraints the brief states in prose but never tests - above all that the
configured button is swallowed, that no test ever installs a real low-level
mouse hook, and that the hook shuts down cleanly.

Every Win32 constant and structure below is declared here, from the documented
Win32 ABI, rather than imported from the module under test. Importing them would
let a wrong value in hook.py satisfy its own assertion: renaming XBUTTON1 to 2
would make the hook capture the wrong button and still pass.
"""

import ast
import contextlib
import ctypes
import gc
import inspect
import subprocess
import sys
import threading
import time
import weakref
from collections import defaultdict
from ctypes import wintypes
from pathlib import Path

import pytest

# The test module reads the configuration on purpose; hook.py must not. See
# test_the_module_does_not_import_config below.
import config
import hook
from hook import HookState, MouseHook

# --- Win32 ABI, declared independently of hook.py -----------------------------

WH_MOUSE_LL = 14
WM_QUIT = 0x0012
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MBUTTONDBLCLK = 0x0209
WM_MOUSEWHEEL = 0x020A
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_XBUTTONDBLCLK = 0x020D
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002
HC_ACTION = 0
PM_REMOVE = 0x0001
# A non-zero return value is what makes a low-level hook swallow an event. This
# is the whole point of the module: the focused application must not see the
# button at all.
SWALLOW = 1

# POINT is two LONGs; MSLLHOOKSTRUCT is that point, three DWORDs and a
# pointer-sized extra-info value, padded out to the pointer alignment.
_EXPECTED_MSLLHOOKSTRUCT_SIZE = 32 if ctypes.sizeof(ctypes.c_void_p) == 8 else 24


class _MSLLHOOKSTRUCT(ctypes.Structure):
    """The struct a WH_MOUSE_LL hook receives in lParam - test-local copy."""

    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


def _event(message, *, button=0, low=0):
    """Return lParam for one hook event, with the button in the high word."""
    return ctypes.byref(_MSLLHOOKSTRUCT(mouseData=(button << 16) | low))


# --- tests from the brief ----------------------------------------------------

def test_down_then_up():
    s = HookState(max_seconds=120.0)
    assert s.handle("down", 0.0) == "start"
    assert s.handle("up", 1.0) == "stop"


def test_repeated_down_is_ignored():
    s = HookState(max_seconds=120.0)
    s.handle("down", 0.0)
    assert s.handle("down", 0.5) == "ignore"


def test_up_without_down_is_ignored():
    assert HookState(max_seconds=120.0).handle("up", 1.0) == "ignore"


def test_unrelated_event_is_ignored():
    assert HookState(max_seconds=120.0).handle(None, 1.0) == "ignore"


def test_watchdog_stops_a_held_button():
    s = HookState(max_seconds=120.0)
    s.handle("down", 100.0)
    assert s.handle(None, 260.0) == "stop"      # 160 s held -> forced stop
    assert s.handle("up", 261.0) == "ignore"    # late release must not stop twice


# --- the watchdog limit ------------------------------------------------------

def test_watchdog_does_not_fire_one_millisecond_early():
    s = HookState(max_seconds=120.0)
    assert s.handle("down", 0.0) == "start"
    assert s.handle(None, 119.999) == "ignore"
    assert s.recording


def test_watchdog_fires_exactly_at_the_limit():
    # The limit is inclusive. With a strict comparison the recording would run
    # past max_record_seconds until the next event happened to arrive.
    s = HookState(max_seconds=120.0)
    s.handle("down", 0.0)
    assert s.handle(None, 120.0) == "stop"
    assert not s.recording


def test_watchdog_beats_the_release_at_the_limit():
    s = HookState(max_seconds=120.0)
    s.handle("down", 0.0)
    assert s.handle("up", 120.0) == "stop"
    assert not s.recording


def test_a_new_session_starts_after_the_watchdog_cut_the_previous_one_off():
    s = HookState(max_seconds=120.0)
    s.handle("down", 0.0)
    assert s.handle(None, 130.0) == "stop"
    assert s.handle("down", 140.0) == "start"
    assert s.recording


def test_a_released_session_accepts_the_next_press():
    s = HookState(max_seconds=120.0)
    assert s.handle("down", 0.0) == "start"
    assert s.handle("up", 1.0) == "stop"
    assert s.handle("down", 2.0) == "start"


def test_only_down_and_up_are_special_kinds():
    # The state machine must not guess: anything that is not exactly "down" or
    # "up" is an event it has no opinion about.
    s = HookState(max_seconds=120.0)
    for kind in ("down-click", "DOWN", "", "press", 1):
        assert s.handle(kind, 0.0) == "ignore"
    assert not s.recording


def test_reset_returns_to_idle_and_reports_an_open_session():
    s = HookState(max_seconds=120.0)
    assert s.reset() is False
    s.handle("down", 0.0)
    assert s.reset() is True
    assert not s.recording
    # Idle again, so the next press is a first press rather than a repeat.
    assert s.handle("down", 1.0) == "start"


def test_max_seconds_may_be_a_short_limit():
    s = HookState(max_seconds=5)
    assert s.handle("down", 0.0) == "start"
    assert s.handle(None, 4.9) == "ignore"
    assert s.handle(None, 5.0) == "stop"


# --- event classification ----------------------------------------------------

@pytest.mark.parametrize("button,message,expected", [
    ("XButton1", WM_XBUTTONDOWN, "down"),
    ("XButton1", WM_XBUTTONUP, "up"),
    ("XButton2", WM_XBUTTONDOWN, "down"),
    ("XButton2", WM_XBUTTONUP, "up"),
    ("Middle", WM_MBUTTONDOWN, "down"),
    ("Middle", WM_MBUTTONUP, "up"),
])
def test_the_configured_button_is_classified(button, message, expected):
    high = XBUTTON1 if button == "XButton1" else XBUTTON2 if button == "XButton2" else 0
    kind, ours = hook._classify(message, high << 16, button)
    assert kind == expected
    assert ours is True


@pytest.mark.parametrize("button,message,high", [
    ("XButton1", WM_XBUTTONDOWN, XBUTTON2),   # the other thumb button
    ("XButton2", WM_XBUTTONDOWN, XBUTTON1),
    ("XButton1", WM_XBUTTONUP, XBUTTON2),
    ("Middle", WM_XBUTTONDOWN, XBUTTON1),     # an xbutton while Middle is ours
    ("XButton1", WM_MBUTTONDOWN, 0),          # the middle button
    ("XButton1", WM_MOUSEWHEEL, XBUTTON1),    # the wheel carries its own value
    ("XButton1", WM_MOUSEMOVE, 0),
    ("XButton1", WM_LBUTTONDOWN, 0),
])
def test_events_that_are_not_the_configured_button_are_passed_through(button, message, high):
    kind, ours = hook._classify(message, high << 16, button)
    assert kind is None
    assert ours is False


def test_the_button_lives_in_the_high_word_of_mouse_data():
    # XBUTTONDOWN without the button in the high word is not ours. Reading the
    # low word instead would swallow every X button on the mouse.
    assert hook._classify(WM_XBUTTONDOWN, XBUTTON1, "XButton1") == (None, False)
    assert hook._classify(WM_XBUTTONDOWN, XBUTTON1 << 16, "XButton1") == ("down", True)


def test_a_double_click_of_the_configured_button_is_still_swallowed():
    # Windows sends the second click of a fast pair as WM_XBUTTONDBLCLK. It
    # starts no session (that is the up/down pair that follows it), but it is
    # still our button and must not reach the application as a navigation.
    assert hook._classify(WM_XBUTTONDBLCLK, XBUTTON1 << 16, "XButton1") == (None, True)
    assert hook._classify(WM_MBUTTONDBLCLK, 0, "Middle") == (None, True)


# --- the callback: swallowing the button --------------------------------------

def _build_hook(button="XButton1", *, max_seconds=120.0, on_press=None, on_release=None):
    """A MouseHook whose callbacks record their calls."""
    log = []
    return MouseHook(
        button,
        on_press if on_press is not None else lambda: log.append("press"),
        on_release if on_release is not None else lambda: log.append("release"),
        max_seconds,
    ), log


def _proc(mouse_hook):
    """The ctypes callback, built without touching any Win32 function."""
    return mouse_hook._make_callback()


def test_a_press_is_swallowed_and_starts_a_session(monkeypatch):
    fake = FakeUser32()
    monkeypatch.setattr(hook, "_user32", fake)
    mouse_hook, log = _build_hook()
    assert _proc(mouse_hook)(HC_ACTION, WM_XBUTTONDOWN, _event(WM_XBUTTONDOWN, button=XBUTTON1)) == SWALLOW
    assert log == ["press"]
    assert fake.next_calls == []


def test_a_release_is_swallowed_and_stops_the_session(monkeypatch):
    fake = FakeUser32()
    monkeypatch.setattr(hook, "_user32", fake)
    mouse_hook, log = _build_hook()
    proc = _proc(mouse_hook)
    proc(HC_ACTION, WM_XBUTTONDOWN, _event(WM_XBUTTONDOWN, button=XBUTTON1))
    assert proc(HC_ACTION, WM_XBUTTONUP, _event(WM_XBUTTONUP, button=XBUTTON1)) == SWALLOW
    assert log == ["press", "release"]


def test_the_other_thumb_button_reaches_the_application(monkeypatch):
    fake = FakeUser32()
    monkeypatch.setattr(hook, "_user32", fake)
    mouse_hook, log = _build_hook("XButton1")
    proc = _proc(mouse_hook)
    assert proc(HC_ACTION, WM_XBUTTONDOWN, _event(WM_XBUTTONDOWN, button=XBUTTON2)) == 0
    assert log == []
    assert len(fake.next_calls) == 1, "an event we do not own must be chained on"


def test_ordinary_mouse_movement_reaches_the_application(monkeypatch):
    fake = FakeUser32()
    monkeypatch.setattr(hook, "_user32", fake)
    mouse_hook, log = _build_hook()
    proc = _proc(mouse_hook)
    assert proc(HC_ACTION, WM_MOUSEMOVE, _event(WM_MOUSEMOVE)) == 0
    assert proc(HC_ACTION, WM_MOUSEWHEEL, _event(WM_MOUSEWHEEL, low=120)) == 0
    assert log == []
    assert len(fake.next_calls) == 2


def test_a_non_action_code_is_never_touched(monkeypatch):
    # nCode < 0 means the hook was called about an error and lParam is not a
    # mouse event at all; nCode > 0 is reserved for the hook's own use.
    fake = FakeUser32()
    monkeypatch.setattr(hook, "_user32", fake)
    mouse_hook, _ = _build_hook()
    proc = _proc(mouse_hook)
    assert proc(1, WM_XBUTTONDOWN, _event(WM_XBUTTONDOWN, button=XBUTTON1)) == 0
    assert proc(-1, WM_XBUTTONDOWN, None) == 0
    assert len(fake.next_calls) == 2


def test_a_repeated_press_is_swallowed_but_does_not_start_a_second_session(monkeypatch):
    fake = FakeUser32()
    monkeypatch.setattr(hook, "_user32", fake)
    mouse_hook, log = _build_hook()
    proc = _proc(mouse_hook)
    proc(HC_ACTION, WM_XBUTTONDOWN, _event(WM_XBUTTONDOWN, button=XBUTTON1))
    assert proc(HC_ACTION, WM_XBUTTONDOWN, _event(WM_XBUTTONDOWN, button=XBUTTON1)) == SWALLOW
    assert log == ["press"]


def test_a_release_after_the_watchdog_is_still_swallowed(monkeypatch):
    # The product requirement is that the focused application never sees this
    # button. A release the state machine ignores is still ours to swallow, or
    # Chrome would navigate back half a second after the recording was cut off.
    fake = FakeUser32()
    monkeypatch.setattr(hook, "_user32", fake)
    mouse_hook, log = _build_hook(max_seconds=0.0)
    proc = _proc(mouse_hook)
    proc(HC_ACTION, WM_XBUTTONDOWN, _event(WM_XBUTTONDOWN, button=XBUTTON1))
    assert log == ["press"]
    # max_seconds=0 is already over, so the next event - the release - cuts it
    # off, and a further release must not stop anything twice.
    assert proc(HC_ACTION, WM_XBUTTONUP, _event(WM_XBUTTONUP, button=XBUTTON1)) == SWALLOW
    assert proc(HC_ACTION, WM_XBUTTONUP, _event(WM_XBUTTONUP, button=XBUTTON1)) == SWALLOW
    assert log == ["press", "release"]


def test_the_middle_button_is_swallowed_when_it_is_configured(monkeypatch):
    fake = FakeUser32()
    monkeypatch.setattr(hook, "_user32", fake)
    mouse_hook, log = _build_hook("Middle")
    proc = _proc(mouse_hook)
    assert proc(HC_ACTION, WM_MBUTTONDOWN, _event(WM_MBUTTONDOWN)) == SWALLOW
    assert proc(HC_ACTION, WM_MBUTTONUP, _event(WM_MBUTTONUP)) == SWALLOW
    assert log == ["press", "release"]


def test_an_unknown_button_is_rejected():
    with pytest.raises(ValueError, match="XButton1"):
        MouseHook("Back", lambda: None, lambda: None, 120.0)


def test_the_allowed_button_names_match_the_configuration():
    # Task 1 owns the user-facing names and Task 8 wires them in. Reading
    # config.MOUSE_BUTTONS here - not a literal copy of it - is the whole point:
    # a literal would keep passing after config.py changed the allowed values.
    assert hook.MOUSE_BUTTONS == config.MOUSE_BUTTONS


# --- running and stopping the hook -------------------------------------------

@contextlib.contextmanager
def _running(monkeypatch, *, on_press=None, on_release=None, **kwargs):
    """Run a MouseHook on a thread against fake user32/kernel32.

    Yields ``(mouse_hook, log, user32, kernel32, thread, errors)`` and always
    stops the hook afterwards. ``errors`` collects whatever run() raised, so a
    test can assert on a failure the loop only reports when it ends.
    """
    install_kwargs = kwargs.pop("install_kwargs", {})
    user32 = FakeUser32(**install_kwargs)
    kernel32 = FakeKernel32()
    monkeypatch.setattr(hook, "_user32", user32)
    monkeypatch.setattr(hook, "_kernel32", kernel32)
    mouse_hook, log = _build_hook(on_press=on_press, on_release=on_release, **kwargs)
    ready = threading.Event()
    errors = []

    def target():
        try:
            mouse_hook.run(on_ready=ready.set)
        except BaseException as exc:  # noqa: BLE001 - the test asserts on it
            errors.append(exc)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    try:
        assert ready.wait(5.0), "run() never reported the hook ready"
        yield mouse_hook, log, user32, kernel32, thread, errors
    finally:
        mouse_hook.stop()
        thread.join(5.0)


def test_run_installs_one_global_low_level_mouse_hook(monkeypatch):
    # WH_MOUSE_LL with thread id 0 is a *global* hook: every process, every
    # thread. hMod is NULL because a low-level hook runs inside this process and
    # needs no DLL of its own; anything else fails the installation outright.
    with _running(monkeypatch) as (mouse_hook, _, user32, kernel32, _, _):
        assert len(user32.installs) == 1
        install = user32.installs[0]
        assert install["id"] == WH_MOUSE_LL
        assert install["hmod"] is None
        assert install["thread_id"] == 0
        assert callable(install["proc"])
        assert install["proc"] is mouse_hook._proc


def test_run_reports_ready_exactly_once_after_the_hook_is_live(monkeypatch):
    calls = []
    user32 = FakeUser32()
    monkeypatch.setattr(hook, "_user32", user32)
    monkeypatch.setattr(hook, "_kernel32", FakeKernel32())
    mouse_hook, _ = _build_hook()
    thread = threading.Thread(
        target=mouse_hook.run, kwargs={"on_ready": lambda: calls.append(1)},
        daemon=True,
    )
    thread.start()
    for _ in range(200):
        if calls:
            break
        threading.Event().wait(0.01)
    try:
        assert calls == [1]
        assert len(user32.installs) == 1, "ready must not be reported before the install"
    finally:
        mouse_hook.stop()
        thread.join(5.0)


def test_a_failed_installation_is_surfaced_instead_of_pretending(monkeypatch):
    # SetWindowsHookExW reports failure by returning NULL. A dictation tool that
    # quietly carries on would leave the user holding a button that does nothing
    # and no idea why - so run() has to fail loudly instead.
    user32 = FakeUser32(install_handle=0)
    monkeypatch.setattr(hook, "_user32", user32)
    monkeypatch.setattr(hook, "_kernel32", FakeKernel32())
    ready = []
    mouse_hook, _ = _build_hook()
    with pytest.raises(RuntimeError, match="hook could not be installed"):
        mouse_hook.run(on_ready=lambda: ready.append(1))
    assert ready == []
    assert user32.unhooks == []
    assert user32.get_message_calls == 0, "no message loop without a hook"


def test_stop_wakes_the_pump_with_wm_quit(monkeypatch):
    # GetMessageW blocks until a message arrives, so without a posted WM_QUIT a
    # stop() from another thread would never come back.
    with _running(monkeypatch) as (mouse_hook, _, user32, _, _, _):
        mouse_hook.stop()
        user32.quit.wait(5.0)
        assert user32.posts == [(4242, WM_QUIT, 0, 0)]


def test_stop_unhooks_exactly_once_however_often_it_is_called(monkeypatch):
    with _running(monkeypatch) as (mouse_hook, _, user32, _, thread, _):
        mouse_hook.stop()
        mouse_hook.stop()
        thread.join(5.0)
    assert not thread.is_alive()
    assert user32.unhooks == [1], "the hook must be removed once, not twice"
    assert user32.get_message_calls >= 1
    assert user32.peek_message_calls >= 1, "WM_QUIT has to leave the queue"


def test_the_queue_is_drained_of_every_remaining_message(monkeypatch):
    # A WM_QUIT left in the queue makes the *next* message loop on this thread
    # quit immediately, so the pump removes it - and keeps removing until the
    # queue says it is empty.
    with _running(monkeypatch, install_kwargs={"peek_results": [1, 1, 0]}) as (
        mouse_hook, _, user32, _, thread, _
    ):
        mouse_hook.stop()
        thread.join(5.0)
    assert user32.peek_message_calls == 3


def test_stopping_before_running_never_installs_a_hook(monkeypatch):
    user32 = FakeUser32()
    monkeypatch.setattr(hook, "_user32", user32)
    monkeypatch.setattr(hook, "_kernel32", FakeKernel32())
    mouse_hook, log = _build_hook()
    mouse_hook.stop()
    mouse_hook.run(on_ready=lambda: pytest.fail("never ready"))
    assert user32.installs == []
    assert log == []


def _assert_a_stop_during_startup_left_nothing_behind(user32, thread):
    """A hook installed while a stop() was already on its way must not survive."""
    thread.join(5.0)
    assert not thread.is_alive(), (
        "run() never returned, so a live global hook is still swallowing the "
        "user's mouse button with no way to stop it")
    assert [install["id"] for install in user32.installs] == [WH_MOUSE_LL]
    assert user32.unhooks == [1], "the hook that was installed must be removed"
    assert user32.get_message_calls == 0, "no message loop may start after a stop"


def test_a_stop_during_the_install_does_not_strand_the_hook(monkeypatch):
    # The window between SetWindowsHookExW and publishing the thread id is real.
    # A stop() there sets the stopped flag and has no thread to post WM_QUIT to,
    # so without a second check the pump would start and block on a live global
    # WH_MOUSE_LL hook that can only be gone if the process dies.
    user32 = FakeUser32()
    kernel32 = FakeKernel32()
    monkeypatch.setattr(hook, "_user32", user32)
    monkeypatch.setattr(hook, "_kernel32", kernel32)
    mouse_hook, _ = _build_hook()
    user32.on_install = mouse_hook.stop
    thread = threading.Thread(target=mouse_hook.run, daemon=True)
    thread.start()
    _assert_a_stop_during_startup_left_nothing_behind(user32, thread)


def test_a_stop_before_the_thread_id_is_known_does_not_strand_the_hook(monkeypatch):
    # The same race one line further along: stop() runs while the thread id is
    # still being looked up, so it cannot be posted either. Publishing the id
    # before re-checking the flag is what keeps this window shut.
    user32 = FakeUser32()
    kernel32 = FakeKernel32()
    monkeypatch.setattr(hook, "_user32", user32)
    monkeypatch.setattr(hook, "_kernel32", kernel32)
    mouse_hook, _ = _build_hook()
    kernel32.on_current_thread_id = mouse_hook.stop
    thread = threading.Thread(target=mouse_hook.run, daemon=True)
    thread.start()
    _assert_a_stop_during_startup_left_nothing_behind(user32, thread)


def test_running_again_after_a_stop_installs_nothing(monkeypatch):
    # run() is a one-shot entry point. A second run() after a stop() must not
    # install a second hook on top of the first one.
    with _running(monkeypatch) as (mouse_hook, _, user32, _, thread, _):
        mouse_hook.stop()
        thread.join(5.0)
        assert len(user32.installs) == 1
        mouse_hook.run(on_ready=lambda: pytest.fail("never ready"))
    assert len(user32.installs) == 1


def test_shutting_down_releases_a_session_that_was_still_open(monkeypatch):
    # A half-open session would make the next press look like a repeat, so the
    # next recording would never start - and the microphone would stay open.
    with _running(monkeypatch) as (mouse_hook, log, _, _, _, _):
        mouse_hook._dispatch("down")
        assert log == ["press"]
    assert log == ["press", "release"]
    assert not mouse_hook.recording


def test_the_callback_object_stays_alive_for_the_life_of_the_hook(monkeypatch):
    # The ctypes callback must outlive the hook. If it is garbage collected
    # while Windows still holds its pointer, the next mouse event jumps into
    # freed memory and the process dies without a traceback.
    with _running(monkeypatch) as (mouse_hook, _, user32, _, _, _):
        installed = user32.installs[0]["proc"]
        reference = weakref.ref(installed)
        user32.installs.clear()
        del installed
        gc.collect()
        assert reference() is not None, "the hook callback was garbage collected"
        assert mouse_hook._proc is reference()


def test_a_failing_callback_never_reaches_win32(monkeypatch):
    # An exception crossing back into the hook procedure is undefined behaviour
    # and loses the swallow. The button must still be swallowed, and the failure
    # has to be reported somewhere the caller can see it.
    user32 = FakeUser32()
    monkeypatch.setattr(hook, "_user32", user32)
    mouse_hook, _ = _build_hook(on_press=lambda: 1 / 0)
    proc = mouse_hook._make_callback()
    assert proc(HC_ACTION, WM_XBUTTONDOWN, _event(WM_XBUTTONDOWN, button=XBUTTON1)) == SWALLOW
    assert "on_press" in mouse_hook.error
    # Still working afterwards.
    assert proc(HC_ACTION, WM_XBUTTONUP, _event(WM_XBUTTONUP, button=XBUTTON1)) == SWALLOW
    assert mouse_hook.error.count("on_press") == 1, "only the first failure is kept"


def test_run_reports_the_first_callback_failure_when_the_loop_ends(monkeypatch):
    with _running(monkeypatch, on_press=lambda: 1 / 0) as (mouse_hook, _, _, _, _, errors):
        mouse_hook._dispatch("down")
    assert any(isinstance(exc, RuntimeError) and "on_press" in str(exc)
               for exc in errors), errors


# --- the watchdog thread -----------------------------------------------------

def test_the_watchdog_ends_a_button_that_is_never_released(monkeypatch):
    # The state machine only gets to look at its limit when an event arrives.
    # A user who holds the button perfectly still produces no events at all, so
    # without the watchdog thread the recording would run until they let go -
    # minutes later, if ever.
    log = []
    with _running(monkeypatch, max_seconds=0.05,
                  on_press=lambda: log.append("press"),
                  on_release=lambda: log.append("release")) as (
        mouse_hook, _, _, _, _, errors
    ):
        mouse_hook._dispatch("down")
        # The deadline below sits well inside the fake pump's own 30 s block, so
        # it can only be satisfied by the watchdog: the shutdown path releases
        # an open session too, and must not be able to rescue this test.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and log != ["press", "release"]:
            threading.Event().wait(0.01)
        assert log == ["press", "release"], "a held button was never cut off"
    assert not mouse_hook.recording
    assert errors == []


def test_the_watchdog_never_fires_a_session_that_ends_in_time(monkeypatch):
    with _running(monkeypatch, max_seconds=30.0) as (mouse_hook, log, _, _, _, _):
        mouse_hook._dispatch("down")
        threading.Event().wait(0.5)   # many watchdog ticks, nowhere near 30 s
        assert log == ["press"], "the watchdog fired on a session inside its limit"
        mouse_hook._dispatch("up")
    assert log == ["press", "release"]


def test_the_watchdog_interval_is_bounded():
    assert hook._watchdog_interval(0.01) == hook._WATCHDOG_MIN_INTERVAL
    assert hook._watchdog_interval(120.0) == hook._WATCHDOG_MAX_INTERVAL
    assert hook._watchdog_interval(0.5) == pytest.approx(0.05)


# --- no real hook outside run() ----------------------------------------------

def test_nothing_outside_run_touches_the_windows_hook_api(monkeypatch):
    # The safety rule: a live WH_MOUSE_LL hook swallows the user's actual side
    # button system-wide. Only run() - which a human starts deliberately - may
    # go near it.
    user32 = Tripwire()
    kernel32 = Tripwire()
    monkeypatch.setattr(hook, "_user32", user32)
    monkeypatch.setattr(hook, "_kernel32", kernel32)
    mouse_hook, log = _build_hook()
    proc = mouse_hook._make_callback()
    assert proc(HC_ACTION, WM_XBUTTONDOWN, _event(WM_XBUTTONDOWN, button=XBUTTON1)) == SWALLOW
    assert proc(HC_ACTION, WM_XBUTTONUP, _event(WM_XBUTTONUP, button=XBUTTON1)) == SWALLOW
    mouse_hook.stop()
    mouse_hook.run(on_ready=lambda: pytest.fail("never ready"))
    assert log == ["press", "release"]
    assert user32.calls == [] and kernel32.calls == []


@pytest.mark.parametrize("api", [
    "SetWindowsHookExW", "UnhookWindowsHookEx", "GetMessageW", "PeekMessageW",
    "PostThreadMessageW",
])
def test_each_win32_hook_api_is_called_from_exactly_one_function(api):
    # "Installed once, removed once" is a property of the code, not of any one
    # test run: two call sites for UnhookWindowsHookEx would mean a hook that
    # removes itself twice depending on which path is taken.
    callers = defaultdict(list)

    def walk(node, enclosing):
        for child in ast.iter_child_nodes(node):
            name = child.name if isinstance(child, (ast.FunctionDef,)) else enclosing
            if (isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
                    and child.func.attr == api):
                callers[name].append(child.lineno)
            walk(child, name)

    walk(ast.parse(inspect.getsource(hook)), "<module>")
    assert len(callers) == 1, f"{api} is called from {dict(callers)}"
    assert len(next(iter(callers.values()))) == 1, f"{api} has several call sites"


def test_the_hook_install_is_only_reachable_from_run():
    # The one caller of SetWindowsHookExW is _install; nothing but run() calls it.
    callers = defaultdict(list)

    def walk(node, enclosing):
        for child in ast.iter_child_nodes(node):
            name = child.name if isinstance(child, ast.FunctionDef) else enclosing
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                callers[child.func.id].append(name)
            walk(child, name)

    walk(ast.parse(inspect.getsource(hook)), "<module>")
    assert callers.get("_install") == ["run"], (
        f"the hook is installed from {callers.get('_install')}")


def test_importing_the_module_installs_no_hook():
    # Fresh interpreter, so nothing this suite did can hide here. ctypes.WinDLL
    # is replaced by a stand-in that fails on any real call, and hook is
    # imported behind it: the module may declare prototypes, never act.
    script = _IMPORT_TRIPWIRE_SCRIPT
    root = str(hook.__file__).rsplit("hook.py", 1)[0]
    result = subprocess.run(
        [sys.executable, "-c", script, root],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "NO_WIN32_CALLS_AT_IMPORT", result.stdout


# --- module structure --------------------------------------------------------

def _module_tree():
    return ast.parse(Path(hook.__file__).read_text(encoding="utf-8"))


def _top_level_imports(tree):
    """The modules imported at module scope, not inside a function."""
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def _imports_anywhere(tree):
    """Every module the source imports, wherever the import sits."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_the_module_does_not_import_config():
    # Task 8 passes the settings in; reading the config here would tie the hook
    # to a file it has no business knowing about - and would make the button and
    # the watchdog limit impossible to inject in a test.
    assert "config" not in _top_level_imports(_module_tree())


def test_nothing_in_the_module_imports_config_either():
    # Same rule, not just at module scope: an import tucked inside a function is
    # just as much a dependency on the config file, and just as invisible to the
    # test above.
    assert "config" not in _imports_anywhere(_module_tree())


# --- the struct the hook reads ------------------------------------------------

def test_the_hook_struct_has_the_size_win32_expects():
    # A struct that is missing a field or has the wrong types shifts mouseData,
    # and the high word - the button identity - would read as garbage. Every
    # X button would then be either swallowed or passed through at random.
    assert ctypes.sizeof(hook.MSLLHOOKSTRUCT) == _EXPECTED_MSLLHOOKSTRUCT_SIZE, (
        f"MSLLHOOKSTRUCT is {ctypes.sizeof(hook.MSLLHOOKSTRUCT)} bytes, "
        f"the Win32 ABI requires {_EXPECTED_MSLLHOOKSTRUCT_SIZE} on this platform")


def test_the_hook_struct_has_the_win32_field_order():
    # mouseData is the third field; reordering the struct silently breaks the
    # button identity without changing the total size.
    assert [name for name, _ in hook.MSLLHOOKSTRUCT._fields_] == [
        "pt", "mouseData", "flags", "time", "dwExtraInfo"
    ]


# --- test doubles -------------------------------------------------------------

class FakeUser32:
    """Stands in for user32: records every call, hooks nothing.

    GetMessageW blocks until stop() posts WM_QUIT, so a test can run the real
    message pump without Windows ever seeing it.
    """

    def __init__(self, install_handle=1, thread_id=4242, peek_results=(0,),
                 message_wait=30.0):
        self.install_handle = install_handle
        self.thread_id = thread_id
        self.peek_results = list(peek_results)
        # Called from inside SetWindowsHookExW, on the installing thread. That is
        # how a stop() arriving during start-up can be timed exactly.
        self.on_install = None
        # How long a single GetMessageW blocks before it gives up. Long enough
        # that a test can tell "the watchdog fired" from "the pump timed out and
        # the hook shut down", which is what releases an open session.
        self.message_wait = message_wait
        self.installs = []
        self.unhooks = []
        self.next_calls = []
        self.posts = []
        self.get_message_calls = 0
        self.peek_message_calls = 0
        self.quit = threading.Event()

    def SetWindowsHookExW(self, hook_id, proc, hmod, thread_id):
        self.installs.append({"id": hook_id, "proc": proc, "hmod": hmod,
                              "thread_id": thread_id})
        if self.on_install is not None:
            self.on_install()
        return self.install_handle

    def UnhookWindowsHookEx(self, handle):
        self.unhooks.append(handle)
        return 1

    def CallNextHookEx(self, hhk, code, wparam, lparam):
        self.next_calls.append((code, wparam, lparam))
        return 0

    def GetMessageW(self, message, hwnd, filter_min, filter_max):
        self.get_message_calls += 1
        self.quit.wait(self.message_wait)
        return 0  # 0 from GetMessage means WM_QUIT

    def PeekMessageW(self, message, hwnd, filter_min, filter_max, flags):
        self.peek_message_calls += 1
        return self.peek_results.pop(0) if self.peek_results else 0

    def PostThreadMessageW(self, thread_id, message, wparam, lparam):
        self.posts.append((thread_id, message, wparam, lparam))
        if message == WM_QUIT:
            self.quit.set()
        return 1


class FakeKernel32:
    """Stands in for kernel32: only the thread id the hook loop needs."""

    def __init__(self, thread_id=4242):
        self.thread_id = thread_id
        self.thread_id_calls = 0
        # Called from inside GetCurrentThreadId - the second start-up window.
        self.on_current_thread_id = None

    def GetCurrentThreadId(self):
        self.thread_id_calls += 1
        if self.on_current_thread_id is not None:
            self.on_current_thread_id()
        return self.thread_id


class Tripwire:
    """A DLL stand-in that fails on every single call.

    Reaching one of these means the code under test talked to Win32 where the
    test did not allow it - which, for a live WH_MOUSE_LL hook, would mean
    swallowing the user's real mouse button.
    """

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def record(*args):
            self.calls.append(name)
            raise AssertionError(f"Win32 call {name!r} is not allowed here")
        return record


# Imports hook in a fresh interpreter with ctypes.WinDLL replaced by a stand-in
# that records any real call. argv[1] is the directory holding hook.py.
_IMPORT_TRIPWIRE_SCRIPT = r"""
import ctypes, sys

calls = []


class TripwireDLL:
    def __init__(self, name):
        self._name = name

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def record(*args, **kwargs):
            calls.append(self._name + "." + name)
            return 0

        return record


ctypes.WinDLL = lambda name, *a, **k: TripwireDLL(name)
sys.path.insert(0, sys.argv[1])

import hook  # noqa: F401

print("WIN32_CALLS_AT_IMPORT:" + repr(calls) if calls
      else "NO_WIN32_CALLS_AT_IMPORT")
"""
