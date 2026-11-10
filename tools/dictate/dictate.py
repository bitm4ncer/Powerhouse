"""dictate: push-to-talk dictation for Windows.

This is the layer that connects the other modules into a program a human runs:

    button down  ->  record microphone          (recorder)
    button up    ->  recognise, correct, type   (transcriber, dictionary, inserter)
    anywhere      ->  a coloured dot             (tray, hook)

Three decisions shape everything below.

**The button callback only queues work.** The low-level mouse hook is called by
Windows on the thread that installed it, with a budget of
``LowLevelHooksTimeout`` - about 300 ms. A callback that overruns it is dropped
by Windows, and the user is left with a push-to-talk button that silently does
nothing. So :meth:`Pipeline.on_press` decides, paints the dot and returns; the
microphone is opened by a worker thread that was idle anyway.

**One recognizer, one caller.** A recognition that does not come back - which
is what a CUDA library missing at decode time does - would otherwise wedge every
following utterance behind it. Every recognition therefore runs on a thread of
its own with a deadline (:func:`transcribe_bounded`), and no second one starts
while the first is still in the model.

**A failure the user cannot see is a failure.** An empty transcription is not
an utterance, an unresolvable microphone name is not the system default, and a
keyboard batch Windows only half accepted is not a typed sentence. Each of
those turns into a tray notification, a grey dot and a beep, and each of them
leaves the tool able to try again.

Example:

    python dictate.py                       # push to talk, tray icon, hook
    python dictate.py --no-tray             # the same, messages on the console
    python dictate.py --file spoken.wav --print    # one WAV, no button
    python dictate.py --install-autostart   # start at every logon

Run :func:`main`; nothing here happens at import time, which is what lets the
test suite import the module and drive every part of it.
"""

from __future__ import annotations

import argparse
import os
import queue
import sys
import threading
import wave
from pathlib import Path
from typing import Any, Callable, NamedTuple, Sequence

import numpy as np

import autostart
import hook as hook_module
from config import Config, ensure_config
from dictionary import (apply_replacements, build_initial_prompt,
                        load_replacements, load_vocabulary)
from inserter import insert_text
from recorder import CHANNELS, DTYPE, SAMPLERATE, Recorder
from transcriber import Transcriber
from tray import INITIAL_STATE, Tray

# The name the user sees. Used in the messages, not in the tray's own German.
APP_NAME = "dictate"

# This file, and the configuration that sits next to it. The tool runs from a
# checkout, so the defaults have to be the ones that are committed here; a user
# with their own settings passes --config or copies this file.
SCRIPT_PATH = Path(__file__).resolve()
DEFAULT_CONFIG_PATH = SCRIPT_PATH.with_name("dictate.config.json")

# The two dictionary files, resolved next to the configuration file: they belong
# to the installation, not to whoever happens to run the tool.
VOCABULARY_NAME = "vocabulary.txt"
REPLACEMENTS_NAME = "replacements.txt"

# The states that accept a new press. "error" is one of them on purpose: the
# user has to be able to try again without restarting the tool.
PRESS_ACCEPTING_STATES = frozenset({"ready", "error"})

# What "recording started" and "that went wrong" sound like, as winsound.Beep
# arguments. Two different tones, because the two are told apart in a room
# where nobody is looking at the tray.
BEEP_TONES = {
    "start": (1000, 60),    # Hz, ms - a short click, as confirmation
    "error": (440, 250),    # Hz, ms - a lower, longer tone, as a complaint
}

# How long a recognition may take before the release is reported as failed.
# A 120 s utterance on the CPU fallback is a few seconds of work; a wedged CUDA
# call has been observed to run past 180 s, so this is not a latency target but
# the line between "slow" and "gone".
TRANSCRIBE_TIMEOUT_SECONDS = 60.0

# Process exit codes. 0 is a run that did what it was asked to; everything else
# says which part of the start-up did not work.
EXIT_OK = 0
EXIT_HOOK = 1        # the push-to-talk hook could not be installed
EXIT_SETUP = 2       # configuration, model or audio file is unusable
EXIT_FAILED = 3      # it started, and recognition failed


# --- the pure gate ------------------------------------------------------------

def accept_press(state: str) -> bool:
    """Whether a press in ``state`` may start a recording.

    Only ``"ready"`` and ``"error"`` accept one. A press while recording would
    open a second microphone over the first, and a press while transcribing
    would hand the model a second utterance while it still works on the first.

    This is a function of the state and nothing else - no pipeline, no clock, no
    tray - so the rule can be read, tested and argued about on its own.
    """
    return state in PRESS_ACCEPTING_STATES


def check_platform() -> str | None:
    """Return why dictate cannot run here, or None when it can.

    The whole tool is Win32 - a low-level mouse hook, synthetic keyboard input,
    winsound - and the modules below cannot even be imported elsewhere. Saying
    so in one line beats a traceback out of a ctypes call.
    """
    if os.name != "nt":
        return f"{APP_NAME} only runs on Windows, not on os.name == {os.name!r}."
    return None


# --- the dictionary -----------------------------------------------------------

class Dictionary(NamedTuple):
    """The two dictionary tables, read once.

    ``problems`` is what could not be read. A missing or malformed dictionary
    costs spelling accuracy and nothing else, so it is reported rather than
    raised - dictation must not stop because somebody deleted a text file.
    """

    prompt: str = ""
    rules: Sequence[tuple[str, str]] = ()
    problems: Sequence[str] = ()


def dictionary_paths(config_path: Path) -> tuple[Path, Path]:
    """Return the vocabulary and replacement files that belong to ``config_path``.

    Both live in the configuration's own folder, so one folder is the whole
    installation: config, vocabulary, replacements. The tool that reads them
    does not care how it was started.
    """
    folder = Path(config_path).parent
    return folder / VOCABULARY_NAME, folder / REPLACEMENTS_NAME


def load_dictionary(config_path: Path) -> Dictionary:
    """Read the vocabulary and the replacement rules of this installation.

    The vocabulary becomes the initial prompt that biases the recognizer
    towards the names this user says; the rules repair what it mishears. Each
    file is optional: what is missing or unreadable lands in ``problems``, and
    the rest is still used.
    """
    vocabulary_path, replacements_path = dictionary_paths(config_path)
    problems: list[str] = []
    prompt = ""
    rules: list[tuple[str, str]] = []
    try:
        prompt = build_initial_prompt(load_vocabulary(vocabulary_path))
    except (OSError, ValueError) as exc:
        problems.append(f"{vocabulary_path} could not be read ({exc}).")
    try:
        rules = load_replacements(replacements_path)
    except (OSError, ValueError) as exc:
        problems.append(f"{replacements_path} could not be read ({exc}).")
    return Dictionary(prompt=prompt, rules=tuple(rules), problems=tuple(problems))


# --- reading a recorded WAV ---------------------------------------------------

def read_wav(path: Path) -> np.ndarray:
    """Return a WAV file as 1-D float32 samples at 16 kHz, mono.

    That is exactly what :class:`recorder.Recorder` produces, so a file can be
    recognised exactly like a recording. Files are read as 16-bit PCM, which is
    what every recorder writes and what ``wave`` can read without a third
    library; a stereo file is averaged down to mono.

    A different sample rate is refused rather than resampled: dictation is 16
    kHz because that is what the model's front end is built for, and resampling
    a file the user picked would hide the difference between "this file is not
    dictation audio" and "this file was recorded badly".
    """
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if width != 2:
        raise ValueError(f"{path} is {width * 8}-bit; dictate needs 16-bit audio.")
    if rate != SAMPLERATE:
        raise ValueError(
            f"{path} is {rate} Hz; dictate needs {SAMPLERATE} Hz audio.")
    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return np.ascontiguousarray(samples, dtype=np.float32)


# --- a bounded recognition ----------------------------------------------------

def transcribe_bounded(
    transcriber,
    audio: np.ndarray,
    timeout: float = TRANSCRIBE_TIMEOUT_SECONDS,
    on_finish: Callable[[], None] | None = None,
) -> tuple[str, str | None]:
    """Recognise ``audio`` and return ``(text, problem)``.

    ``problem`` is None when recognition worked, and the sentence to show the
    user when it did not - so an empty string is never mistaken for silence.

    The recognition runs on a thread of its own and this call waits at most
    ``timeout`` seconds for it. That is not politeness: with a CUDA library
    missing at decode time, the first call returned nothing and the next one
    never returned at all. A push-to-talk tool that waits forever on a release
    is worse than one that says it gave up.

    ``on_finish`` is called - on the recognising thread, whenever it ends - the
    moment the model is free again. The caller uses it to keep exactly one
    recognition in flight: a second call into a model that is still busy is
    undefined behaviour, and an abandoned thread cannot be killed.

    The error is cleared before the call, so whatever is there afterwards is
    this call's own. :class:`transcriber.Transcriber` also uses ``error`` for
    the informational "the GPU was not usable, so dictate fell back to the
    CPU" note from ``load()``, and that note must not be mistaken for a failed
    utterance.
    """
    outcome: dict[str, Any] = {}
    finished = threading.Event()

    def recognise() -> None:
        try:
            transcriber.error = None
            outcome["text"] = transcriber.transcribe(audio)
        except Exception as exc:   # the model never raises; this is the net
            outcome["problem"] = f"The recording could not be transcribed: {exc}"
        finally:
            if on_finish is not None:
                on_finish()
            finished.set()

    threading.Thread(target=recognise, name="dictate-transcribe",
                     daemon=True).start()
    if not finished.wait(timeout):
        return "", (
            f"The speech recognition did not answer within {timeout:.0f} seconds "
            f"and was left behind. dictate waits no longer - restart it if the "
            f"next push of the button does not work."
        )
    if "problem" in outcome:
        return "", outcome["problem"]
    if transcriber.error:
        return "", transcriber.error
    return outcome.get("text", ""), None


# --- the beeps ----------------------------------------------------------------

def beep(name: str) -> None:
    """Make the tone of ``name`` - see :data:`BEEP_TONES`.

    A missing or unhappy sound device is not worth an exception: the user gets
    the same information from the dot and the notification.
    """
    frequency, duration = BEEP_TONES[name]
    _beep(frequency, duration)


def _beep(frequency: int, duration: int) -> bool:
    """Call winsound.Beep once; False when there is no sound to make."""
    try:
        import winsound
    except ImportError:       # not Windows, or a winsound that is gone
        return False
    try:
        winsound.Beep(frequency, duration)
    except Exception as exc:  # no sound device, session without an audio desk
        print(f"{APP_NAME}: no beep ({exc})", file=sys.stderr)
        return False
    return True


# --- telling the user ---------------------------------------------------------

def _has_console() -> bool:
    """Whether this process has somewhere to print to.

    pythonw.exe has no console at all - sys.stdout is None - so a message that
    only goes to stderr is never seen. That is exactly the case the autostart
    launcher creates.
    """
    return sys.stdout is not None and sys.stderr is not None


def _message_box(title: str, message: str) -> None:
    """Show a modal message box. The only Win32 call in this module.

    It shows a message and takes two buttons' worth of constants; it types
    nothing, and the test suite pins that this module never touches the
    keyboard at all.
    """
    try:
        import ctypes

        MB_OK = 0x00000000
        MB_ICONERROR = 0x00000010
        ctypes.windll.user32.MessageBoxW(None, message, title, MB_OK | MB_ICONERROR)
    except Exception as exc:    # no desktop, no window station, no ctypes
        print(f"{APP_NAME}: no message box ({exc})", file=sys.stderr)


def report_fatal(message: str) -> None:
    """Report something that ends this run, where the user can actually see it.

    The console when there is one, a message box when there is not. Under the
    autostart launcher there never is one, and a tool that fails silently at
    every logon is the failure mode this whole line exists to prevent.
    """
    print(f"{APP_NAME}: {message}", file=sys.stderr, flush=True)
    if not _has_console():
        _message_box(f"{APP_NAME} - Fehler", message)


def open_path(path: Path) -> None:
    """Open ``path`` with whatever the desktop associates with it."""
    try:
        os.startfile(str(path))     # type: ignore[attr-defined]
    except Exception as exc:
        print(f"{APP_NAME}: {path} could not be opened ({exc})", file=sys.stderr)


# --- the microphone -----------------------------------------------------------

def query_devices() -> list[dict]:
    """Return every audio device the host knows, inputs and outputs alike."""
    import sounddevice

    return [dict(device) for device in sounddevice.query_devices()]


def default_input_device() -> int | None:
    """Return the index Windows uses as the default input, or None."""
    import sounddevice

    return sounddevice.default.device[0]


def format_devices(devices: Sequence[dict], default_input: int | None = None) -> str:
    """Return the device list as text, for --list-devices.

    The default input is marked, because that is the one a user is looking for.
    Output-only devices are listed as such rather than hidden: knowing that
    "Speakers" is not a microphone answers most questions about a name that
    does not resolve.
    """
    lines = []
    for index, device in enumerate(devices):
        mark = "*" if index == default_input else " "
        name = str(device.get("name", "?"))
        hostapi = device.get("hostapi", "?")
        inputs = device.get("max_input_channels") or 0
        rate = device.get("default_samplerate", 0)
        lines.append(
            f"{index:>3} {mark} {name} [{hostapi}] "
            f"in:{inputs} out:{device.get('max_output_channels') or 0} "
            f"{int(rate)} Hz"
        )
    return "\n".join(lines)


def candidate_devices(devices: Sequence[dict], spec: str) -> list[int]:
    """Return every input device that ``spec`` selects, in the order PortAudio lists them.

    The same rules :func:`recorder.pick_device` uses, without stopping at the
    first hit: a name can match a WASAPI endpoint and an MME one, and only one
    of the two accepts the 16 kHz dictate records at.
    """
    spec = str(spec).strip()
    if not spec:
        return []
    inputs = [
        index for index, device in enumerate(devices)
        if (device.get("max_input_channels") or 0) >= 1
    ]
    if spec.isdigit():
        try:
            index = int(spec)
        except ValueError:       # characters int() rejects, e.g. superscripts
            return []
        return [index] if index in inputs else []
    needle = spec.casefold()
    return [
        index for index in inputs
        if needle in str(devices[index].get("name", "")).casefold()
    ]


def probe_input_device(index: int) -> str | None:
    """Try to open the input at ``index``; return None or why it failed.

    This is the answer to the WASAPI problem: some Windows endpoints reject
    16 kHz with "Invalid sample rate" while the same microphone on MME or
    DirectSound accepts it, and ``query_devices`` lists both. Opening the
    stream once at start-up is the only way to know which one this machine
    actually has - and it costs a few milliseconds, once.
    """
    import sounddevice

    try:
        stream = sounddevice.InputStream(device=index, samplerate=SAMPLERATE,
                                         channels=CHANNELS, dtype=DTYPE)
    except Exception as exc:
        return str(exc)
    try:
        stream.close()
    except Exception as exc:
        return str(exc)
    return None


def resolve_input_device(
    spec: str,
    devices: Sequence[dict],
    probe: Callable[[int], str | None],
) -> tuple[int | None, str | None]:
    """Return ``(device index, warning)`` for the user's ``micDevice`` setting.

    Every device the setting selects is tried in turn, because a name can
    resolve to an endpoint that will not open at 16 kHz. The first one that
    opens wins and produces no warning.

    If the setting is empty the system default is used - that is what an empty
    setting means, and there is nothing to report. If it selects nothing, or
    nothing that can be opened, the default is used *and the user is told*:
    recording from a different microphone than the configured one without
    saying so is how a user ends up dictating into the wrong room.

    The default itself is not probed: with no configuration to honour, the
    recorder opens it on the first press and reports there if it cannot, which
    is the same message on the same path as every other microphone failure.
    """
    if not str(spec).strip():
        return None, None        # the system default, and nothing to report
    candidates = candidate_devices(devices, spec)
    problems: list[str] = []
    for index in candidates:
        problem = probe(index)
        if problem is None:
            return index, None
        name = str(devices[index].get("name", index))
        problems.append(f"{name}: {problem}")
    if not candidates:
        return None, (
            f"No input device matches micDevice {spec!r} (see --list-devices). "
            f"Recording from the system default microphone instead."
        )
    return None, (
        f"None of the {len(candidates)} input devices matching micDevice "
        f"{spec!r} could be opened ({'; '.join(problems)}). Recording from the "
        f"system default microphone instead."
    )


# --- the background worker ----------------------------------------------------

class Worker:
    """One thread that runs the pipeline's jobs one after another.

    The queue is what keeps the order: a release that arrives before the press
    that opened the microphone has finished still runs after it, so the recorder
    is never stopped while it is being started. A thread per job would lose
    that, and the microphone would be left open and recording into a buffer
    nobody reads.

    The thread is daemonised, so a dictation tool that is on its way out does
    not wait for the queue, and it is started on the first job rather than at
    construction: importing dictate must not start a thread.
    """

    def __init__(self, name: str = "dictate-pipeline", on_error=None) -> None:
        self.name = name
        self.on_error = on_error
        self._queue: queue.SimpleQueue = queue.SimpleQueue()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def submit(self, job: Callable[[], None]) -> None:
        """Hand one job to the worker and return at once."""
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, name=self.name,
                                                daemon=True)
                self._thread.start()
            self._queue.put(job)

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            if job is None:
                return
            try:
                job()
            except Exception as exc:
                # The jobs guard themselves; this is the net under that net, so
                # a surprise leaves the worker alive for the next utterance.
                if self.on_error is not None:
                    self.on_error(exc)
                else:
                    print(f"{APP_NAME}: {exc}", file=sys.stderr, flush=True)

    def stop(self) -> None:
        """Ask the worker to end after the job it is running."""
        self._queue.put(None)


class StderrReporter:
    """The tray's two jobs without a tray: remember the state, print the messages.

    With ``--no-tray`` there is a console and no icon, so the state is kept in
    a string (the press gate needs it) and every message goes to stderr. The
    pipeline talks to this exactly as it talks to :class:`tray.Tray`.
    """

    def __init__(self) -> None:
        self.state = INITIAL_STATE
        self.messages: list[str] = []

    def set_state(self, state: str) -> None:
        self.state = state

    def notify(self, message: str) -> None:
        self.messages.append(message)
        print(f"{APP_NAME}: {message}", file=sys.stderr, flush=True)

    def stop(self) -> None:
        """There is nothing running to stop. The console does not own a loop."""
        return None


# --- the pipeline -------------------------------------------------------------

class Pipeline:
    """One push-to-talk session: press, record, recognise, correct, type.

    ``config`` is the user's settings, ``transcriber`` the warm recognizer,
    ``recorder`` the microphone and ``tray`` whatever reports state - the real
    tray icon, or the stderr reporter when there is none.

    The two public methods are the whole interface: :meth:`on_press` and
    :meth:`on_release` are what the mouse hook calls, from its own thread and
    from the watchdog thread. Neither blocks and neither raises; the work
    happens on the worker that ``submit`` names.

    ``replacements`` are the dictionary's correction rules, ``transcribe_timeout``
    the deadline of one recognition, and ``print_instead`` writes the text to
    stdout instead of typing it - for a run without a window to type into.

    Example:

        pipeline = Pipeline(cfg, transcriber, recorder, tray)
        pipeline.on_press()      # from the mouse hook, in under a millisecond
        ...
        pipeline.on_release()    # typing happens on the worker thread
        ...
        pipeline.state           # 'ready'
    """

    def __init__(
        self,
        config: Config,
        transcriber,
        recorder,
        tray,
        *,
        replacements: Sequence[tuple[str, str]] = (),
        submit: Callable[[Callable[[], None]], None] | None = None,
        transcribe_timeout: float = TRANSCRIBE_TIMEOUT_SECONDS,
        print_instead: bool = False,
    ) -> None:
        self.config = config
        self.transcriber = transcriber
        self.recorder = recorder
        self.tray = tray
        self.replacements = list(replacements)
        self.transcribe_timeout = transcribe_timeout
        self.print_instead = print_instead
        self._lock = threading.Lock()
        # True while a recognition is inside the model. The flag belongs to the
        # recognising thread and is cleared by it, which is why it is not reset
        # at the end of the release: the call it belongs to may still be running.
        self._recognising = False
        self._worker = Worker(on_error=self._unexpected)
        self._submit = submit if submit is not None else self._worker.submit

    # --- what the mouse hook calls --------------------------------------------

    @property
    def state(self) -> str:
        """The state the tray is in right now."""
        return self.tray.state

    @property
    def accepts_press(self) -> bool:
        """Whether a press right now would start a recording."""
        with self._lock:
            return self._wants_press()

    def _wants_press(self) -> bool:
        return accept_press(self.tray.state) and not self._recognising

    def on_press(self) -> None:
        """Start one utterance. Returns as soon as the work is queued.

        A press that arrives while recording or transcribing is refused - the
        gate is :func:`accept_press`, and the microphone is opened by the
        worker rather than here.
        """
        with self._lock:
            if not self._wants_press():
                return
            self.tray.set_state("recording")
        self._submit(self._open_microphone)

    def on_release(self) -> None:
        """End the utterance. Returns as soon as the work is queued.

        A release with no open session is ignored: the watchdog thread and the
        button can both end a session, and only one of them may stop the
        microphone.
        """
        with self._lock:
            if self.tray.state != "recording":
                return
            self._recognising = True
            self.tray.set_state("transcribing")
        self._submit(self._transcribe_and_type)

    def set_replacements(self, rules: Sequence[tuple[str, str]]) -> None:
        """Use ``rules`` from the next utterance on - the tray's reload action."""
        self.replacements = list(rules)

    # --- the jobs --------------------------------------------------------------

    def _open_microphone(self) -> None:
        if self.config.beep:
            beep("start")
        self.recorder.start()
        if self.recorder.error:
            self._fail(self.recorder.error)

    def _transcribe_and_type(self) -> None:
        """Everything between the button coming up and the next press.

        Each step can fail on its own, and each failure ends the utterance the
        same way: a message, a grey dot, a beep. Nothing here raises into the
        worker, and nothing here leaves the tool in a state it cannot leave.
        """
        handed_over = False
        try:
            audio = self.recorder.stop()
            if self.recorder.error:
                self._fail(self.recorder.error)
                return
            if getattr(audio, "size", 0) == 0:
                # Nothing was captured. A click too short to be speech is not an
                # error, and the recorder has already said so if it was one.
                self._settle()
                return
            handed_over = True
            text, problem = transcribe_bounded(
                self.transcriber, audio, self.transcribe_timeout,
                on_finish=self._recognition_finished,
            )
            if problem is not None:
                self._fail(problem)
                return
            text = apply_replacements(text, self.replacements)
            if not text.strip():
                # Voice activity detection legitimately recognises nothing in a
                # short click or a cough. There is nothing to type.
                self._settle()
                return
            if self._deliver(text):
                self._settle()
        except Exception as exc:
            self._fail(f"The recording could not be handled: {exc}")
        finally:
            if not handed_over:
                self._recognition_finished()

    def _deliver(self, text: str) -> bool:
        """Type the text into whatever has focus, or print it.

        Returns whether the text made it out. inserter.insert_text raises
        RuntimeError when Windows accepted only part of the batch - a
        foreground window refusing input is the usual reason - and that is
        reported here rather than re-raised, so the tool stays up and the next
        press is a fresh attempt.
        """
        if self.print_instead:
            print(text)
            return True
        try:
            insert_text(text, self.config.insert_mode)
        except RuntimeError as exc:
            self._fail(f"The text could not be typed into the window: {exc}")
            return False
        return True

    def _settle(self) -> None:
        """The utterance is over and nothing went wrong."""
        self.tray.set_state("ready")

    def _fail(self, message: str) -> None:
        """Show one problem and go to the grey dot, leaving a retry possible."""
        self.tray.set_state("error")
        self.tray.notify(message)
        if self.config.beep:
            beep("error")

    def _recognition_finished(self) -> None:
        """Called on the recognising thread: the model is free again."""
        with self._lock:
            self._recognising = False

    def _unexpected(self, exc: Exception) -> None:
        """Last net: a job raised something the jobs themselves did not catch."""
        self._fail(f"{exc}")

    # --- lifecycle ------------------------------------------------------------

    def stop(self) -> None:
        """Let the worker end. The tool is going out, not pushing anything."""
        self._worker.stop()


# --- the seams ----------------------------------------------------------------
#
# Everything below builds its collaborators through these four functions. They
# exist for the test suite - a real microphone, a real recognizer and a real
# global mouse hook cannot be part of an automated run - and they are the only
# place the concrete classes are named.

def build_transcriber(cfg: Config, prompt: str) -> Transcriber:
    """Build the recognizer this configuration asks for, warm but not loaded."""
    return Transcriber(cfg.model, language=cfg.language, device=cfg.device,
                       initial_prompt=prompt)


def build_recorder(device: int | None) -> Recorder:
    """Build the microphone recorder for one already-resolved device."""
    return Recorder(device)


def build_tray(**callbacks: Callable[[], None]) -> Tray:
    """Build the notification-area icon with the four menu callbacks."""
    return Tray(**callbacks)


def build_hook(
    button: str,
    on_press: Callable[[], None],
    on_release: Callable[[], None],
    max_seconds: float,
) -> hook_module.MouseHook:
    """Build the push-to-talk hook for the configured button."""
    return hook_module.MouseHook(button, on_press=on_press, on_release=on_release,
                                 max_seconds=max_seconds)


def run_hook(hook, tray, on_ready: Callable[[], None]) -> threading.Thread:
    """Install the mouse hook on a thread of its own; report a failed install.

    The hook installs a global low-level mouse hook and then pumps a message
    loop, so it needs a thread that does nothing else - and it must not be the
    main thread, which belongs to pystray.

    :meth:`hook.MouseHook.run` raises ``RuntimeError`` when
    ``SetWindowsHookExW`` fails. Raising into a daemon thread would print a
    traceback nobody sees and leave a push-to-talk button that does nothing at
    all, so the failure becomes a grey dot and a notification instead.
    """

    def install() -> None:
        try:
            hook.run(on_ready=on_ready)
        except RuntimeError as exc:
            tray.set_state("error")
            tray.notify(str(exc))

    return threading.Thread(target=install, name="dictate-hook", daemon=True)


# --- the command line ---------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Return the command line the tool is started with."""
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Push-to-talk dictation for Windows: hold the mouse button, "
                    "speak, and the words appear in the focused window.",
    )
    parser.add_argument(
        "--file", type=Path, metavar="PATH",
        help=f"transcribe this {SAMPLERATE} Hz mono 16-bit WAV and exit "
             f"(no button, no tray)",
    )
    parser.add_argument(
        "--print", action="store_true",
        help="print what was recognised instead of typing it",
    )
    parser.add_argument(
        "--config", type=Path, metavar="PATH",
        help=f"the configuration file to use (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--install-autostart", action="store_true",
        help="start dictate at every logon",
    )
    parser.add_argument(
        "--uninstall-autostart", action="store_true",
        help="stop starting dictate at logon",
    )
    parser.add_argument(
        "--list-devices", action="store_true",
        help="print the audio devices and exit",
    )
    parser.add_argument(
        "--no-tray", action="store_true",
        help="no tray icon; the console shows the state and every message",
    )
    return parser


# --- the two ways to run ------------------------------------------------------

def run_file(path: Path, cfg: Config, table: Dictionary) -> int:
    """Transcribe one WAV file, print the text, and exit.

    No hook, no tray, no microphone: the same model and the same dictionary as
    the push-to-talk run, on a file instead of a recording. That makes it the
    only end-to-end check of the pipeline a script can do.
    """
    try:
        audio = read_wav(path)
    except (OSError, ValueError, wave.Error) as exc:
        report_fatal(f"{path} could not be read: {exc}")
        return EXIT_SETUP
    transcriber = build_transcriber(cfg, table.prompt)
    transcriber.load()
    if not transcriber.is_ready:
        report_fatal(transcriber.error or "The speech model could not be loaded.")
        return EXIT_SETUP
    text, problem = transcribe_bounded(transcriber, audio)
    if problem is not None:
        report_fatal(problem)
        return EXIT_FAILED
    print(apply_replacements(text, table.rules))
    return EXIT_OK


def run_app(
    cfg: Config,
    config_path: Path,
    table: Dictionary,
    tray_enabled: bool = True,
    print_instead: bool = False,
) -> int:
    """Start the recognizer, the tray and the hook, and stay up.

    The main thread is pystray's: ``Tray.run`` wants the main thread and blocks
    there until the tool quits. The hook gets a thread of its own, the pipeline
    a third for the work the button queues, and the model is loaded before any
    of them exists so that a broken installation is reported before a hook
    starts swallowing the user's button.

    Everything that can be wrong at start-up is reported here rather than at
    the first press: the model, the microphone, the dictionary.
    """
    transcriber = build_transcriber(cfg, table.prompt)
    transcriber.load()
    if not transcriber.is_ready:
        report_fatal(transcriber.error or "The speech model could not be loaded.")
        return EXIT_SETUP

    device, warning = resolve_input_device(cfg.mic_device, query_devices(),
                                          probe_input_device)
    recorder = build_recorder(device)

    # The hook does not exist yet, and neither do the tray callbacks that stop
    # it. Both are filled in below; nothing calls a callback before the tray
    # icon is up, by which time the holder is complete.
    holder: dict[str, Any] = {}

    def on_quit() -> None:
        """The Beenden entry: take the button back, then take the icon down."""
        hook = holder.get("hook")
        if hook is not None:
            hook.stop()
        reporter.stop()

    def on_reload() -> None:
        """The Wörterbuch entry: read both dictionary files again, right now."""
        fresh = load_dictionary(config_path)
        pipeline.set_replacements(fresh.rules)
        transcriber.initial_prompt = fresh.prompt
        message = f"The dictionary was reloaded: {len(fresh.rules)} rules."
        if fresh.problems:
            message += " " + " ".join(fresh.problems)
        reporter.notify(message)

    def on_select_mic() -> None:
        """The Mikrofon entry: which device, and where to change it.

        There is no console to ask on, so the list is shown in a message box
        and the configuration is opened next to it - the user copies a name or
        an index into micDevice.
        """
        _message_box(f"{APP_NAME} - Mikrofon wählen",
                     "Set micDevice in the configuration to a name or an index "
                     "from this list:\n\n"
                     + format_devices(query_devices(), default_input_device()))
        open_path(config_path)

    def on_open_config() -> None:
        """The Config entry: open the configuration in whatever handles JSON."""
        open_path(config_path)

    tray = (build_tray(on_quit=on_quit, on_reload=on_reload,
                      on_select_mic=on_select_mic, on_open_config=on_open_config)
            if tray_enabled else None)
    reporter: Any = tray if tray is not None else StderrReporter()

    pipeline = Pipeline(cfg, transcriber, recorder, reporter,
                        replacements=table.rules, print_instead=print_instead)

    if warning:
        reporter.notify(warning)
    if transcriber.error:
        # Only reachable when the model did load: the CPU fallback note.
        reporter.notify(transcriber.error)
    for problem in table.problems:
        reporter.notify(problem)

    hook = build_hook(cfg.mouse_button, pipeline.on_press, pipeline.on_release,
                      cfg.max_record_seconds)
    holder["hook"] = hook

    def on_hook_ready() -> None:
        """The hook is live and the button is the tool's from here on."""
        reporter.set_state("ready")

    if tray is not None:
        thread = run_hook(hook, tray, on_hook_ready)
        thread.start()
        try:
            tray.run()               # pystray, on the main thread, until stop()
        except KeyboardInterrupt:
            on_quit()
        finally:
            hook.stop()
            thread.join(5)
        return EXIT_OK

    # Without a tray nothing else keeps the process alive, so the hook's message
    # loop is the main loop - and its failure is the end of this run.
    try:
        hook.run(on_ready=on_hook_ready)
    except KeyboardInterrupt:
        pass
    except RuntimeError as exc:
        report_fatal(str(exc))
        return EXIT_HOOK
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Parse the command line and run what it asks for. Returns the exit code."""
    args = build_parser().parse_args(argv)

    reason = check_platform()
    if reason is not None:
        report_fatal(reason)
        return EXIT_SETUP

    if args.install_autostart:
        try:
            launcher = autostart.install_autostart(SCRIPT_PATH)
        except OSError as exc:
            report_fatal(f"The logon entry could not be written: {exc}")
            return EXIT_SETUP
        print(f"{APP_NAME} will start at every logon: {launcher}")
        return EXIT_OK

    if args.uninstall_autostart:
        try:
            autostart.uninstall_autostart()
        except OSError as exc:
            report_fatal(f"The logon entry could not be removed: {exc}")
            return EXIT_SETUP
        print(f"{APP_NAME} will no longer start at logon.")
        return EXIT_OK

    if args.list_devices:
        try:
            print(format_devices(query_devices(), default_input_device()))
        except Exception as exc:     # no audio subsystem at all
            report_fatal(f"No audio devices could be listed: {exc}")
            return EXIT_SETUP
        print("\n* marks the default input. Set it as micDevice in the "
              "configuration.")
        return EXIT_OK

    config_path = Path(args.config) if args.config else DEFAULT_CONFIG_PATH
    try:
        cfg = ensure_config(config_path)
    except (OSError, ValueError) as exc:
        report_fatal(f"The configuration {config_path} is unusable: {exc}")
        return EXIT_SETUP

    table = load_dictionary(config_path)
    if args.file:
        return run_file(args.file, cfg, table)
    return run_app(cfg, config_path, table, tray_enabled=not args.no_tray,
                   print_instead=args.print)


if __name__ == "__main__":
    sys.exit(main())
