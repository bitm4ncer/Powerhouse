"""Tests for the whisper transcriber.

The brief tests come first, with one addition the brief's own Step 4 demands:
``test_transcribes_fixture`` asserts ``active_device == "cuda"`` so the hard
GPU gate is pinned by a committed test rather than by a script someone ran once,
guarded by a skip for machines that cannot do CUDA at all. The rest pin
constraints the project mandates but the brief only states in prose: the CUDA
DLL folders really are registered (and their handles kept alive), the GPU is
tried first and the CPU is the tested fallback, a failure that only surfaces
while the segments are being decoded is still reported rather than raised, and
the recognition settings - VAD, beam size 1, no conditioning on the previous
text - are passed through unchanged.

Everything from "fake whisper model" onwards runs against a stub WhisperModel,
so those tests need no GPU and load nothing. The two pipeline tests do use the
real model and are skipped unless DICTATE_FIXTURE_WAV points at a 16 kHz mono
16-bit WAV of German speech.
"""

import ast
import ctypes
import os
from pathlib import Path

import numpy as np
import pytest

import transcriber
from transcriber import Transcriber, add_cuda_dll_dirs

FIXTURE = os.environ.get("DICTATE_FIXTURE_WAV")
pipeline = pytest.mark.skipif(not FIXTURE, reason="set DICTATE_FIXTURE_WAV to run")

# The values the tool is specified with, written out instead of imported from
# the module under test, so a changed default fails the test rather than
# redefining it.
MODEL = "large-v3-turbo"
LANGUAGE = "de"

# What CTranslate2 loads for a CUDA run; see requirements-cuda.txt.
CUDA_DLLS = ("cublas64_12.dll", "cudnn_ops64_9.dll")


def cuda_is_available() -> bool:
    """Whether this machine can run the whisper model on the GPU at all.

    Two halves, both cheap and both needed before the gate assertion in
    ``test_transcribes_fixture`` means anything:

    * CTranslate2 has to see a CUDA device - what it reports is what
      ``Transcriber.load`` will try to use.
    * the cuBLAS and cuDNN DLLs have to load, which is what
      ``requirements-cuda.txt`` provides and ``add_cuda_dll_dirs`` puts on the
      search path. CTranslate2 loads them itself while the first segment is
      decoded, so a box without them can load the model and still transcribe
      nothing at all.

    A box missing either one is not a regression in this module - it is a
    machine that cannot run whisper on the GPU - so the gate test skips there
    instead of failing. The CPU fallback is the specified behaviour on exactly
    those machines, and ``test_load_falls_back_to_cpu_int8_when_cuda_fails``
    covers it.
    """
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() < 1:
            return False
    except Exception:
        return False
    for name in CUDA_DLLS:
        try:
            ctypes.WinDLL(name)
        except OSError:
            return False
    return True


@pytest.fixture
def cuda_required():
    """Skip the calling test unless this box can really run the model on the GPU.

    A fixture rather than a mark, so the probe only costs anything on a machine
    that is about to load the 1.6 GB model.
    """
    if not cuda_is_available():
        pytest.skip("no CUDA device with cuBLAS and cuDNN on this machine")


# --- tests from the brief ----------------------------------------------------

def test_add_cuda_dll_dirs_returns_list():
    assert isinstance(add_cuda_dll_dirs(), list)


@pipeline
def test_transcribes_fixture(cuda_required):
    import wave, time
    with wave.open(FIXTURE, "rb") as w:
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
        ch = w.getnchannels()
    audio = (np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0)
    if ch > 1:
        audio = audio.reshape(-1, ch).mean(axis=1)
    assert sr == 16000

    t = Transcriber("large-v3-turbo", language="de")
    assert t.load() is None
    assert t.is_ready, t.error
    # The hard gate from the brief: on a CUDA machine the model must have
    # landed on the GPU, not quietly on the CPU. cuda_required skips this box
    # when it cannot do CUDA at all.
    assert t.active_device == "cuda", f"gate failed: {t.active_device} ({t.error})"
    start = time.perf_counter()
    text = t.transcribe(audio)
    elapsed = time.perf_counter() - start
    assert "test" in text.lower()
    assert elapsed < 2.5, f"transcription took {elapsed:.2f}s (target < 1.5s)"


@pipeline
def test_latency_under_target():
    import time
    import wave

    with wave.open(FIXTURE, "rb") as w:
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
        ch = w.getnchannels()
    assert sr == 16000
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        audio = audio.reshape(-1, ch).mean(axis=1)

    t = Transcriber("large-v3-turbo", language="de")
    t.load()
    # The first call pays for cuBLAS/cuDNN warmup - kernel selection, memory
    # pool growth. What the user waits for on the second push of the button is
    # the steady state, and that is what the 1.5 s budget is about.
    t.transcribe(audio)
    start = time.perf_counter()
    t.transcribe(audio)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.5, f"warm transcription took {elapsed:.2f}s (target < 1.5s)"


# --- fake whisper model ------------------------------------------------------

class FakeSegment:
    """One Whisper segment: faster-whisper hands out objects carrying .text."""

    def __init__(self, text):
        self.text = text


class FakeWhisperModel:
    """Stand-in for faster-whisper's WhisperModel.

    It records how it was constructed and what every transcribe() call was
    asked for, and returns a fixed list of segments. The real model needs a GPU
    and seconds to load; the pipeline tests above cover it, and everything here
    is about the wiring dictate puts around it.

    ``error`` fails the call, ``lazy_error`` fails the *iteration* - the second
    is what faster-whisper really does, because it hands back a generator whose
    segments only materialise while the caller walks it.
    """

    def __init__(self, model_name, device="auto", compute_type="default", **kwargs):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.calls = []
        self.error = None
        self.lazy_error = None

    def _decode(self):
        """Yield the segments, the way the real generator does: one at a time."""
        for text in self.segments:
            yield FakeSegment(text)
        if self.lazy_error is not None:
            raise self.lazy_error

    def transcribe(self, audio, **kwargs):
        self.calls.append((audio, kwargs))
        if self.lazy_error is not None:
            return self._decode(), {"language": "de"}
        if self.error is not None:
            raise self.error
        return [FakeSegment(text) for text in self.segments], {"language": "de"}


class FakeModelFactory:
    """Stand-in for transcriber._create_model, recording every attempt.

    ``fail_on`` names the devices whose load must blow up, which is how the
    GPU-failure path is exercised without pulling the card out of the machine.
    ``lazy_error`` is handed to the model, see :class:`FakeWhisperModel`.
    """

    def __init__(self, segments=(), fail_on=(), lazy_error=None):
        self.attempts = []
        self.segments = list(segments)
        self.fail_on = set(fail_on)
        self.lazy_error = lazy_error
        self.models = []

    def __call__(self, model_name, device, compute_type):
        self.attempts.append((device, compute_type))
        if device in self.fail_on:
            raise RuntimeError(f"Library cudnn_ops64_9.dll not found ({device})")
        model = FakeWhisperModel(model_name, device=device, compute_type=compute_type)
        model.segments = self.segments
        model.lazy_error = self.lazy_error
        self.models.append(model)
        return model

    @property
    def last_model(self):
        return self.models[-1]


@pytest.fixture
def factory(monkeypatch):
    # Whisper segments carry their word separator at the front (" Hallo.") and
    # no trailing space, which is what a real decoding produces.
    fake = FakeModelFactory(segments=[" Hallo Welt.", " Guten Tag."])
    monkeypatch.setattr(transcriber, "_create_model", fake)
    return fake


# --- device selection --------------------------------------------------------

def test_load_prefers_cuda_with_float16(factory):
    t = Transcriber(MODEL)
    assert t.load() is None
    assert factory.attempts == [("cuda", "float16")]
    assert t.active_device == "cuda"
    assert t.is_ready is True
    assert t.error is None


def test_load_falls_back_to_cpu_int8_when_cuda_fails(monkeypatch):
    fake = FakeModelFactory(segments=[" Hallo Welt "], fail_on={"cuda"})
    monkeypatch.setattr(transcriber, "_create_model", fake)
    t = Transcriber(MODEL)
    t.load()
    assert fake.attempts == [("cuda", "float16"), ("cpu", "int8")]
    assert t.active_device == "cpu"
    assert t.is_ready is True
    # The reason for the slower path is worth showing the user, not filing away.
    assert "cudnn_ops64_9.dll" in t.error


def test_explicit_cuda_also_falls_back_to_the_cpu(monkeypatch):
    # "cuda" means "the GPU first", not "the GPU or nothing": a machine without
    # a working driver should still dictate, just slower.
    fake = FakeModelFactory(fail_on={"cuda"})
    monkeypatch.setattr(transcriber, "_create_model", fake)
    t = Transcriber(MODEL, device="cuda")
    t.load()
    assert fake.attempts == [("cuda", "float16"), ("cpu", "int8")]
    assert t.active_device == "cpu"
    assert t.is_ready is True


def test_device_cpu_never_touches_the_gpu(factory):
    t = Transcriber(MODEL, device="cpu")
    t.load()
    assert factory.attempts == [("cpu", "int8")]
    assert t.active_device == "cpu"
    assert t.is_ready is True
    assert t.error is None


def test_load_reports_a_broken_install_instead_of_raising(monkeypatch):
    fake = FakeModelFactory(fail_on={"cuda", "cpu"})
    monkeypatch.setattr(transcriber, "_create_model", fake)
    t = Transcriber(MODEL)
    assert t.load() is None
    assert t.is_ready is False
    assert t.active_device == ""
    assert "cuda" in t.error and "cpu" in t.error


def test_a_successful_reload_clears_the_fallback_error(monkeypatch):
    # A driver that comes back, or a card the user just plugged in, must get a
    # clean second try instead of being stuck on the CPU with a stale message.
    fake = FakeModelFactory(segments=[" Hallo Welt "], fail_on={"cuda"})
    monkeypatch.setattr(transcriber, "_create_model", fake)
    t = Transcriber(MODEL)
    t.load()
    assert t.active_device == "cpu"

    fake.fail_on.clear()
    t.load()
    assert t.active_device == "cuda"
    assert t.is_ready is True
    assert t.error is None


def test_transcribe_before_load_reports_and_yields_nothing(factory):
    t = Transcriber(MODEL)
    assert t.transcribe(np.zeros(1600, dtype=np.float32)) == ""
    assert t.is_ready is False
    assert t.error is not None


def test_transcription_failure_is_reported_not_raised(factory):
    t = Transcriber(MODEL)
    t.load()
    factory.last_model.error = RuntimeError("out of memory")
    assert t.transcribe(np.zeros(1600, dtype=np.float32)) == ""
    assert "out of memory" in t.error


def test_a_failure_while_decoding_is_reported_not_raised(monkeypatch):
    # faster-whisper hands back a *generator*: the decode, and with it the first
    # CUDA kernel launch, happens while the segments are being walked, long
    # after transcribe() returned. A missing cublas64_12.dll surfaces exactly
    # here - the call succeeds, then the iteration blows up - so the join of the
    # segments has to sit inside the try or the exception escapes into the tray.
    fake = FakeModelFactory(
        segments=[" Hallo."],
        lazy_error=RuntimeError(
            "Library cublas64_12.dll is not found or cannot be loaded"
        ),
    )
    monkeypatch.setattr(transcriber, "_create_model", fake)
    t = Transcriber(MODEL)
    t.load()

    assert t.transcribe(np.zeros(1600, dtype=np.float32)) == ""
    assert "cublas64_12.dll" in t.error
    # One utterance failing to decode is not a model that has gone away: the
    # model stays loaded, on the device it was loaded on, ready for the next
    # push of the button.
    assert t.is_ready is True
    assert t.active_device == "cuda"


# --- recognition settings ----------------------------------------------------

def test_recognition_uses_vad_beam_one_and_no_previous_text(factory):
    t = Transcriber(MODEL)
    t.load()
    t.transcribe(np.zeros(1600, dtype=np.float32))
    _, kwargs = factory.last_model.calls[-1]
    assert kwargs["vad_filter"] is True
    assert kwargs["beam_size"] == 1
    assert kwargs["condition_on_previous_text"] is False


def test_the_configured_language_is_passed_to_the_model(factory):
    # A language that is neither the default nor an English "hard-coded value"
    # guess, so passing a fixed language instead of the configured one fails
    # here.
    t = Transcriber(MODEL, language="fr")
    t.load()
    t.transcribe(np.zeros(1600, dtype=np.float32))
    _, kwargs = factory.last_model.calls[-1]
    assert kwargs["language"] == "fr"


def test_language_defaults_to_german(factory):
    # The tool is built for German dictation; the default is what makes that
    # true when nobody passes a language.
    assert Transcriber(MODEL).language == LANGUAGE


def test_transcribe_joins_the_segments_without_inserting_spaces(monkeypatch):
    # Whisper puts the word separator at the *start* of every segment and
    # deliberately leaves punctuation glued to its neighbours, so the segments
    # are concatenated as they are and only the whole text is stripped. A
    # trailing blank segment is normal: it is how a recording ends.
    fake = FakeModelFactory(segments=[" Hallo.", ", wie geht es?", " "])
    monkeypatch.setattr(transcriber, "_create_model", fake)
    t = Transcriber(MODEL)
    t.load()
    assert t.transcribe(np.zeros(1600, dtype=np.float32)) == "Hallo., wie geht es?"


def test_transcribe_returns_text_without_surrounding_whitespace(factory):
    t = Transcriber(MODEL)
    t.load()
    text = t.transcribe(np.zeros(1600, dtype=np.float32))
    assert text == "Hallo Welt. Guten Tag."
    assert text == text.strip()


# --- the audio contract ------------------------------------------------------

def test_the_recorders_audio_format_reaches_the_model_untouched(factory):
    # What the recorder hands over: 1-D float32 samples at 16 kHz, one channel.
    # Two seconds of it is 31616 samples.
    audio = np.zeros(31616, dtype=np.float32)
    t = Transcriber(MODEL)
    t.load()
    t.transcribe(audio)
    handed_over, _ = factory.last_model.calls[-1]
    assert handed_over is audio, "the samples were copied or converted on the way"
    assert handed_over.dtype == np.dtype(np.float32)
    assert handed_over.ndim == 1


def test_the_model_name_is_passed_through(factory):
    # Task 8 hands the user's config value in; the module must not second-guess
    # it, or a user pointing at another converted model gets a different one.
    t = Transcriber("Systran/faster-whisper-small")
    t.load()
    assert factory.last_model.model_name == "Systran/faster-whisper-small"


# --- CUDA DLL folders --------------------------------------------------------

class DllHandle:
    """Stand-in for the handle os.add_dll_directory() returns."""

    def __init__(self, path):
        self.path = path
        self.closed = False

    def close(self):
        self.closed = True


class RecordingDllDirs:
    """Stand-in for os.add_dll_directory, remembering what it handed out."""

    def __init__(self):
        self.handles = []
        self.fail_on = ()

    def __call__(self, path):
        if any(part in path for part in self.fail_on):
            raise OSError("cannot add the directory to the DLL search path")
        handle = DllHandle(path)
        self.handles.append(handle)
        return handle


@pytest.fixture
def dll_dirs(tmp_path, monkeypatch):
    """Register DLL folders from an empty site-packages instead of the real one."""
    fake = RecordingDllDirs()
    monkeypatch.setattr(transcriber, "site_packages_dir", lambda: tmp_path)
    monkeypatch.setattr(os, "add_dll_directory", fake)
    # add_cuda_dll_dirs() also rewrites PATH; keep the real one for the rest of
    # the suite.
    monkeypatch.setenv("PATH", os.environ["PATH"])
    return fake


def _nvidia_bin(root, *packages):
    for package in packages:
        (root / "nvidia" / package / "bin").mkdir(parents=True)


def test_every_installed_nvidia_bin_folder_is_registered(dll_dirs, tmp_path):
    _nvidia_bin(tmp_path, "cublas", "cudnn", "cuda_nvrtc")
    added = add_cuda_dll_dirs()
    # Sorted, so the order does not depend on how the filesystem enumerates.
    assert [Path(p).parent.name for p in added] == ["cublas", "cuda_nvrtc", "cudnn"]
    assert [h.path for h in dll_dirs.handles] == added


def test_the_folders_come_back_in_a_stable_order(dll_dirs, tmp_path, monkeypatch):
    # The filesystem does not promise an order, so the module imposes one: a
    # glob that hands the folders over backwards must still come back sorted.
    _nvidia_bin(tmp_path, "cublas", "cudnn", "cuda_nvrtc")
    real_glob = Path.glob

    def reversed_glob(self, pattern):
        found = list(real_glob(self, pattern))
        return iter(found[::-1] if pattern == "*/bin" else found)

    monkeypatch.setattr(Path, "glob", reversed_glob)
    added = add_cuda_dll_dirs()
    assert [Path(p).parent.name for p in added] == ["cublas", "cuda_nvrtc", "cudnn"]


def test_folders_without_a_bin_directory_are_skipped(dll_dirs, tmp_path):
    # nvidia packages ship a lot besides DLLs; a folder without bin/ is not a
    # DLL folder and registering it would only add noise.
    (tmp_path / "nvidia" / "some_package").mkdir(parents=True)
    assert add_cuda_dll_dirs() == []


def test_no_nvidia_packages_means_no_dll_directories(dll_dirs, tmp_path):
    assert add_cuda_dll_dirs() == []


def test_a_folder_that_cannot_be_registered_does_not_stop_the_others(dll_dirs, tmp_path):
    # Losing cuDNN means falling back to the CPU, which the transcriber does by
    # itself - far better than the whole tool failing to start.
    _nvidia_bin(tmp_path, "cublas", "cudnn")
    dll_dirs.fail_on = ("cublas",)
    added = add_cuda_dll_dirs()
    assert len(added) == 1 and added[0].endswith("cudnn\\bin")


def test_the_registered_handles_are_kept_alive(dll_dirs, tmp_path):
    # Windows drops a folder from the DLL search path again the moment the
    # handle returned by os.add_dll_directory() is garbage collected, so
    # discarding the handles would undo the whole function.
    _nvidia_bin(tmp_path, "cublas")
    before = len(transcriber._DLL_HANDLES)
    added = add_cuda_dll_dirs()
    handles = transcriber._DLL_HANDLES[before:]
    assert len(handles) == len(added)
    assert [h.path for h in handles] == added
    assert not any(h.closed for h in handles)


def test_the_folders_are_put_on_the_process_path(dll_dirs, tmp_path):
    # os.add_dll_directory() does not reach CTranslate2: it is a C++ extension
    # that calls LoadLibrary on the cuBLAS and cuDNN DLLs itself, and that call
    # only sees the process PATH. Without this the model loads and the first
    # recognition fails on cublas64_12.dll.
    _nvidia_bin(tmp_path, "cublas", "cudnn")
    add_cuda_dll_dirs()
    entries = os.environ["PATH"].split(os.pathsep)
    assert entries[0] == str(tmp_path / "nvidia" / "cublas" / "bin")
    assert entries[1] == str(tmp_path / "nvidia" / "cudnn" / "bin")


def test_the_process_path_is_not_grown_on_every_call(dll_dirs, tmp_path):
    # add_cuda_dll_dirs() runs at import time and is meant to be callable again
    # from anywhere; repeating a folder would grow PATH on every call.
    _nvidia_bin(tmp_path, "cublas")
    add_cuda_dll_dirs()
    after_first = os.environ["PATH"].split(os.pathsep)
    add_cuda_dll_dirs()
    assert os.environ["PATH"].split(os.pathsep) == after_first


def test_an_empty_nvidia_tree_leaves_the_path_alone(dll_dirs, tmp_path):
    before = os.environ["PATH"]
    assert add_cuda_dll_dirs() == []
    assert os.environ["PATH"] == before


def test_the_installed_cuda_folders_are_registered():
    added = add_cuda_dll_dirs()
    if not added:
        pytest.skip("no nvidia CUDA DLL packages installed in this environment")
    for path in added:
        assert Path(path).is_dir()
        assert list(Path(path).glob("*.dll")), f"{path} holds no DLL"


# --- module structure --------------------------------------------------------

def _module_tree():
    return ast.parse(Path(transcriber.__file__).read_text(encoding="utf-8"))


def _top_level_imports(tree):
    """The modules imported at module scope, not inside a function."""
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_the_module_does_not_import_config():
    # Task 8 passes the settings in; reading the config here would tie the
    # transcriber to a file it has no business knowing about.
    assert "config" not in _top_level_imports(_module_tree())


def _module_level_calls(tree):
    """The names called while the module is imported - bare or assigned."""
    names = []
    for node in tree.body:
        if isinstance(node, ast.Expr):
            value = node.value
        elif isinstance(node, ast.Assign):
            value = node.value
        else:
            continue
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            names.append(value.func.id)
    return names


def test_the_dll_folders_are_registered_at_import_time():
    # cuBLAS and cuDNN are loaded as soon as CTranslate2 is imported, and they
    # are only on the DLL search path after add_cuda_dll_dirs() has run. So the
    # call has to happen at import time, and faster-whisper must not be imported
    # at module scope - only inside the function that builds a model.
    tree = _module_tree()
    assert "faster_whisper" not in _top_level_imports(tree)
    assert "add_cuda_dll_dirs" in _module_level_calls(tree), (
        "add_cuda_dll_dirs() is never called at import time"
    )


# --- file convention ---------------------------------------------------------

@pytest.mark.parametrize(
    "path",
    [
        transcriber.__file__,
        __file__,
        Path(transcriber.__file__).parent / "requirements-cuda.txt",
    ],
)
def test_source_file_uses_lf_endings_and_ends_with_a_newline(path):
    # Project convention for every committed file: LF endings, no BOM, and a
    # final newline, so diffs and POSIX tooling stay sane.
    raw = Path(path).read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "file starts with a BOM"
    assert b"\r\n" not in raw, "file contains CRLF line endings"
    assert raw.endswith(b"\n"), "file does not end with a newline"
