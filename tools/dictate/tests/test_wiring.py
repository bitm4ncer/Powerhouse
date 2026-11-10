"""Tests for the entry point, the autostart launcher and the wiring between them.

The five tests the brief specifies verbatim come first. The rest pin the
constraints this layer is responsible for and that nothing below it enforces:
that a failed recognition is shown to the user instead of quietly typing
nothing, that a recognition which never returns cannot wedge a push-to-talk
session, that the mouse hook is installed off the main thread (pystray's
``run`` wants the main thread) while the button callback only queues work
(Windows drops a low-level hook callback that takes longer than
``LowLevelHooksTimeout``), that a configured microphone which does not resolve -
by name or by index - is reported rather than silently replaced by the system
default, and that a device which refuses 16 kHz is passed over for one that
accepts it.

Everything that can be decided without Windows, without a microphone and
without a GPU is decided here through explicit seams: :mod:`dictate` builds its
recorder, transcriber, hook and tray through four factories, the recognition
runs through ``transcribe_bounded``, and the audio the recognizer is asked to
recognise comes from a WAV file written by the test.
"""

import subprocess
import sys
import threading
import time
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import autostart
import config
import dictate
import hook as hook_module
from autostart import VBS_TEMPLATE, autostart_command
from config import Config
from dictate import accept_press
from tray import Tray

# --- the values the brief fixes, declared here and not read from the module ----

# The only tray states that accept a new press. Spelled out here so that a
# changed gate fails the test instead of redefining what the test means.
_ACCEPTING_STATES = ("ready", "error")
_REJECTING_STATES = ("recording", "transcribing", "", "idle", "READY")

# The launcher file the Startup folder gets, and the window style that keeps it
# invisible: 0 is WScript's "hidden window".
_LAUNCHER_NAME = "dictate.vbs"
_HIDDEN_WINDOW_STYLE = ", 0, False"

# A device list shaped like sounddevice.query_devices() returns it. Two host
# APIs expose the same microphone name, which is exactly the WASAPI case: the
# first match may refuse 16 kHz while the second one accepts it.
_DEVICES = [
    {"name": "Speakers (Realtek Audio)", "hostapi": "MME", "max_input_channels": 0,
     "max_output_channels": 2, "default_samplerate": 48000.0},
    {"name": "Microphone (Realtek Audio)", "hostapi": "MME", "max_input_channels": 2,
     "max_output_channels": 0, "default_samplerate": 48000.0},
    {"name": "Microphone (Realtek Audio)", "hostapi": "WASAPI", "max_input_channels": 2,
     "max_output_channels": 0, "default_samplerate": 48000.0},
]
_MIC_NAME = "Microphone (Realtek Audio)"
_MIC_MME = 1
_MIC_WASAPI = 2

# The seven command line switches, and exactly what they parse to.
_EXPECTED_CLI = {
    "file": Path("a.wav"),
    "print": True,
    "config": Path("c.json"),
    "install_autostart": True,
    "uninstall_autostart": True,
    "list_devices": True,
    "no_tray": True,
}
_EXPECTED_CLI_EMPTY = {
    "file": None, "print": False, "config": None, "install_autostart": False,
    "uninstall_autostart": False, "list_devices": False, "no_tray": False,
}

# The exit code of a run that did what it was asked to.
_EXIT_OK = 0


# --- the five tests the brief specifies ---------------------------------------

def test_press_rejected_while_transcribing():
    assert accept_press("transcribing") is False


def test_press_accepted_when_ready_or_error():
    assert accept_press("ready") is True
    assert accept_press("error") is True


def test_press_rejected_while_already_recording():
    assert accept_press("recording") is False


def test_autostart_command_is_hidden_and_quoted():
    cmd = autostart_command(Path(r"C:\v\pythonw.exe"), Path(r"C:\t\dictate.py"))
    assert "pythonw.exe" in cmd and "dictate.py" in cmd
    assert cmd.count('"') == 4  # both paths quoted


def test_vbs_template_uses_a_placeholder_pair():
    assert VBS_TEMPLATE.count("{command}") == 1


# --- the gate itself ----------------------------------------------------------

def test_the_gate_accepts_exactly_the_two_declared_states():
    for state in _ACCEPTING_STATES:
        assert accept_press(state) is True, state
    for state in _REJECTING_STATES:
        assert accept_press(state) is False, state


def test_the_gate_needs_nothing_but_its_argument():
    # The gate is the thing that decides whether a press is allowed, so it has
    # to be decidable from the state alone - no pipeline, no clock, no hook.
    assert [accept_press(s) for s in _ACCEPTING_STATES + _REJECTING_STATES] == \
        [True, True, False, False, False, False, False]


# --- the autostart launcher ---------------------------------------------------

def test_autostart_command_quotes_both_paths_exactly_once():
    cmd = autostart_command(Path(r"C:\v env\pythonw.exe"), Path(r"C:\t\dictate.py"))
    assert cmd == f'"{Path(r"C:\v env\pythonw.exe")}" "{Path(r"C:\t\dictate.py")}"'


def test_autostart_command_names_the_script_and_nothing_else():
    cmd = autostart_command(Path(r"C:\v\pythonw.exe"), Path(r"C:\t\dictate.py"))
    assert cmd.count("pythonw") == 1
    assert cmd.endswith(f'"{Path(r"C:\t\dictate.py")}"')


def test_pythonw_sits_next_to_the_interpreter():
    assert autostart.pythonw_for(Path(r"C:\v\Scripts\python.exe")) == \
        Path(r"C:\v\Scripts\pythonw.exe")


def test_pythonw_of_an_already_windowless_interpreter_is_itself():
    assert autostart.pythonw_for(Path(r"C:\v\pythonw.exe")) == Path(r"C:\v\pythonw.exe")


def test_the_interpreter_this_process_runs_under_launches_through_pythonw():
    # The autostart entry points at this very environment, so python.exe must
    # never end up in the launcher - a console window would flash on logon.
    assert autostart.pythonw_for(Path(sys.executable)).name == "pythonw.exe"


def test_the_startup_folder_is_the_shell_startup_folder(monkeypatch):
    monkeypatch.setenv("APPDATA", r"C:\Users\dude\AppData\Roaming")
    assert autostart.startup_folder() == \
        Path(r"C:\Users\dude\AppData\Roaming") / "Microsoft" / "Windows" / \
        "Start Menu" / "Programs" / "Startup"


def test_install_autostart_writes_a_hidden_launcher_into_the_startup_folder(
    tmp_path, monkeypatch
):
    startup = tmp_path / "Startup"
    startup.mkdir()
    monkeypatch.setattr(autostart, "startup_folder", lambda: startup)
    monkeypatch.setattr(autostart, "pythonw_for",
                        lambda python: Path(r"C:\v\Scripts\pythonw.exe"))

    written = autostart.install_autostart(Path(r"C:\t\dictate.py"))

    assert written == startup / _LAUNCHER_NAME
    body = written.read_text(encoding="utf-8")
    assert f'"{Path(r"C:\v\Scripts\pythonw.exe")}" "{Path(r"C:\t\dictate.py")}"' \
        .replace('"', '""') in body
    assert _HIDDEN_WINDOW_STYLE in body
    assert "{command}" not in body


def test_install_autostart_is_idempotent(tmp_path, monkeypatch):
    startup = tmp_path / "Startup"
    startup.mkdir()
    monkeypatch.setattr(autostart, "startup_folder", lambda: startup)
    monkeypatch.setattr(autostart, "pythonw_for", lambda python: Path("pythonw.exe"))

    first = autostart.install_autostart(Path(r"C:\t\dictate.py"))
    body = first.read_text(encoding="utf-8")
    second = autostart.install_autostart(Path(r"C:\t\dictate.py"))

    assert first == second
    assert second.read_text(encoding="utf-8") == body
    assert len(list(startup.iterdir())) == 1


def test_uninstall_autostart_removes_the_launcher(tmp_path, monkeypatch):
    startup = tmp_path / "Startup"
    startup.mkdir()
    monkeypatch.setattr(autostart, "startup_folder", lambda: startup)
    monkeypatch.setattr(autostart, "pythonw_for", lambda python: Path("pythonw.exe"))
    autostart.install_autostart(Path(r"C:\t\dictate.py"))

    assert autostart.uninstall_autostart() is None
    assert not (startup / _LAUNCHER_NAME).exists()


def test_uninstall_autostart_without_a_launcher_does_nothing(tmp_path, monkeypatch):
    startup = tmp_path / "Startup"
    startup.mkdir()
    monkeypatch.setattr(autostart, "startup_folder", lambda: startup)
    assert autostart.uninstall_autostart() is None


def test_a_missing_startup_folder_is_created(tmp_path, monkeypatch):
    startup = tmp_path / "Startup" / "Programs" / "Startup"
    monkeypatch.setattr(autostart, "startup_folder", lambda: startup)
    monkeypatch.setattr(autostart, "pythonw_for", lambda python: Path("pythonw.exe"))

    assert autostart.install_autostart(Path(r"C:\t\dictate.py")).is_file()


def test_the_launched_command_is_hidden_and_quoted_after_substitution():
    command = autostart_command(Path(r"C:\v\pythonw.exe"), Path(r"C:\t\dictate.py"))
    body = autostart.launcher_body(command)
    # One VBScript string literal: its own opening quote, then the command with
    # every quote of its own doubled, then its own closing quote.
    assert body == (
        'CreateObject("WScript.Shell").Run '
        f'"""C:\\v\\pythonw.exe"" ""C:\\t\\dictate.py"""{_HIDDEN_WINDOW_STYLE}'
    )


def test_the_commands_quotes_are_doubled_for_the_vbscript_literal():
    # A command line is full of double quotes, and a VBScript string literal
    # writes each of them twice. Without that the launcher does not compile and
    # the tool silently never starts at logon - see the compile test below.
    command = autostart_command(Path(r"C:\v\pythonw.exe"), Path(r"C:\t\dictate.py"))
    body = autostart.launcher_body(command)
    assert command.count('"') == 4
    assert body.count('""') == 4
    assert command not in body


def test_the_generated_launcher_compiles(tmp_path, monkeypatch):
    # The only test that runs the real VBScript compiler over the real
    # generated file. cscript both compiles and runs a script, so the command
    # under test is a no-op ("cmd /c rem") rather than dictate itself.
    startup = tmp_path / "Startup"
    startup.mkdir()
    monkeypatch.setattr(autostart, "startup_folder", lambda: startup)
    monkeypatch.setattr(autostart, "pythonw_for", lambda python: Path("pythonw.exe"))
    launcher = tmp_path / "check.vbs"
    launcher.write_text(autostart.launcher_body('"cmd" "/c" "rem"'),
                        encoding="utf-8", newline="\r\n")
    try:
        compiled = subprocess.run(
            ["cscript.exe", "//nologo", str(launcher)],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"cscript.exe is not usable here ({exc})")

    assert compiled.returncode == 0, compiled.stdout + compiled.stderr


def test_the_launcher_the_autostart_entry_point_writes_compiles(tmp_path, monkeypatch):
    # Same check on the file install_autostart() actually produces - the one
    # that runs at every logon.
    startup = tmp_path / "Startup"
    startup.mkdir()
    monkeypatch.setattr(autostart, "startup_folder", lambda: startup)
    monkeypatch.setattr(autostart, "pythonw_for", lambda python: Path("pythonw.exe"))
    launcher = autostart.install_autostart(tmp_path / "dictate.py")
    # The interpreter path is the real one but the script does not exist, so the
    # launcher starts pythonw once with a path that is not there: it exits
    # immediately, silently, and nothing is typed.
    try:
        compiled = subprocess.run(
            ["cscript.exe", "//nologo", str(launcher)],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"cscript.exe is not usable here ({exc})")

    assert compiled.returncode == 0, compiled.stdout + compiled.stderr


# --- fakes --------------------------------------------------------------------

_EMPTY_AUDIO = np.empty(0, dtype=np.float32)
_TONE = np.zeros(1600, dtype=np.float32)


class FakeRecorder:
    """A microphone that never fails, records silence and counts its calls.

    ``start_error`` puts a message into ``error`` the way a driver that cannot
    open the device does, and ``audio`` is what :meth:`stop` hands back. The
    real recorder's audio contract is not re-implemented here - only that the
    pipeline treats it as "float32 samples or empty, never an exception".
    """

    def __init__(self, audio=None, start_error=None, gate=None):
        self.audio = _EMPTY_AUDIO if audio is None else audio
        self.start_error = start_error
        self.gate = gate          # start() waits on this, if given
        self.error = None
        self.started = 0
        self.stopped = 0

    def start(self):
        self.started += 1
        if self.gate is not None:
            self.gate.wait(10)
        self.error = self.start_error

    def stop(self):
        self.stopped += 1
        return self.audio


class FakeTranscriber:
    """The recognizer's side of the pipeline, without a model.

    ``text`` is what recognition returns and ``fail_with`` is the message the
    real :class:`transcriber.Transcriber` leaves in ``error`` - assigned inside
    transcribe, the way the real one does. ``gate`` reproduces the call that
    never comes back, ``load_error`` a model that will not load at all, and
    ``fallback_note`` the informational "the GPU was not usable" message a
    *successful* CPU load leaves behind.
    """

    def __init__(self, text="Hallo Welt.", fail_with=None, gate=None,
                 is_ready=True, load_error=None, fallback_note=None):
        self.text = text
        self.fail_with = fail_with
        self.gate = gate
        self.is_ready = is_ready
        self.load_error = load_error
        self.fallback_note = fallback_note
        self.error = load_error
        self.active_device = "cpu" if fallback_note else "cuda"
        self.initial_prompt = ""
        self.calls = []
        self.seen_error = []

    def load(self):
        self.is_ready = self.load_error is None
        self.error = self.load_error or self.fallback_note
        return None

    def transcribe(self, audio):
        self.calls.append(audio)
        self.seen_error.append(self.error)
        if self.gate is not None:
            self.gate.wait(10)
        self.error = self.fail_with
        return self.text


class RecordingTray(Tray):
    """The real tray state machine, with the notifications kept.

    ``set_state`` and ``state`` come from :class:`tray.Tray`, so the pipeline is
    exercised against the state the user actually sees; only ``notify`` is
    intercepted, because a test has no notification area to show it in.
    """

    def __init__(self, **actions):
        super().__init__(
            on_quit=actions.get("on_quit", lambda: None),
            on_reload=actions.get("on_reload", lambda: None),
            on_select_mic=actions.get("on_select_mic", lambda: None),
            on_open_config=actions.get("on_open_config", lambda: None),
        )
        self.messages = []

    def notify(self, message):
        self.messages.append(message)


class RunningTray(RecordingTray):
    """A tray that shows itself and hands the main thread straight back."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.thread = None
        self.stopped = False

    def run(self):
        self.thread = threading.get_ident()

    def stop(self):
        self.stopped = True


class RecordingHook:
    """A mouse hook that records where it ran instead of installing one."""

    def __init__(self, button, on_press, on_release, max_seconds, failure=None):
        self.button = button
        self.on_press = on_press
        self.on_release = on_release
        self.max_seconds = max_seconds
        self.failure = failure
        self.thread = None
        self.ready_called = False
        self.finished = threading.Event()
        self.running = threading.Event()

    def run(self, on_ready=None):
        self.running.set()
        self.thread = threading.get_ident()
        try:
            if self.failure is not None:
                raise RuntimeError(self.failure)
            if on_ready is not None:
                on_ready()
                self.ready_called = True
            self.finished.wait(10)
        finally:
            self.running.clear()

    def stop(self):
        self.finished.set()


def run_now(job):
    """A ``submit`` that runs the job in the calling thread - what tests want."""
    job()


def wait_for(predicate, timeout=10.0):
    """Block until predicate() holds; fail the test rather than hang on it."""
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    raise AssertionError("the condition was not met within the timeout")


def write_wav(path, *, seconds=0.1, rate=16000, channels=1):
    """A silent PCM WAV of the shape the recorder itself produces."""
    samples = np.zeros(int(rate * seconds * channels), dtype=np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(samples.tobytes())
    return path


# --- fixtures -----------------------------------------------------------------

@pytest.fixture(autouse=True)
def tones(monkeypatch):
    """Capture the beeps instead of making noise in the test runner."""
    played = []
    monkeypatch.setattr(
        dictate, "_beep",
        lambda frequency, duration: played.append((frequency, duration)))
    return played


@pytest.fixture
def typed(monkeypatch):
    """Capture the text that would have been typed into the focused window."""
    calls = []
    monkeypatch.setattr(
        dictate, "insert_text",
        lambda text, mode="sendinput": calls.append((text, mode)))
    return calls


@pytest.fixture
def app(monkeypatch):
    """Replace every seam the entry point builds through, and keep what it made.

    One fixture instead of six monkeypatch calls per test: the tray, the hook,
    the microphone list and the recognizer are the only objects a real run
    would have created, and a test that cares about one of them reads it off
    the namespace this returns.
    """
    env = SimpleNamespace(
        transcriber=FakeTranscriber(), devices=list(_DEVICES), trays=[],
        hooks=[], opened=[], typed=[], probe_errors={}, prompt=None, boxes=[],
        recorders=[],
    )

    def build_transcriber(cfg, prompt):
        env.prompt = prompt
        # The real builder hands the vocabulary on to the model.
        env.transcriber.initial_prompt = prompt
        return env.transcriber

    def build_recorder(device):
        # Never the real microphone: an automated run has no business opening
        # the user's input device.
        env.recorders.append(FakeRecorder(audio=_TONE))
        env.recorders[-1].device = device
        return env.recorders[-1]

    def build_tray(**kwargs):
        env.trays.append(RunningTray(**kwargs))
        return env.trays[-1]

    def build_hook(*args, **kwargs):
        env.hooks.append(RecordingHook(*args, failure=kwargs.get("failure")))
        return env.hooks[-1]

    monkeypatch.setattr(dictate, "build_transcriber", build_transcriber)
    monkeypatch.setattr(dictate, "build_recorder", build_recorder)
    monkeypatch.setattr(dictate, "build_tray", build_tray)
    monkeypatch.setattr(dictate, "build_hook", build_hook)
    monkeypatch.setattr(dictate, "query_devices", lambda: env.devices)
    monkeypatch.setattr(
        dictate, "probe_input_device", lambda index: env.probe_errors.get(index))
    monkeypatch.setattr(dictate, "open_path", env.opened.append)
    # A real message box is modal and would wait for a human.
    monkeypatch.setattr(
        dictate, "_message_box",
        lambda title, message: env.boxes.append((title, message)))
    monkeypatch.setattr(
        dictate, "insert_text",
        lambda text, mode="sendinput": env.typed.append((text, mode)))
    return env


def build_pipeline(tray=None, transcriber=None, recorder=None, cfg=None, **kwargs):
    """A Pipeline whose jobs run in the calling thread."""
    kwargs.setdefault("submit", run_now)
    return dictate.Pipeline(
        cfg if cfg is not None else Config(),
        transcriber if transcriber is not None else FakeTranscriber(),
        recorder if recorder is not None else FakeRecorder(),
        tray if tray is not None else RecordingTray(),
        **kwargs,
    )


# --- press and release: the ordinary path -------------------------------------

def test_a_press_opens_the_microphone_and_shows_recording():
    recorder, tray = FakeRecorder(), RecordingTray()
    pipeline = build_pipeline(tray=tray, recorder=recorder)

    pipeline.on_press()

    assert recorder.started == 1
    assert tray.state == "recording"


def test_a_release_types_the_text_and_returns_to_ready(typed):
    tray = RecordingTray()
    pipeline = build_pipeline(tray=tray, recorder=FakeRecorder(audio=_TONE))

    pipeline.on_press()
    pipeline.on_release()

    assert typed == [("Hallo Welt.", "sendinput")]
    assert tray.state == "ready"


def test_the_recorders_audio_is_handed_to_the_recognizer_unchanged():
    transcriber = FakeTranscriber()
    pipeline = build_pipeline(recorder=FakeRecorder(audio=_TONE),
                              transcriber=transcriber)

    pipeline.on_press()
    pipeline.on_release()

    assert transcriber.calls[0] is _TONE


def test_the_configured_insert_mode_is_used(typed):
    pipeline = build_pipeline(cfg=Config(insert_mode="clipboard"),
                              recorder=FakeRecorder(audio=_TONE))

    pipeline.on_press()
    pipeline.on_release()

    assert typed == [("Hallo Welt.", "clipboard")]


def test_the_dictionary_rules_are_applied_before_the_text_is_typed(typed):
    # What the recognizer hears and what the user gets are two different
    # strings; the replacement table is the bridge between them.
    pipeline = build_pipeline(
        transcriber=FakeTranscriber(text="Radio Dock ist gut."),
        recorder=FakeRecorder(audio=_TONE),
        replacements=[("power house", "Powerhouse")],
    )

    pipeline.on_press()
    pipeline.on_release()

    assert typed == [("Powerhouse ist gut.", "sendinput")]


def test_reloaded_rules_are_used_by_the_next_utterance(typed):
    pipeline = build_pipeline(recorder=FakeRecorder(audio=_TONE))
    pipeline.on_press()
    pipeline.on_release()

    pipeline.set_replacements([("hallo", "Guten Tag")])
    pipeline.on_press()
    pipeline.on_release()

    assert [text for text, _mode in typed] == ["Hallo Welt.", "Guten Tag Welt."]


def test_a_second_press_while_recording_starts_nothing_new():
    recorder = FakeRecorder()
    pipeline = build_pipeline(recorder=recorder)

    pipeline.on_press()
    pipeline.on_press()

    assert recorder.started == 1


def test_a_press_while_transcribing_is_refused():
    recorder, tray = FakeRecorder(audio=_TONE), RecordingTray()
    gate = threading.Event()
    pipeline = build_pipeline(tray=tray, recorder=recorder,
                              transcriber=FakeTranscriber(gate=gate),
                              transcribe_timeout=30, submit=None)
    pipeline.on_press()
    assert wait_for(lambda: recorder.started == 1)
    pipeline.on_release()          # the worker thread is inside the recognizer
    assert wait_for(lambda: tray.state == "transcribing")

    pipeline.on_press()            # a press that arrives mid-recognition

    assert recorder.started == 1
    assert tray.state == "transcribing"
    gate.set()


def test_a_release_without_an_open_session_does_nothing():
    # The button and the watchdog can both end a session; only one of them may
    # stop the recorder, and a stray release must not transcribe silence.
    recorder, tray = FakeRecorder(audio=_TONE), RecordingTray()
    pipeline = build_pipeline(tray=tray, recorder=recorder)

    pipeline.on_release()

    assert recorder.stopped == 0
    assert tray.state == "ready"


def test_exactly_one_of_many_concurrent_releases_stops_the_recorder():
    # on_release arrives on the hook thread and on the watchdog thread, and a
    # session may only be closed once.
    recorder, tray = FakeRecorder(audio=_TONE), RecordingTray()
    pipeline = build_pipeline(tray=tray, recorder=recorder)
    pipeline.on_press()

    barrier = threading.Barrier(8)
    threads = [
        threading.Thread(target=lambda: (barrier.wait(10), pipeline.on_release()))
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)

    assert recorder.stopped == 1


def test_a_release_from_another_thread_finishes_the_session(typed):
    tray = RecordingTray()
    pipeline = build_pipeline(tray=tray, recorder=FakeRecorder(audio=_TONE))
    pipeline.on_press()

    thread = threading.Thread(target=pipeline.on_release)
    thread.start()
    thread.join(10)

    assert tray.state == "ready"
    assert typed == [("Hallo Welt.", "sendinput")]


# --- the press must not hold the mouse hook -----------------------------------

def test_the_press_returns_before_the_microphone_is_open():
    # Windows gives a low-level mouse hook callback a few hundred milliseconds
    # and silently drops the hook when it overruns, so on_press may only queue
    # the work. This recorder takes ten seconds to open, and the one second
    # budget below is the whole test: a synchronous on_press spends ten of them.
    gate = threading.Event()
    recorder = FakeRecorder(gate=gate)
    pipeline = build_pipeline(recorder=recorder, submit=None)   # the real worker
    try:
        started = time.perf_counter()
        pipeline.on_press()
        elapsed = time.perf_counter() - started

        assert elapsed < 1.0, f"on_press blocked for {elapsed:.2f}s"
        assert wait_for(lambda: recorder.started == 1), "the recorder never started"
    finally:
        gate.set()


def test_the_background_worker_runs_the_release_to_the_end():
    tray = RecordingTray()
    pipeline = build_pipeline(tray=tray, recorder=FakeRecorder(audio=_TONE))
    pipeline.on_press()
    pipeline.on_release()

    assert wait_for(lambda: tray.state == "ready" or tray.state == "error")
    assert tray.state == "ready"


# --- failures the user must be told about -------------------------------------

def test_a_failed_recognition_is_shown_and_nothing_is_typed(typed):
    tray = RecordingTray()
    pipeline = build_pipeline(
        tray=tray,
        recorder=FakeRecorder(audio=_TONE),
        transcriber=FakeTranscriber(
            text="", fail_with="The recording could not be transcribed: "
                               "Library cublas64_12.dll is not found"),
    )

    pipeline.on_press()
    pipeline.on_release()

    assert typed == []
    assert tray.state == "error"
    assert any("cublas64_12.dll" in message for message in tray.messages)


def test_a_stale_model_message_does_not_look_like_a_failed_utterance(typed):
    # Transcriber.error also carries the informational "the GPU was not usable,
    # so dictate fell back to the CPU" note from load(). Recognising the next
    # sentence must not turn that note into an error the user sees.
    transcriber = FakeTranscriber(text="Guten Tag.")
    transcriber.error = "The GPU was not usable, so dictate fell back to the CPU: ..."
    tray = RecordingTray()
    pipeline = build_pipeline(tray=tray, recorder=FakeRecorder(audio=_TONE),
                              transcriber=transcriber)

    pipeline.on_press()
    pipeline.on_release()

    assert typed == [("Guten Tag.", "sendinput")]
    assert tray.state == "ready"
    assert tray.messages == []


def test_the_recognizer_is_asked_with_a_clean_error():
    transcriber = FakeTranscriber(text="Hallo.")
    transcriber.error = "an old message from load()"
    pipeline = build_pipeline(recorder=FakeRecorder(audio=_TONE),
                              transcriber=transcriber)

    pipeline.on_press()
    pipeline.on_release()

    assert transcriber.seen_error == [None]


def test_a_microphone_that_will_not_open_is_reported(typed):
    tray = RecordingTray()
    pipeline = build_pipeline(
        tray=tray,
        recorder=FakeRecorder(start_error="The microphone could not be opened: nope"),
    )

    pipeline.on_press()

    assert tray.state == "error"
    assert any("microphone" in message.lower() for message in tray.messages)

    pipeline.on_release()
    assert typed == []


def test_a_failed_insert_is_reported_and_the_tool_keeps_running(monkeypatch):
    # inserter.insert_text raises RuntimeError when Windows accepted only part
    # of the SendInput batch - typically a foreground window blocking us. The
    # run must not die with a traceback.
    def blocked(text, mode="sendinput"):
        raise RuntimeError("SendInput queued 12 of 24 input events")

    monkeypatch.setattr(dictate, "insert_text", blocked)
    tray = RecordingTray()
    pipeline = build_pipeline(tray=tray, recorder=FakeRecorder(audio=_TONE))

    pipeline.on_press()
    pipeline.on_release()

    assert tray.state == "error"
    # The message has to name the typing, not just repeat the exception: the
    # generic safety net would otherwise produce an indistinguishable one.
    assert any("could not be typed into the window" in message
               and "12 of 24" in message for message in tray.messages)


def test_an_error_state_still_accepts_the_next_press():
    # The user has to be able to retry without restarting the tool.
    recorder, tray = FakeRecorder(audio=_TONE), RecordingTray()
    transcriber = FakeTranscriber(text="", fail_with="first try failed")
    pipeline = build_pipeline(tray=tray, recorder=recorder, transcriber=transcriber)
    pipeline.on_press()
    pipeline.on_release()
    assert tray.state == "error"

    transcriber.fail_with = None
    pipeline.on_press()
    pipeline.on_release()

    assert recorder.started == 2
    assert tray.state == "ready"


def test_a_recognition_that_never_returns_is_abandoned(typed):
    # A CUDA library missing at decode time made the first call return nothing
    # and the next one never return at all. The user must not be left holding a
    # button whose tool is gone.
    gate = threading.Event()
    tray = RecordingTray()
    pipeline = build_pipeline(
        tray=tray,
        recorder=FakeRecorder(audio=_TONE),
        transcriber=FakeTranscriber(gate=gate),
        transcribe_timeout=0.2,
    )
    try:
        started = time.perf_counter()
        pipeline.on_press()
        pipeline.on_release()
        elapsed = time.perf_counter() - started

        assert elapsed < 5.0, f"the release waited {elapsed:.2f}s on the recognizer"
        assert tray.state == "error"
        assert typed == []
        assert tray.messages, "an abandoned recognition has to say so"
    finally:
        gate.set()


def test_no_second_press_while_a_stuck_recognition_is_still_running():
    # One recognizer, one caller. As long as the abandoned call has not
    # returned, the model is in use and a second call would be undefined.
    gate = threading.Event()
    recorder, tray = FakeRecorder(audio=_TONE), RecordingTray()
    pipeline = build_pipeline(
        tray=tray, recorder=recorder,
        transcriber=FakeTranscriber(gate=gate), transcribe_timeout=0.2,
    )
    try:
        pipeline.on_press()
        pipeline.on_release()
        assert tray.state == "error"

        pipeline.on_press()

        assert recorder.started == 1
    finally:
        gate.set()


def test_pressing_works_again_once_the_stuck_recognition_returns():
    gate = threading.Event()
    recorder, tray = FakeRecorder(audio=_TONE), RecordingTray()
    pipeline = build_pipeline(
        tray=tray, recorder=recorder,
        transcriber=FakeTranscriber(gate=gate), transcribe_timeout=0.2,
    )
    pipeline.on_press()
    pipeline.on_release()
    assert tray.state == "error"

    gate.set()

    assert wait_for(lambda: pipeline.accepts_press), "the tool stayed wedged"
    pipeline.on_press()
    assert recorder.started == 2


def test_the_pipeline_reports_whether_it_would_accept_a_press():
    recorder, tray = FakeRecorder(audio=_TONE), RecordingTray()
    pipeline = build_pipeline(tray=tray, recorder=recorder)

    assert pipeline.accepts_press is True
    pipeline.on_press()
    assert pipeline.accepts_press is False
    pipeline.on_release()
    assert pipeline.accepts_press is True


# --- nothing to say, nothing to type ------------------------------------------

def test_an_empty_recording_transcribes_nothing(typed):
    transcriber, tray = FakeTranscriber(), RecordingTray()
    pipeline = build_pipeline(tray=tray, recorder=FakeRecorder(),
                              transcriber=transcriber)

    pipeline.on_press()
    pipeline.on_release()

    assert transcriber.calls == []
    assert typed == []
    assert tray.state == "ready"


def test_silence_does_not_type_and_does_not_complain(typed):
    # VAD legitimately returns nothing for a click too short to be speech, and
    # that is not an error.
    tray = RecordingTray()
    pipeline = build_pipeline(tray=tray, recorder=FakeRecorder(audio=_TONE),
                              transcriber=FakeTranscriber(text=""))

    pipeline.on_press()
    pipeline.on_release()

    assert typed == []
    assert tray.state == "ready"
    assert tray.messages == []


def test_the_text_is_typed_exactly_as_transcribed(typed):
    # No trailing newline, no Enter: the tool types the words and leaves
    # sending them to the user.
    pipeline = build_pipeline(recorder=FakeRecorder(audio=_TONE),
                              transcriber=FakeTranscriber(text="Ein Satz."))

    pipeline.on_press()
    pipeline.on_release()

    assert typed == [("Ein Satz.", "sendinput")]


def test_the_entry_point_cannot_type_a_key_itself():
    source = Path(dictate.__file__).read_text(encoding="utf-8")
    for forbidden in ("SendInput", "KEYEVENTF", "VK_RETURN", "VK_ENTER",
                      "KEYEVENTF_KEYUP", "keybd_event"):
        assert forbidden not in source, forbidden


def test_print_mode_writes_to_stdout_instead_of_the_window(typed, capsys):
    pipeline = build_pipeline(recorder=FakeRecorder(audio=_TONE), print_instead=True)

    pipeline.on_press()
    pipeline.on_release()

    assert typed == []
    assert capsys.readouterr().out.strip() == "Hallo Welt."


# --- the beeps ---------------------------------------------------------------

def test_the_recording_start_beeps(tones):
    build_pipeline().on_press()
    assert len(tones) == 1


def test_an_error_beeps_in_a_different_tone(tones):
    build_pipeline(recorder=FakeRecorder(start_error="no microphone")).on_press()
    assert len(tones) == 2
    assert tones[0] != tones[1]


def test_nothing_beeps_when_the_user_turned_it_off(tones):
    build_pipeline(cfg=Config(beep=False),
                   recorder=FakeRecorder(start_error="no microphone")).on_press()
    assert tones == []


def test_a_missing_winsound_is_not_fatal(monkeypatch):
    # Only the beep is missing, never the dictation. A None entry in sys.modules
    # makes the import raise exactly like an absent module would.
    monkeypatch.setitem(sys.modules, "winsound", None)
    pipeline = build_pipeline()

    pipeline.on_press()

    assert pipeline.state == "recording"


# --- the microphone selection -------------------------------------------------

def test_an_empty_mic_setting_uses_the_system_default():
    index, warning = dictate.resolve_input_device("", _DEVICES, lambda i: None)
    assert index is None
    assert warning is None


def test_a_name_that_matches_is_used_without_a_warning():
    index, warning = dictate.resolve_input_device(_MIC_NAME, _DEVICES, lambda i: None)
    assert index == _MIC_MME
    assert warning is None


def test_a_device_that_refuses_16khz_is_passed_over_for_one_that_accepts_it():
    # The same microphone is exposed by two host APIs, and a WASAPI endpoint
    # rejects the 16 kHz dictate records at. Trying every candidate is what
    # keeps this from recording nothing at all.
    tried = []

    def probe(candidate):
        tried.append(candidate)
        return "Invalid sample rate" if candidate == _MIC_MME else None

    index, warning = dictate.resolve_input_device(_MIC_NAME, _DEVICES, probe)

    assert tried == [_MIC_MME, _MIC_WASAPI]
    assert index == _MIC_WASAPI
    assert warning is None


def test_a_microphone_name_that_matches_nothing_is_reported():
    index, warning = dictate.resolve_input_device("Headset G2", _DEVICES,
                                                  lambda i: None)
    assert index is None
    assert "Headset G2" in warning


def test_an_out_of_range_microphone_index_is_reported():
    # "99999" is the typo that otherwise records from the system default
    # microphone with no word about it.
    index, warning = dictate.resolve_input_device("99999", _DEVICES, lambda i: None)
    assert index is None
    assert "99999" in warning


def test_a_microphone_that_cannot_be_opened_at_all_is_reported_with_the_reason():
    index, warning = dictate.resolve_input_device(
        _MIC_NAME, _DEVICES, lambda candidate: f"Invalid sample rate ({candidate})")
    assert index is None
    assert "Invalid sample rate" in warning
    assert "default" in warning.lower()


def test_the_first_working_candidate_is_the_one_pick_device_would_have_chosen():
    # dictate adds the probing; it must not quietly disagree with the module
    # that does the plain matching.
    from recorder import pick_device

    assert dictate.resolve_input_device(_MIC_NAME, _DEVICES, lambda i: None)[0] == \
        pick_device(_DEVICES, _MIC_NAME)
    assert dictate.resolve_input_device("1", _DEVICES, lambda i: None)[0] == \
        pick_device(_DEVICES, "1")


def test_an_index_that_selects_a_device_is_probed_too():
    index, warning = dictate.resolve_input_device("2", _DEVICES, lambda i: None)
    assert index == _MIC_WASAPI
    assert warning is None


def test_an_output_only_device_is_never_chosen():
    index, warning = dictate.resolve_input_device("Speakers", _DEVICES,
                                                  lambda i: None)
    assert index is None
    assert "Speakers" in warning


def test_a_probe_of_a_device_portaudio_does_not_know_reports_the_reason():
    # The seam talks to the real PortAudio, so this exercises the failure path
    # without needing a microphone.
    assert isinstance(dictate.probe_input_device(99999), str)


def test_list_devices_prints_the_devices(capsys, monkeypatch):
    monkeypatch.setattr(dictate, "query_devices", lambda: list(_DEVICES))
    monkeypatch.setattr(dictate, "default_input_device", lambda: _MIC_MME)
    monkeypatch.setattr(dictate, "build_tray",
                        lambda **kwargs: pytest.fail("built a tray"))

    assert dictate.main(["--list-devices"]) == _EXIT_OK

    out = capsys.readouterr().out
    assert _MIC_NAME in out
    assert "MME" in out and "WASAPI" in out
    assert "Microphone" in out


# --- reading a WAV file -------------------------------------------------------

def test_read_wav_returns_mono_float32_at_16khz(tmp_path):
    audio = dictate.read_wav(write_wav(tmp_path / "a.wav", seconds=0.5))
    assert audio.dtype == np.dtype(np.float32)
    assert audio.ndim == 1
    assert audio.shape == (8000,)


def test_read_wav_downmixes_a_stereo_file(tmp_path):
    audio = dictate.read_wav(write_wav(tmp_path / "a.wav", seconds=0.5, channels=2))
    assert audio.shape == (8000,)


def test_read_wav_refuses_another_sample_rate(tmp_path):
    path = write_wav(tmp_path / "a.wav", seconds=0.1, rate=44100)
    with pytest.raises(ValueError, match="44100"):
        dictate.read_wav(path)


def test_the_file_mode_prints_the_text_and_never_types(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "dictate.config.json"
    (tmp_path / "replacements.txt").write_text("power house => Powerhouse\n",
                                               encoding="utf-8")
    monkeypatch.setattr(
        dictate, "build_transcriber",
        lambda cfg, prompt: FakeTranscriber(text="Radio Dock ist gut."))
    monkeypatch.setattr(dictate, "insert_text",
                        lambda text, mode="sendinput": pytest.fail("typed the text"))

    result = dictate.main(["--file", str(write_wav(tmp_path / "a.wav")), "--print",
                           "--config", str(config_path)])

    assert result == _EXIT_OK
    assert capsys.readouterr().out.strip() == "Powerhouse ist gut."


def test_the_file_mode_needs_no_microphone_and_no_tray(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(dictate, "build_transcriber", lambda cfg, prompt: FakeTranscriber())
    monkeypatch.setattr(dictate, "query_devices",
                        lambda: pytest.fail("asked for an audio device"))
    monkeypatch.setattr(dictate, "build_tray",
                        lambda **kwargs: pytest.fail("built a tray"))

    result = dictate.main(["--file", str(write_wav(tmp_path / "a.wav"))])

    assert result == _EXIT_OK
    assert capsys.readouterr().out.strip() == "Hallo Welt."


def test_a_missing_wav_file_is_reported(tmp_path, capsys):
    result = dictate.main(["--file", str(tmp_path / "nope.wav")])
    assert result != _EXIT_OK
    assert "nope.wav" in capsys.readouterr().err


def test_a_failed_recognition_in_the_file_mode_is_reported(tmp_path, monkeypatch,
                                                           capsys):
    monkeypatch.setattr(
        dictate, "build_transcriber",
        lambda cfg, prompt: FakeTranscriber(
            text="", fail_with="The recording could not be transcribed: boom"))

    result = dictate.main(["--file", str(write_wav(tmp_path / "a.wav"))])

    assert result != _EXIT_OK
    assert "boom" in capsys.readouterr().err


def test_the_file_mode_uses_the_configured_model(tmp_path, monkeypatch, capsys):
    built = {}

    def build(cfg, prompt):
        built["cfg"] = cfg
        return FakeTranscriber()

    monkeypatch.setattr(dictate, "build_transcriber", build)

    assert dictate.main(["--file", str(write_wav(tmp_path / "a.wav"))]) == _EXIT_OK
    assert built["cfg"].model == "large-v3-turbo"
    assert built["cfg"].language == "de"


# --- the dictionary -----------------------------------------------------------

def test_the_dictionary_is_read_next_to_the_configuration_file(tmp_path):
    (tmp_path / "vocabulary.txt").write_text("Powerhouse\nExample\n",
                                             encoding="utf-8")
    (tmp_path / "replacements.txt").write_text("power house => Powerhouse\n",
                                               encoding="utf-8")

    dictionary = dictate.load_dictionary(tmp_path / "dictate.config.json")

    assert dictionary.prompt == "Powerhouse, Example"
    assert list(dictionary.rules) == [("power house", "Powerhouse")]
    assert list(dictionary.problems) == []


def test_a_missing_dictionary_is_not_fatal(tmp_path):
    # load_vocabulary/load_replacements raise on a missing file; dictation must
    # not die because somebody deleted the vocabulary.
    dictionary = dictate.load_dictionary(tmp_path / "dictate.config.json")
    assert list(dictionary.rules) == []
    assert dictionary.prompt == ""
    assert dictionary.problems


def test_a_missing_vocabulary_leaves_the_replacement_rules_alone(tmp_path):
    (tmp_path / "replacements.txt").write_text("power house => Powerhouse\n",
                                               encoding="utf-8")
    dictionary = dictate.load_dictionary(tmp_path / "dictate.config.json")
    assert list(dictionary.rules) == [("power house", "Powerhouse")]


def test_the_vocabulary_becomes_the_recognizers_prompt(tmp_path, app):
    (tmp_path / "vocabulary.txt").write_text("Powerhouse\nExample\n",
                                             encoding="utf-8")

    assert dictate.main(["--file", str(write_wav(tmp_path / "a.wav")),
                         "--config", str(tmp_path / "dictate.config.json")]) == _EXIT_OK
    assert app.prompt == "Powerhouse, Example"


def test_the_prompt_reaches_the_recognizer(tmp_path, app):
    (tmp_path / "vocabulary.txt").write_text("Powerhouse\n", encoding="utf-8")

    assert dictate.main(["--file", str(write_wav(tmp_path / "a.wav")),
                         "--config", str(tmp_path / "dictate.config.json")]) == _EXIT_OK
    assert app.transcriber.initial_prompt == "Powerhouse"


# --- threads, tray and hook ---------------------------------------------------

def test_the_tray_runs_on_the_main_thread_and_the_hook_on_its_own(app):
    # pystray wants its run() on the main thread; the hook installs a global
    # low-level mouse hook and pumps a message loop of its own. They cannot
    # share a thread.
    assert dictate.main([]) == _EXIT_OK

    tray = app.trays[0]
    assert tray.thread == threading.get_ident(), "pystray was not on the main thread"
    assert app.hooks[0].thread is not None
    assert app.hooks[0].thread != threading.get_ident()


def test_the_hook_is_built_from_the_configuration(app, tmp_path):
    config_path = tmp_path / "dictate.config.json"
    config_path.write_text(
        '{"mouseButton": "XButton2", "maxRecordSeconds": 30, "micDevice": "1"}',
        encoding="utf-8")

    assert dictate.main(["--config", str(config_path)]) == _EXIT_OK

    assert app.hooks[0].button == "XButton2"
    assert app.hooks[0].max_seconds == 30


def test_a_hook_that_cannot_be_installed_is_reported_to_the_user(app, monkeypatch):
    # hook.MouseHook.run raises RuntimeError rather than printing anything: a
    # dictation tool whose button does nothing must not start silently.
    def build(*args, **kwargs):
        return RecordingHook(
            *args,
            failure="The XButton1 push-to-talk hook could not be installed "
                    "(Windows error 5)")

    monkeypatch.setattr(dictate, "build_hook", build)

    assert dictate.main([]) == _EXIT_OK

    assert app.trays[0].state == "error"
    assert any("could not be installed" in message
               for message in app.trays[0].messages)


def test_the_hook_is_started_with_a_ready_callback(app):
    assert dictate.main([]) == _EXIT_OK
    assert app.hooks[0].ready_called is True


def test_on_ready_turns_the_dot_green():
    tray = RunningTray()
    tray.set_state("error")
    hook = RecordingHook("XButton1", lambda: None, lambda: None, 120)

    thread = dictate.run_hook(hook, tray, lambda: tray.set_state("ready"))
    thread.start()
    hook.finished.wait(10)
    hook.stop()
    thread.join(10)

    assert tray.state == "ready"


def test_run_hook_reports_an_install_failure_and_keeps_the_thread_quiet(capsys):
    tray = RunningTray()
    hook = RecordingHook("XButton1", lambda: None, lambda: None, 120,
                         failure="The XButton1 push-to-talk hook could not be "
                                 "installed (Windows error 5)")

    thread = dictate.run_hook(hook, tray, lambda: None)
    thread.start()
    thread.join(10)

    assert tray.state == "error"
    assert any("Windows error 5" in message for message in tray.messages)
    assert "Traceback" not in capsys.readouterr().err


def test_without_a_tray_the_hook_is_the_main_loop(app):
    assert dictate.main(["--no-tray"]) == _EXIT_OK
    assert app.hooks[0].thread == threading.get_ident()
    assert app.trays == []


def test_the_no_tray_reporter_keeps_the_state_and_prints_the_problems(capsys):
    reporter = dictate.StderrReporter()
    reporter.set_state("error")
    reporter.notify("something went wrong")

    assert reporter.state == "error"
    assert "something went wrong" in capsys.readouterr().err


def test_a_microphone_warning_reaches_the_user(app, tmp_path):
    # A named device that will not open must not be replaced by the system
    # default in silence: this is the message that says so.
    config_path = tmp_path / "dictate.config.json"
    config_path.write_text(f'{{"micDevice": "{_MIC_NAME}"}}', encoding="utf-8")
    app.probe_errors[_MIC_MME] = "Invalid sample rate"
    app.probe_errors[_MIC_WASAPI] = "Invalid sample rate"

    assert dictate.main(["--config", str(config_path)]) == _EXIT_OK

    assert any("Invalid sample rate" in message for message in app.trays[0].messages)


def test_the_microphone_that_is_recorded_from_is_the_resolved_one(app, tmp_path):
    config_path = tmp_path / "dictate.config.json"
    config_path.write_text(f'{{"micDevice": "{_MIC_NAME}"}}', encoding="utf-8")

    assert dictate.main(["--config", str(config_path)]) == _EXIT_OK

    assert app.recorders[0].device == _MIC_MME


def test_a_device_that_will_not_open_at_16khz_is_not_the_one_recorded_from(
    app, tmp_path
):
    # The WASAPI endpoint comes first here and refuses 16 kHz, so the MME one
    # is what actually gets the microphone.
    config_path = tmp_path / "dictate.config.json"
    config_path.write_text(f'{{"micDevice": "{_MIC_NAME}"}}', encoding="utf-8")
    app.probe_errors[_MIC_MME] = "Invalid sample rate"

    assert dictate.main(["--config", str(config_path)]) == _EXIT_OK

    assert app.recorders[0].device == _MIC_WASAPI
    assert [m for m in app.trays[0].messages if "sample rate" in m] == []


def test_the_quit_menu_entry_stops_the_hook_and_the_tray(app):
    assert dictate.main([]) == _EXIT_OK

    # pystray hands a menu action the icon and the menu item; both are dropped.
    quit_action = dict(app.trays[0].menu_entries())["Beenden"]
    quit_action("the icon", "the item")

    assert app.hooks[0].finished.is_set()
    assert app.trays[0].stopped is True


def test_the_reload_menu_entry_reads_the_dictionary_again(app, tmp_path):
    config_path = tmp_path / "dictate.config.json"
    (tmp_path / "replacements.txt").write_text("hallo => Guten Tag\n", encoding="utf-8")
    (tmp_path / "vocabulary.txt").write_text("Powerhouse\n", encoding="utf-8")

    assert dictate.main(["--config", str(config_path)]) == _EXIT_OK
    assert app.transcriber.initial_prompt == "Powerhouse"

    (tmp_path / "replacements.txt").write_text("welt => World\n", encoding="utf-8")
    (tmp_path / "vocabulary.txt").write_text("OpenCode\n", encoding="utf-8")
    reload_action = dict(app.trays[0].menu_entries())["Wörterbuch neu laden"]
    reload_action()

    assert app.transcriber.initial_prompt == "OpenCode"

    app.hooks[0].on_press()
    app.hooks[0].on_release()

    assert wait_for(lambda: bool(app.typed)), "nothing was typed at all"
    assert [text for text, _mode in app.typed] == ["Hallo World."]


def test_the_config_menu_entries_open_the_configuration(app, tmp_path):
    config_path = tmp_path / "dictate.config.json"

    assert dictate.main(["--config", str(config_path)]) == _EXIT_OK

    entries = dict(app.trays[0].menu_entries())
    entries["Config öffnen"]()
    entries["Mikrofon wählen"]()

    assert app.opened == [config_path, config_path]


def test_the_microphone_entry_shows_the_device_list_to_copy_from(app, tmp_path):
    # There is no console to pick a microphone on, so the list is shown and the
    # configuration is opened next to it.
    assert dictate.main(["--config", str(tmp_path / "dictate.config.json")]) == _EXIT_OK

    dict(app.trays[0].menu_entries())["Mikrofon wählen"]()

    assert app.boxes, "the device list was never shown"
    assert _MIC_NAME in app.boxes[-1][1]
    assert str(_MIC_MME) in app.boxes[-1][1]


# --- the configuration on disk ------------------------------------------------

def test_the_default_configuration_is_the_one_next_to_the_tool():
    assert dictate.DEFAULT_CONFIG_PATH == \
        Path(dictate.__file__).with_name("dictate.config.json")


def test_the_documented_defaults_are_written_to_a_new_configuration(tmp_path):
    config_path = tmp_path / "dictate.config.json"
    cfg = dictate.ensure_config(config_path)

    assert cfg == config.DEFAULT_CONFIG
    assert (cfg.mouse_button, cfg.mic_device, cfg.model) == \
        ("XButton1", "", "large-v3-turbo")
    assert (cfg.language, cfg.device, cfg.insert_mode, cfg.beep) == \
        ("de", "auto", "sendinput", True)
    assert config.load_config(config_path) == cfg


def test_a_broken_configuration_is_reported_not_raised(tmp_path, capsys):
    config_path = tmp_path / "dictate.config.json"
    config_path.write_text('{"maxRecordSeconds": 3}', encoding="utf-8")

    result = dictate.main(["--config", str(config_path)])

    assert result != _EXIT_OK
    assert "maxRecordSeconds" in capsys.readouterr().err


def test_a_model_that_cannot_be_loaded_stops_the_tool(app, capsys):
    app.transcriber = FakeTranscriber(
        is_ready=False, load_error="The speech model could not be loaded: no driver")

    result = dictate.main([])

    assert result != _EXIT_OK
    assert "no driver" in capsys.readouterr().err


def test_the_cpu_fallback_is_announced_once(app, capsys):
    app.transcriber = FakeTranscriber(
        fallback_note="The GPU was not usable, so dictate fell back to the CPU: dll")

    assert dictate.main([]) == _EXIT_OK

    assert any("CPU" in message for message in app.trays[0].messages)


def test_a_loaded_model_on_the_gpu_says_nothing(app):
    assert dictate.main([]) == _EXIT_OK
    assert app.trays[0].messages == []


# --- the two mouse button tables ----------------------------------------------

def test_the_hook_and_the_configuration_agree_on_the_button_names():
    assert hook_module.MOUSE_BUTTONS == config.MOUSE_BUTTONS


def test_every_button_name_the_configuration_accepts_hooks():
    for button in config.MOUSE_BUTTONS:
        hook_module.MouseHook(button, lambda: None, lambda: None, 120)


# --- the command line ---------------------------------------------------------

def test_all_documented_flags_are_parsed():
    parsed = dictate.build_parser().parse_args([
        "--file", "a.wav", "--print", "--config", "c.json",
        "--install-autostart", "--uninstall-autostart",
        "--list-devices", "--no-tray",
    ])
    assert vars(parsed) == _EXPECTED_CLI


def test_no_flags_means_push_to_talk():
    assert vars(dictate.build_parser().parse_args([])) == _EXPECTED_CLI_EMPTY


def test_install_autostart_from_the_command_line(tmp_path, monkeypatch, capsys):
    startup = tmp_path / "Startup"
    startup.mkdir()
    monkeypatch.setattr(autostart, "startup_folder", lambda: startup)
    monkeypatch.setattr(autostart, "pythonw_for", lambda python: Path("pythonw.exe"))

    assert dictate.main(["--install-autostart"]) == _EXIT_OK

    written = startup / _LAUNCHER_NAME
    assert str(written) in capsys.readouterr().out
    assert "pythonw.exe" in written.read_text(encoding="utf-8")


def test_uninstall_autostart_from_the_command_line(tmp_path, monkeypatch, capsys):
    startup = tmp_path / "Startup"
    startup.mkdir()
    monkeypatch.setattr(autostart, "startup_folder", lambda: startup)
    monkeypatch.setattr(autostart, "pythonw_for", lambda python: Path("pythonw.exe"))
    dictate.main(["--install-autostart"])

    assert dictate.main(["--uninstall-autostart"]) == _EXIT_OK

    assert not (startup / _LAUNCHER_NAME).exists()


def test_a_startup_folder_that_cannot_be_used_is_reported(monkeypatch, capsys):
    def explode():
        raise OSError("APPDATA is not set")

    monkeypatch.setattr(autostart, "startup_folder", explode)

    result = dictate.main(["--install-autostart"])

    assert result != _EXIT_OK
    assert "APPDATA" in capsys.readouterr().err


# --- Windows only, and visible failures ---------------------------------------

def test_the_tool_refuses_to_start_anywhere_but_on_windows(monkeypatch):
    monkeypatch.setattr(dictate.os, "name", "posix")
    assert dictate.check_platform() is not None


def test_on_windows_there_is_nothing_to_refuse():
    assert dictate.check_platform() is None


def test_a_failure_without_a_console_opens_a_dialog(monkeypatch):
    boxes = []
    monkeypatch.setattr(dictate, "_has_console", lambda: False)
    monkeypatch.setattr(dictate, "_message_box",
                        lambda title, message: boxes.append((title, message)))

    dictate.report_fatal("the microphone is missing")

    assert boxes and "the microphone is missing" in boxes[0][1]


def test_a_failure_with_a_console_goes_to_stderr(monkeypatch, capsys):
    boxes = []
    monkeypatch.setattr(dictate, "_has_console", lambda: True)
    monkeypatch.setattr(dictate, "_message_box",
                        lambda title, message: boxes.append((title, message)))

    dictate.report_fatal("the configuration is broken")

    assert boxes == []
    assert "the configuration is broken" in capsys.readouterr().err


def test_a_console_means_stdout_and_stderr_both_exist(monkeypatch):
    monkeypatch.setattr(dictate.sys, "stdout", None)
    assert dictate._has_console() is False


def test_a_missing_desktop_does_not_break_the_report(monkeypatch, capsys):
    def explode(title, message):
        raise OSError("no window station")

    monkeypatch.setattr(dictate, "_message_box", explode)

    dictate.report_fatal("still visible in the terminal")

    assert "still visible in the terminal" in capsys.readouterr().err


# --- file conventions ---------------------------------------------------------

@pytest.mark.parametrize(
    "path",
    [
        pytest.param(dictate.__file__, id="dictate.py"),
        pytest.param(autostart.__file__, id="autostart.py"),
        pytest.param(Path(dictate.__file__).parent / "tests" / "test_wiring.py",
                     id="test_wiring.py"),
        pytest.param(Path(dictate.__file__).parents[2] / "README.md", id="README.md"),
    ],
)
def test_committed_file_uses_lf_endings_and_ends_with_a_newline(path):
    raw = Path(path).read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "file starts with a BOM"
    assert b"\r\n" not in raw, "file contains CRLF line endings"
    assert raw.endswith(b"\n"), "file does not end with a newline"


def test_importing_dictate_starts_nothing():
    # tests/test_wiring.py imports dictate; an unguarded main() would install a
    # global mouse hook and a tray icon in the middle of the test run.
    assert 'if __name__ == "__main__":' in Path(dictate.__file__).read_text(
        encoding="utf-8")
