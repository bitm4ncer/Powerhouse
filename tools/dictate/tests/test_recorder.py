"""Tests for the microphone recorder.

The first six tests are the ones the task brief specifies verbatim. The rest pin
project constraints the brief states in prose but does not test: the fixed
16 kHz mono float32 format the transcriber consumes, and the promise that the
recorder reports hardware problems through ``error`` instead of raising.

Every test runs against a fake PortAudio layer (see the ``portaudio`` fixture),
so the suite never opens a real stream and needs no microphone.
"""

from pathlib import Path

import numpy as np
import pytest
import sounddevice

import recorder
from recorder import pick_device, Recorder

DEVICES = [
    {"name": "Mikrofon (JBL Quantum350 Wireless)", "max_input_channels": 1},
    {"name": "Analogue 1/2 (5- Audient iD14)", "max_input_channels": 2},
    {"name": "Loop-back 1/2 (5- Audient iD14)", "max_input_channels": 0},
]

# The capture format is fixed by what the transcriber consumes. The values are
# written out here instead of being imported from recorder, so a changed default
# in the module under test fails the test rather than redefining it.
SAMPLERATE = 16000
CHANNELS = 1
DTYPE = "float32"


# --- tests from the brief ----------------------------------------------------

def test_empty_spec_uses_system_default():
    assert pick_device(DEVICES, "") is None


def test_index_spec():
    assert pick_device(DEVICES, "1") == 1


def test_substring_spec_case_insensitive():
    assert pick_device(DEVICES, "audient") == 1


def test_skips_output_only_devices():
    assert pick_device(DEVICES, "loop-back") is None


def test_unknown_spec_returns_none():
    assert pick_device(DEVICES, "nicht-vorhanden") is None


def test_stop_after_error_returns_empty_array():
    r = Recorder(device=99999)  # no such device
    r.start()
    audio = r.stop()
    assert isinstance(audio, np.ndarray)
    assert audio.size == 0
    assert r.error is not None


# --- fake PortAudio ----------------------------------------------------------

class FakeStream:
    """Stand-in for a sounddevice InputStream.

    It models the detail that matters here: sounddevice creates a stream
    *stopped*, and only ``start()`` makes it run and deliver anything to the
    callback. A fake that reported itself as running from the start would let a
    recorder that never starts the stream pass every test.
    """

    def __init__(self, device, samplerate, channels, dtype, callback):
        self.device = device
        self.samplerate = samplerate
        self.channels = channels
        self.dtype = dtype
        self.callback = callback
        # True while the stream is running, exactly as sounddevice reports it.
        self.active = False
        self.closed = False
        self.start_error = None
        self.close_error = None

    def start(self):
        if self.start_error is not None:
            raise self.start_error
        self.active = True

    def feed(self, block):
        """Hand one block to the recorder's callback, as the audio thread does."""
        assert self.active, "a stream that was never started delivers nothing"
        self.callback(block, len(block), None, None)

    def stop(self):
        self.active = False

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class UnreadableStatusStream(FakeStream):
    """A stream whose ``active`` property raises, the way real PortAudio can.

    sounddevice reads ``Pa_IsStreamActive`` behind that property and turns a
    non-zero return code into a ``PortAudioError`` - so the status check is one
    of the few places where ``stop()`` can be handed an exception it never
    asked for.
    """

    @property
    def active(self):
        raise sounddevice.PortAudioError("Pa_IsStreamActive failed")

    @active.setter
    def active(self, value):
        """The real property is read-only; writes are quietly ignored."""


class FakePortAudio:
    """Stand-in for the sounddevice module, without any audio hardware.

    It models the three things the recorder has to cope with: an unknown device
    index fails the way PortAudio fails, a stream that cannot be started fails
    the way a busy endpoint fails, and an accepted, started stream delivers
    blocks to the callback it was opened with.
    """

    def __init__(self, devices=DEVICES):
        self.devices = list(devices)
        self.streams = []
        self.open_error = None
        self.start_error = None
        self.stream_class = FakeStream

    def InputStream(self, **kwargs):
        if self.open_error is not None:
            raise self.open_error
        index = kwargs.get("device")
        if index is not None and not 0 <= index < len(self.devices):
            raise sounddevice.PortAudioError(f"Invalid device {index}")
        stream = self.stream_class(**kwargs)
        stream.start_error = self.start_error
        self.streams.append(stream)
        return stream

    @property
    def last_stream(self):
        return self.streams[-1]


class UnusableBlock:
    """An audio block the recorder cannot turn into samples."""

    def __len__(self):
        return 0

    def __array__(self, dtype=None, copy=None):
        raise ValueError("audio thread handed over something unusable")


@pytest.fixture(autouse=True)
def portaudio(monkeypatch):
    fake = FakePortAudio()
    monkeypatch.setattr(recorder, "sounddevice", fake)
    return fake


def _block(frames, channels=1, value=0.5):
    return np.full((frames, channels), value, dtype=np.float32)


# --- the audio format is fixed -----------------------------------------------

def test_capture_defaults_are_16khz_mono_float32():
    assert recorder.SAMPLERATE == SAMPLERATE
    assert recorder.CHANNELS == CHANNELS
    assert recorder.DTYPE == DTYPE
    r = Recorder(device=None)
    assert (r.samplerate, r.channels) == (SAMPLERATE, CHANNELS)


def test_recorder_opens_the_stream_at_16khz_mono_float32(portaudio):
    # The sample rate is what the transcriber's front end is built for; the
    # channels and the dtype are what make stop() hand back float32 mono.
    r = Recorder(device=None)
    r.start()
    stream = portaudio.last_stream
    assert stream.samplerate == SAMPLERATE
    assert stream.channels == CHANNELS
    assert stream.dtype == DTYPE
    assert stream.device is None  # None is sounddevice's system default input


def test_recorder_passes_the_selected_device_through(portaudio):
    Recorder(device=1).start()
    assert portaudio.last_stream.device == 1


def test_captured_audio_is_float32_mono(portaudio):
    r = Recorder(device=None)
    r.start()
    portaudio.last_stream.feed(_block(160))
    audio = r.stop()
    assert audio.dtype == np.float32
    assert audio.shape == (160,)


def test_blocks_are_concatenated_in_capture_order(portaudio):
    r = Recorder(device=None)
    r.start()
    portaudio.last_stream.feed(np.full((2, 1), 0.25, dtype=np.float32))
    portaudio.last_stream.feed(np.full((3, 1), 0.75, dtype=np.float32))
    assert r.stop().tolist() == [0.25, 0.25, 0.75, 0.75, 0.75]


def test_multichannel_capture_is_downmixed_to_mono(portaudio):
    # Downmixing is what keeps the promise "mono out" true even when a user
    # points dictate at a stereo interface.
    r = Recorder(device=None, channels=2)
    r.start()
    portaudio.last_stream.feed(np.array([[0.0, 2.0], [1.0, 3.0]], dtype=np.float32))
    audio = r.stop()
    assert audio.shape == (2,)
    assert audio.dtype == np.float32
    assert audio.tolist() == [1.0, 2.0]


# --- never raise: every failure lands in `error` -----------------------------

def test_recorder_starts_without_an_error():
    assert Recorder(device=None).error is None


def test_stop_without_start_returns_an_empty_array():
    audio = Recorder(device=None).stop()
    assert audio.dtype == np.float32
    assert audio.size == 0


def test_stop_after_an_empty_recording_returns_an_empty_array(portaudio):
    r = Recorder(device=None)
    r.start()
    audio = r.stop()
    assert audio.size == 0
    assert r.error is None, "a recording that simply captured nothing is not an error"


def test_device_loss_during_recording_is_reported(portaudio):
    # A microphone that disappears mid-recording leaves a stream that is no
    # longer active. That has to end up in `error` with an empty array back,
    # not as an exception and not as a half-recorded utterance.
    r = Recorder(device=None)
    r.start()
    portaudio.last_stream.feed(_block(160))
    portaudio.last_stream.active = False  # unplugged while recording
    audio = r.stop()
    assert r.error is not None
    assert audio.dtype == np.float32
    assert audio.size == 0


def test_failure_inside_the_audio_callback_is_reported(portaudio):
    # Whatever goes wrong on the PortAudio audio thread - a vanished device, a
    # backend error - must not die silently in that thread and leave a recorder
    # that silently captures nothing.
    r = Recorder(device=None)
    r.start()
    portaudio.last_stream.feed(UnusableBlock())
    audio = r.stop()
    assert r.error is not None
    assert audio.size == 0


def test_a_failing_close_is_reported(portaudio):
    # Closing the stream touches the device, so it can fail too.
    r = Recorder(device=None)
    r.start()
    portaudio.last_stream.close_error = sounddevice.PortAudioError("device gone")
    audio = r.stop()
    assert r.error is not None
    assert audio.size == 0


def test_stop_survives_a_stream_whose_status_cannot_be_read(portaudio):
    # stop() promises never to raise, but the "is this stream still running?"
    # check is a PortAudio call and can come back as a PortAudioError. The
    # stream must still be closed - an unreadable status is no reason to keep
    # the microphone - and the failure must be reported, not swallowed.
    portaudio.stream_class = UnreadableStatusStream
    r = Recorder(device=None)
    r.start()
    stream = portaudio.last_stream
    audio = r.stop()  # must not raise
    assert stream.closed
    assert r.error is not None, "a status check that failed was swallowed"
    assert audio.dtype == np.float32
    assert audio.size == 0


def test_open_failures_of_any_kind_are_reported(portaudio):
    # Not just PortAudioError: whatever the driver raises while opening the
    # microphone has to land in `error`.
    for failure in (sounddevice.PortAudioError("no device"),
                    OSError("driver is on fire"),
                    RuntimeError("something else entirely")):
        portaudio.open_error = failure
        r = Recorder(device=None)
        r.start()  # must not raise
        assert r.error is not None, f"{failure!r} was swallowed"
        assert r.stop().size == 0


def test_a_failing_stream_start_is_reported(portaudio):
    # The stream can open and still refuse to run (device busy, endpoint gone).
    # The device must not stay held by a stream the recorder gave up on.
    portaudio.start_error = sounddevice.PortAudioError("device busy")
    r = Recorder(device=None)
    r.start()
    assert r.error is not None
    assert portaudio.last_stream.closed
    assert r.stop().size == 0


def test_the_stream_is_closed_even_when_the_recording_failed(portaudio):
    r = Recorder(device=None)
    r.start()
    stream = portaudio.last_stream
    stream.active = False
    r.stop()
    assert stream.closed


# --- recorder lifecycle ------------------------------------------------------

def test_start_starts_the_stream_it_opened(portaudio):
    # sounddevice creates a stream stopped: opening it captures nothing until
    # start() is called, so a recorder that only opens would silently record
    # silence forever.
    r = Recorder(device=None)
    r.start()
    assert portaudio.last_stream.active is True
    assert r.error is None


def test_start_twice_opens_only_one_stream(portaudio):
    r = Recorder(device=None)
    r.start()
    r.start()
    assert len(portaudio.streams) == 1
    assert r.error is None


def test_a_failed_start_can_be_retried(portaudio):
    # Replugging the microphone and holding the button again has to work, so a
    # new attempt starts from a clean error. The retry has to happen on the *same*
    # recorder: only then does it reach start()'s reset of a previous error,
    # and a second instance would start out clean no matter what it does.
    r = Recorder(device=None)
    portaudio.open_error = sounddevice.PortAudioError("unplugged")
    r.start()
    assert r.error is not None

    portaudio.open_error = None  # the microphone is plugged in again
    r.start()
    assert r.error is None, "a failed attempt must not condemn the next one"

    # The retried recording is judged on its own: with the error left over,
    # stop() would throw the good audio away as if this attempt had failed too.
    portaudio.last_stream.feed(_block(160))
    assert r.stop().size == 160


def test_start_clears_the_audio_of_a_previous_recording(portaudio):
    # Two utterances in a row must not be concatenated into one.
    r = Recorder(device=None)
    r.start()
    portaudio.last_stream.feed(_block(160))
    r.stop()

    r.start()
    portaudio.last_stream.feed(_block(80))
    assert r.stop().size == 80


def test_stop_can_be_called_twice(portaudio):
    r = Recorder(device=None)
    r.start()
    portaudio.last_stream.feed(_block(160))
    assert r.stop().size == 160
    assert r.stop().size == 0
    assert r.error is None


# --- pick_device -------------------------------------------------------------

# An output-only device in front of the microphone: the indices the caller sees
# are PortAudio's, so filtering must not renumber them.
MIXED_DEVICES = [
    {"name": "Speakers (Realtek Audio)", "max_input_channels": 0},
    {"name": "Mikrofon (JBL Quantum350 Wireless)", "max_input_channels": 1},
]


def test_index_spec_addresses_the_original_device_list():
    assert pick_device(MIXED_DEVICES, "0") is None, "index 0 is output-only"
    assert pick_device(MIXED_DEVICES, "1") == 1


def test_index_spec_rejects_an_output_only_device():
    assert pick_device(DEVICES, "2") is None


def test_index_spec_outside_the_device_list_returns_none():
    assert pick_device(DEVICES, "3") is None
    assert pick_device(DEVICES, "99999") is None


@pytest.mark.parametrize("spec", ["\u00b2", "\u00b9", "\u2070", "\u2153"])
def test_index_spec_never_raises_on_unexpected_digit_characters(spec):
    # str.isdigit() is true for characters int() rejects (superscripts, vulgar
    # fractions), and the spec comes from a hand-edited config file.
    assert pick_device(DEVICES, spec) is None


def test_unicode_decimal_digits_convert_like_ascii_ones():
    assert pick_device(DEVICES, "\u0661") == 1  # Arabic-Indic digit one


def test_device_without_input_channels_is_not_selectable():
    assert pick_device([{"name": "Loop"}], "loop") is None
    assert pick_device([{"name": "Loop", "max_input_channels": None}], "loop") is None


def test_spec_is_stripped_before_matching():
    assert pick_device(DEVICES, "  audient  ") == 1
    assert pick_device(DEVICES, "   ") is None


def test_first_matching_device_wins():
    both = [
        {"name": "Audient One", "max_input_channels": 1},
        {"name": "Audient Two", "max_input_channels": 1},
    ]
    assert pick_device(both, "audient") == 0


# --- file convention ---------------------------------------------------------

@pytest.mark.parametrize("path", [recorder.__file__, __file__])
def test_source_file_uses_lf_endings_and_ends_with_a_newline(path):
    # Project convention for every committed source file: LF endings, no BOM,
    # and a final newline, so diffs and POSIX tooling stay sane.
    raw = Path(path).read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "file starts with a BOM"
    assert b"\r\n" not in raw, "file contains CRLF line endings"
    assert raw.endswith(b"\n"), "file does not end with a newline"
