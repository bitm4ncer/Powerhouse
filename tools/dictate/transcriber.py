"""Speech recognition for dictate: a warm whisper model with a CUDA fallback.

:class:`Transcriber` holds one loaded faster-whisper model and turns the
recorder's audio into text. Two decisions are baked in rather than exposed,
because both are what makes dictation feel immediate on a machine with an RTX
card: the GPU is tried first in float16, and recognition runs with voice
activity detection, a beam of one, and no conditioning on the previous text -
the latency settings, not the accuracy settings.

The model is loaded once and kept warm. :meth:`Transcriber.load` takes seconds
the first time and nothing after that, which is why it is separate from
:meth:`Transcriber.transcribe`.

Nothing on the public surface raises. A missing CUDA runtime, a driver that
does not match the cuDNN wheels, a transcription that runs out of memory - all
of it is reported through :attr:`Transcriber.error`, so the tray layer can tell
the user instead of dying mid-sentence.

Example:

    from transcriber import Transcriber

    t = Transcriber("large-v3-turbo", language="de")
    t.load()
    if not t.is_ready:
        print(t.error)
    else:
        print(t.transcribe(audio))
"""

from __future__ import annotations

import os
import sysconfig
from pathlib import Path
from typing import Any

import numpy as np

# What each device is asked for: float16 on a consumer GPU is about half the
# work and half the memory of float32, int8 on the CPU keeps a machine without a
# usable GPU responsive instead of merely correct.
CUDA_COMPUTE_TYPE = "float16"
CPU_COMPUTE_TYPE = "int8"

# os.add_dll_directory() takes a folder off the DLL search path again as soon as
# the handle it returned is garbage collected, so the handles are collected here
# and live as long as the module does.
_DLL_HANDLES: list[Any] = []


def site_packages_dir() -> Path:
    """The site-packages of the environment that is running dictate.

    Kept separate so tests can point it at a folder they built themselves.
    """
    return Path(sysconfig.get_path("purelib"))


def add_cuda_dll_dirs() -> list[str]:
    """Put every installed ``nvidia/*/bin`` folder on the DLL search path.

    The nvidia CUDA wheels install their DLLs in per-package ``bin`` folders
    that nothing adds to the search path on Windows, so CTranslate2 cannot find
    ``cublas64_12.dll`` and ``cudnn_ops64_9.dll`` even when both are installed.

    Two places have to learn about them, and one of them is not obvious:
    ``os.add_dll_directory`` covers loads Python itself performs (ctypes, an
    extension module), but CTranslate2 is a C++ extension that calls
    ``LoadLibrary`` on the cuBLAS and cuDNN DLLs itself, and that call does not
    see the directories Python registered - it only sees the process PATH. With
    ``os.add_dll_directory`` alone the model loads happily and then the first
    recognition fails with ``Library cublas64_12.dll is not found or cannot be
    loaded``, so the PATH is extended as well.

    Returns the folders that were added, in a stable order. A folder that
    cannot be registered is skipped rather than raised over: it only costs the
    GPU, which the caller has a fallback for.
    """
    root = site_packages_dir() / "nvidia"
    added: list[str] = []
    # glob only yields what is already there, so the missing-folder case needs
    # no test of its own.
    for folder in sorted(root.glob("*/bin")):
        path = str(folder)
        try:
            _DLL_HANDLES.append(os.add_dll_directory(path))
        except OSError:
            continue
        added.append(path)
    _prepend_to_path(added)
    return added


def _prepend_to_path(dirs: list[str]) -> None:
    """Put dirs at the front of the process PATH, where CTranslate2 looks.

    Folders already on the PATH are left where they are, so calling this twice
    - at import time and from a test - does not grow the variable.
    """
    current = os.environ.get("PATH", "").split(os.pathsep)
    missing = [folder for folder in dirs if folder not in current]
    if missing:
        os.environ["PATH"] = os.pathsep.join(missing + current)


# Import time, before anything pulls in CTranslate2: loading that extension is
# what looks for cuBLAS and cuDNN, and the folders it needs were only just put
# on the search path above.
_CUDA_DLL_DIRS = add_cuda_dll_dirs()


def _create_model(model_name: str, device: str, compute_type: str) -> Any:
    """Build the faster-whisper model that :class:`Transcriber` wraps.

    faster-whisper is imported here rather than at module scope so that the DLL
    folders are on the search path before CTranslate2 is loaded. It is also the
    single seam the tests replace to exercise the fallback without a GPU.
    """
    from faster_whisper import WhisperModel

    return WhisperModel(model_name, device=device, compute_type=compute_type)


class Transcriber:
    """Turn 16 kHz mono float32 audio into text with one warm whisper model.

    ``model_name`` is whatever faster-whisper accepts - a size such as
    ``large-v3-turbo`` or a converted model id. ``language`` is passed to the
    recognizer, and ``device`` is ``auto``, ``cuda`` or ``cpu``.

    Call :meth:`load` once, then :meth:`transcribe` per utterance. Nothing
    raises: a problem is reported in :attr:`error` and the call that hit it
    returns nothing to insert.

    Example:

        t = Transcriber(cfg.model, language=cfg.language, device=cfg.device)
        t.load()
        ...
        text = t.transcribe(audio)
        if t.error:
            print(t.error)
    """

    def __init__(
        self,
        model_name: str,
        language: str = "de",
        device: str = "auto",
        *,
        initial_prompt: str = "",
    ) -> None:
        self.model_name = model_name
        self.language = language
        self.device = device
        # Comma-joined vocabulary that biases the recognizer towards the names
        # this user actually says; empty means "no prompt". Set it before the
        # first transcribe, or assign to it to change it for the next call.
        self.initial_prompt = initial_prompt
        # Which device actually won the load; "" until load() has run.
        self.active_device = ""
        self.is_ready = False
        self.error: str | None = None
        self._model: Any | None = None

    def load(self) -> None:
        """Load the model, on the GPU if that works and on the CPU if it does not.

        ``auto`` and ``cuda`` both start on the GPU in float16 and retry once
        on the CPU in int8; ``cpu`` starts and stays there. When the GPU was
        tried and lost, :attr:`active_device` says ``cpu`` and :attr:`error`
        carries why - dictation still works, but slower, and the user is told.

        Every attempt is re-tried from scratch: the state below is cleared, so a
        card that was missing a moment ago gets a clean second try. If no
        attempt works the reason is in :attr:`error` and :attr:`is_ready` stays
        False.
        """
        # error needs no reset: every path out of this method assigns it.
        self.is_ready = False
        self.active_device = ""
        self._model = None
        failures: list[str] = []
        for target, compute_type in self._targets():
            try:
                self._model = _create_model(self.model_name, target, compute_type)
            except Exception as exc:  # a missing DLL, a driver mismatch, OOM
                failures.append(f"{target}/{compute_type}: {exc}")
                continue
            self.active_device = target
            self.is_ready = True
            self.error = (
                f"The GPU was not usable, so dictate fell back to the CPU: "
                f"{'; '.join(failures)}"
                if failures
                else None
            )
            return
        self.error = f"The speech model could not be loaded: {'; '.join(failures)}"

    def transcribe(self, audio: np.ndarray) -> str:
        """Return the spoken text of one recording.

        ``audio`` is what the recorder produces: 1-D float32 samples at 16 kHz,
        one channel. It is handed to the model unchanged.

        Recognition runs with voice activity detection, a beam of one, and no
        conditioning on the previous text: the user is waiting, and a dictation
        is a single utterance rather than a conversation. ``initial_prompt`` is
        the recognizer's own vocabulary hint - the terms from vocabulary.txt -
        and is passed on as it is; None when there are none. The segments are
        concatenated as whisper returns them - it puts the word separator at the
        start of a segment and keeps punctuation glued to its neighbour - and
        the finished text is stripped.

        Returns an empty string when the model is not loaded or recognition
        fails; the reason is in :attr:`error`.
        """
        if self._model is None:
            self.error = "The speech model is not loaded."
            return ""
        try:
            segments, _info = self._model.transcribe(
                audio,
                language=self.language,
                vad_filter=True,
                beam_size=1,
                condition_on_previous_text=False,
                initial_prompt=self.initial_prompt or None,
            )
            return "".join(segment.text for segment in segments).strip()
        except Exception as exc:
            self.error = f"The recording could not be transcribed: {exc}"
            return ""

    # --- internals ------------------------------------------------------------

    def _targets(self) -> list[tuple[str, str]]:
        """The ``(device, compute_type)`` attempts :meth:`load` makes, in order.

        An unrecognised device name lands on the CPU: it is the side that always
        works, and the config layer is where a bad value is rejected.
        """
        if self.device in ("auto", "cuda"):
            return [("cuda", CUDA_COMPUTE_TYPE), ("cpu", CPU_COMPUTE_TYPE)]
        return [("cpu", CPU_COMPUTE_TYPE)]
