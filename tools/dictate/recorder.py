"""Microphone capture for dictate: device selection and audio recording.

The recorder opens one input stream for as long as the user holds the push-to-talk
button and hands the captured audio back as a single 1-D ``float32`` array at
16 kHz, downmixed to one channel. That format is not a tuning knob: it is what
the transcriber consumes, and the sample rate its acoustic front end is built for.

Two entry points:

* :func:`pick_device` turns the user's ``mic_device`` setting into a device index.
  It is pure - the caller passes the device list in and nothing is queried from
  PortAudio.
* :class:`Recorder` records from one device. Nothing on its public surface
  raises: a microphone that is missing, unplugged, busy or that disappears
  mid-recording is reported in :attr:`Recorder.error` and yields an empty array,
  so the wiring layer decides how to tell the user.

Example:

    from recorder import Recorder, pick_device

    device = pick_device(sd.query_devices(), cfg.mic_device)
    recorder = Recorder(device)
    recorder.start()
    ...
    audio = recorder.stop()
    if recorder.error:
        print(recorder.error)

The PortAudio call itself is funnelled through the module-level helper
``_open_input_stream`` so tests can run without audio hardware.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Sequence

import numpy as np
import sounddevice

# The format the transcriber consumes, fixed rather than tuned: 16 kHz mono
# float32. A different sample rate would need resampling before recognition, and
# a different dtype would mean a conversion the recognizer does not expect.
SAMPLERATE = 16000
CHANNELS = 1
DTYPE = "float32"

# What a failed or empty recording returns: an array of the right dtype and
# nothing else, so callers can concatenate it with real audio and check .size.
_EMPTY_AUDIO = np.empty(0, dtype=np.float32)


def pick_device(devices: Sequence[dict], spec: str) -> int | None:
    """Return the index of the input device matching spec, or None.

    spec is the user's ``mic_device`` setting:

    * ``""`` (or only whitespace) returns None, which is sounddevice's system
      default input device.
    * a decimal number selects the device at that index.
    * anything else selects the first device whose name contains spec,
      compared case-insensitively.

    Only devices that can actually record are considered: an entry with fewer
    than one input channel (speakers, a loopback, an output-only endpoint) is
    never selected. The returned index always addresses the caller's list, i.e.
    the list PortAudio itself numbers - filtering decides *whether* a device is
    eligible, it never renumbers the result. None is also the answer when
    nothing matches or when the index does not exist; this function does not
    raise, because it runs on whatever the user typed into a config file.
    """
    spec = spec.strip()
    if not spec:
        return None
    inputs = [
        index
        for index, device in enumerate(devices)
        if (device.get("max_input_channels") or 0) >= 1
    ]
    if spec.isdigit():
        # str.isdigit() also accepts characters int() rejects (superscript
        # digits), so the conversion is guarded rather than assumed to work.
        try:
            index = int(spec)
        except ValueError:
            return None
        return index if index in inputs else None
    needle = spec.casefold()
    for index in inputs:
        if needle in str(devices[index].get("name", "")).casefold():
            return index
    return None


def _open_input_stream(
    *,
    device: int | None,
    samplerate: int,
    channels: int,
    callback: Callable[..., None],
) -> Any:
    """Open the PortAudio input stream that feeds callback.

    The single place that talks to sounddevice, so the recording logic can be
    tested without an audio device. The dtype is fixed here: whatever a caller
    asks for, samples arrive as float32.
    """
    return sounddevice.InputStream(
        device=device,
        samplerate=samplerate,
        channels=channels,
        dtype=DTYPE,
        callback=callback,
    )


def _to_mono(block: np.ndarray) -> np.ndarray:
    """Return one audio block as a 1-D float32 array, averaging extra channels.

    sounddevice hands the callback one row per frame and one column per channel,
    so a mono block is already in the right shape and averaging is a no-op on it.
    Averaging is what keeps the mono promise true for a multi-channel interface.
    """
    data = np.asarray(block, dtype=np.float32)
    if data.ndim > 1:
        data = data.mean(axis=1)
    return np.ascontiguousarray(data, dtype=np.float32)


class Recorder:
    """Record microphone audio while the user holds the push-to-talk button.

    ``device`` is an index into the device list or None for the system default
    input device - see :func:`pick_device`. ``samplerate`` and ``channels`` are
    what is requested from the device; :meth:`stop` always returns 1-D float32
    samples at ``samplerate``, downmixed to one channel.

    Call :meth:`start`, wait for the button to be released, then call
    :meth:`stop`. Recording twice with the same instance is fine: each start
    begins with an empty buffer, so two utterances never merge into one.

    Nothing here raises. Every failure - no microphone, a device that is busy,
    one that is unplugged, one that vanishes mid-recording - is recorded in
    :attr:`error`, and :meth:`stop` then returns an empty array instead of a
    partial recording that would transcribe into half a sentence. Only the first
    problem is kept: the rest are consequences of it.

    Example:

        recorder = Recorder(device=None)
        recorder.start()
        ...
        audio = recorder.stop()
        if recorder.error:
            print(f"no audio: {recorder.error}")
    """

    def __init__(
        self,
        device: int | None = None,
        samplerate: int = SAMPLERATE,
        channels: int = CHANNELS,
    ) -> None:
        self.device = device
        self.samplerate = samplerate
        self.channels = channels
        self.error: str | None = None
        # The callback below runs on PortAudio's audio thread while start/stop
        # run on the caller's, so the block list and the error are shared state.
        self._lock = threading.Lock()
        self._blocks: list[np.ndarray] = []
        self._stream: Any | None = None

    def start(self) -> None:
        """Open the input stream and begin collecting audio.

        Starting a recorder that is already recording does nothing. If the
        stream cannot be opened - no microphone, device index gone, driver
        refusing - or cannot be started, the reason lands in :attr:`error`, the
        recorder stays stopped, and no exception reaches the caller. A previous
        error is cleared, so every recording attempt is judged on its own and a
        re-plugged microphone gets a clean second try.
        """
        with self._lock:
            if self._stream is not None:
                return
            self._blocks = []
            self.error = None
        stream: Any | None = None
        try:
            stream = _open_input_stream(
                device=self.device,
                samplerate=self.samplerate,
                channels=self.channels,
                callback=self._capture,
            )
            # sounddevice creates a stream *stopped*: opening it alone captures
            # nothing, and the callback is never called.
            stream.start()
        except Exception as exc:  # every driver failure, not just PortAudioError
            # Report first: _fail keeps the first message, and closing a stream
            # that never ran would otherwise claim to be the real problem.
            self._fail(f"The microphone could not be opened: {exc}")
            if stream is not None:
                self._close(stream)  # otherwise the device stays held
            return
        with self._lock:
            self._stream = stream

    def stop(self) -> np.ndarray:
        """Close the stream and return everything captured since :meth:`start`.

        The result is a 1-D float32 array at this recorder's sample rate. It is
        empty - with :attr:`error` set - when the recording failed; a half
        captured utterance is thrown away rather than handed to the recognizer.
        Stopping a recorder that is not running returns an empty array, so a
        double stop or a start that never happened is harmless.
        """
        with self._lock:
            stream = self._stream
            self._stream = None
        if stream is not None:
            self._close(stream)
        # Taken after closing: the last blocks arrive while the stream shuts down.
        with self._lock:
            blocks = self._blocks
            self._blocks = []
            failed = self.error is not None
        if failed or not blocks:
            return _EMPTY_AUDIO
        try:
            return np.concatenate(blocks).astype(DTYPE, copy=False)
        except Exception as exc:
            self._fail(f"The captured audio could not be assembled: {exc}")
            return _EMPTY_AUDIO

    # --- internals ------------------------------------------------------------

    def _capture(self, indata, frames, time_info, status) -> None:
        """Append one block; this is the PortAudio callback.

        It runs on the audio thread. Non-fatal status flags (an input underflow,
        say) are ignored because they happen during perfectly good recordings.
        An exception must not die with this thread, though: it is recorded as
        this recorder's error, so the user finds out why the dictation is empty
        instead of getting silence.
        """
        try:
            block = _to_mono(indata)
        except Exception as exc:
            self._fail(f"An audio block could not be read: {exc}")
            return
        with self._lock:
            self._blocks.append(block)

    def _close(self, stream) -> None:
        """Shut the stream down, reporting a device that disappeared."""
        try:
            active = bool(getattr(stream, "active", False))
        except Exception as exc:
            # sounddevice reads Pa_IsStreamActive behind `active` and turns a
            # non-zero return code into a PortAudioError, so this status check
            # can raise like any other driver call. An unknown state is still no
            # reason to leak the stream, and no reason to raise either: report
            # it and shut the stream down as if it were still running.
            self._fail(f"The microphone could not be reached: {exc}")
            active = True
        if active:
            self._stop_and_close(stream)
            return
        # sounddevice reports active=False once a stream stopped running. A
        # recorder that is holding a stream it started never stopped it, so
        # this means the device went away underneath us.
        self._fail("The microphone stopped delivering audio; "
                   "it may have been disconnected.")
        self._stop_and_close(stream)

    def _stop_and_close(self, stream) -> None:
        """Stop and close are attempted separately.

        A failing stop must not leave the stream - and the device it holds -
        open.
        """
        for step in (stream.stop, stream.close):
            try:
                step()
            except Exception as exc:
                self._fail(f"The microphone could not be closed: {exc}")

    def _fail(self, message: str) -> None:
        """Record the first problem; anything after it is a consequence."""
        with self._lock:
            if self.error is None:
                self.error = message
