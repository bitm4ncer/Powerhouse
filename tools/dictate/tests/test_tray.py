"""Tests for the tray icon.

The three tests the brief specifies verbatim come first. The rest pin the
constraints the brief states in prose but never tests: the exact colours and
menu labels it names, that the icon is *drawn* and no image file is committed,
that the module does not depend on the configuration file, and - most of all -
that no test here needs a real notification area.

Every value the brief fixes is declared below in ``_EXPECTED_*`` tables instead
of being read back from tray.py. Reading them back would let a wrong colour
satisfy its own assertion: painting "recording" in the grey of "error" would
leave the tray indistinguishable from a broken one, and the tests would pass.
"""

import ast
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import tray
from tray import STATES, Tray, make_icon, state_color

# --- the values the brief fixes, declared here and not read from tray.py ------

_EXPECTED_STATES = ("ready", "recording", "transcribing", "error")

# state -> RGB, exactly as the brief spells them out.
_EXPECTED_COLORS = {
    "ready": (46, 160, 67),
    "recording": (215, 58, 73),
    "transcribing": (219, 154, 4),
    "error": (120, 120, 120),
}

# The tooltip of every state. The brief does not name these; they are pinned
# here anyway so changing one has to be a deliberate act - and so every state is
# told apart by words as well as by colour.
_EXPECTED_TITLES = {
    "ready": "dictate - bereit",
    "recording": "dictate - nimmt auf",
    "transcribing": "dictate - schreibt mit",
    "error": "dictate - Fehler",
}

# (label, callback name) in the order the menu shows them.
_EXPECTED_MENU = (
    ("Mikrofon wählen", "on_select_mic"),
    ("Wörterbuch neu laden", "on_reload"),
    ("Config öffnen", "on_open_config"),
    ("Beenden", "on_quit"),
)

_CALLBACK_NAMES = ("on_quit", "on_reload", "on_select_mic", "on_open_config")

_IMAGE_SUFFIXES = {".bmp", ".gif", ".ico", ".icns", ".jpeg", ".jpg", ".png", ".webp"}

_CENTER = (32, 32)  # the middle of a 64x64 icon


# --- the tests the brief specifies -------------------------------------------

def test_all_states_have_a_distinct_color():
    colors = [state_color(s) for s in STATES]
    assert len(set(colors)) == len(STATES)


def test_unknown_state_raises():
    with pytest.raises(ValueError):
        state_color("unsinn")


def test_make_icon_is_64x64_rgba():
    img = make_icon("recording")
    assert img.size == (64, 64)
    assert img.mode == "RGBA"


# --- the states and their colours --------------------------------------------

def test_the_states_are_exactly_the_four_the_brief_names():
    assert STATES == _EXPECTED_STATES


@pytest.mark.parametrize("state", _EXPECTED_STATES)
def test_each_state_has_the_colour_the_brief_fixes(state):
    assert state_color(state) == _EXPECTED_COLORS[state]


@pytest.mark.parametrize("state", _EXPECTED_STATES)
def test_every_state_has_a_title(state):
    # No state may fall through the tooltip table either: a missing one would
    # crash the tray in the middle of a recording.
    assert tray.title_for(state) == _EXPECTED_TITLES[state]


def test_every_state_has_its_own_tooltip():
    # Colour alone is not enough: Windows' own themes and colour-blind users
    # need the words as well.
    titles = [tray.title_for(state) for state in _EXPECTED_STATES]
    assert len(set(titles)) == len(_EXPECTED_STATES)


@pytest.mark.parametrize("state", ["", "READY", "Ready", None, 0, ["ready"]])
def test_anything_that_is_not_a_known_state_is_refused(state):
    # Not just a misspelling: a wrong type, a wrong case and an unhashable value
    # all have to be a ValueError, never a TypeError or a silent default.
    with pytest.raises(ValueError):
        state_color(state)


def test_the_error_names_the_state_and_lists_the_valid_ones():
    with pytest.raises(ValueError) as excinfo:
        state_color("unsinn")
    message = str(excinfo.value)
    assert "unsinn" in message
    for state in _EXPECTED_STATES:
        assert state in message


# --- the icon ----------------------------------------------------------------

@pytest.mark.parametrize("state", _EXPECTED_STATES)
def test_the_icon_is_a_disc_in_the_colour_of_its_state(state):
    assert make_icon(state).getpixel(_CENTER) == _EXPECTED_COLORS[state] + (255,)


def test_the_icons_of_two_states_are_not_the_same_picture():
    assert make_icon("ready").tobytes() != make_icon("recording").tobytes()


def test_the_corner_of_the_icon_stays_transparent():
    # The taskbar shows through around the dot; an opaque square would cover it.
    assert make_icon("ready").getpixel((0, 0))[3] == 0


def test_make_icon_refuses_an_unknown_state():
    with pytest.raises(ValueError):
        make_icon("unsinn")


def test_make_icon_returns_a_fresh_image_every_time():
    # The same image handed out twice could be repainted by whoever holds it,
    # and the icon on screen would change under the tray's feet.
    first = make_icon("ready")
    second = make_icon("ready")
    assert first is not second
    assert first.tobytes() == second.tobytes()


# --- the test doubles --------------------------------------------------------

class FakeIcon:
    """Stands in for ``pystray.Icon``.

    It keeps the two behaviours the tray depends on: ``run`` blocks until the
    icon is stopped, and ``stop`` does nothing while the message loop is not up
    yet - pystray ignores a stop that arrives before its loop is running.
    """

    def __init__(self, name, icon, title, menu):
        self.name = name
        self.icon = icon
        self.title = title
        self.menu = menu
        self.visible = False
        self.running = False
        self.stopped = False
        self.runs = 0
        self.stops = 0
        self.notifications = []
        self.ready = threading.Event()
        self._finished = threading.Event()

    def run(self, setup=None):
        self.runs += 1
        self.running = True
        if setup is not None:
            setup(self)
        self.ready.set()
        self._finished.wait(timeout=30)
        self.running = False

    def stop(self):
        self.stops += 1
        if self.running:
            self.stopped = True
            self._finished.set()

    def notify(self, message, title=None):
        self.notifications.append((message, title))


class Tripwire(Exception):
    """Raised when the tray reaches for something that needs a real desktop."""


def _tripwire(*args, **kwargs):
    raise Tripwire("the tray must not need pystray before run()")


class FakeBackend:
    """Replaces the two module-level seams that build the real pystray objects."""

    def __init__(self):
        self.icons = []
        self.menus = []

    def make_menu(self, entries):
        entries = list(entries)
        self.menus.append(entries)
        return entries

    def make_icon(self, name, icon, title, menu):
        self.icons.append(FakeIcon(name, icon, title, menu))
        return self.icons[-1]

    @property
    def icon(self):
        assert len(self.icons) == 1, f"expected one icon, got {len(self.icons)}"
        return self.icons[0]


@pytest.fixture
def backend(monkeypatch):
    """Wire :class:`Tray` to :class:`FakeIcon` instead of to pystray."""
    fake = FakeBackend()
    monkeypatch.setattr(tray, "_make_menu", fake.make_menu)
    monkeypatch.setattr(tray, "_make_icon", fake.make_icon)
    return fake


class StartedTray:
    """``Tray.run()`` on its own thread, the way the wiring layer uses it.

    The run is blocking, so a test that wants a live tray has to keep it on a
    thread too - exactly as the tool will.
    """

    def __init__(self, instance, backend):
        self.instance = instance
        self.backend = backend
        self.thread = threading.Thread(
            target=instance.run, name="dictate-tray-test", daemon=True
        )

    def __enter__(self):
        self.thread.start()
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if self.backend.icons and self.backend.icons[0].ready.wait(0.01):
                return self
        raise AssertionError("run() never brought the icon up")

    def __exit__(self, *exception):
        self.instance.stop()
        self.thread.join(timeout=10.0)
        assert not self.thread.is_alive(), "run() did not return after stop()"

    @property
    def icon(self):
        return self.backend.icon


def callbacks(**overrides):
    """The four callbacks a Tray wants, each recording that it was called.

    Overriding one replaces it, which is how a test makes a single menu action
    fail.
    """
    calls = []

    def make(name):
        def action():
            calls.append(name)
        return action

    built = {name: make(name) for name in _CALLBACK_NAMES}
    built.update(overrides)
    return built, calls


def labels(entries):
    return [label for label, _ in entries]


# --- the menu ----------------------------------------------------------------

def test_the_menu_shows_the_four_actions_the_brief_names():
    built, _ = callbacks()
    entries = Tray(**built).menu_entries()
    assert labels(entries) == [label for label, _ in _EXPECTED_MENU]


def test_each_menu_entry_calls_its_own_callback():
    # The label tells the user what happens; the callback is what actually
    # happens. Crossing the two wires "Beenden" to the dictionary reload.
    built, calls = callbacks()
    entries = Tray(**built).menu_entries()
    assert len(entries) == len(_EXPECTED_MENU)
    for _label, action in entries:
        action()
    assert calls == [name for _label, name in _EXPECTED_MENU]


def test_a_menu_action_ignores_the_arguments_pystray_passes():
    # pystray invokes a menu action with the icon and the menu item. The four
    # callbacks this class is built with take no arguments, so the action has to
    # swallow both instead of passing them on - otherwise every menu click ends
    # in a TypeError.
    built, calls = callbacks()
    instance = Tray(**built)
    for _label, action in instance.menu_entries():
        action(object(), object())
    assert calls == [name for _label, name in _EXPECTED_MENU]
    assert instance.error is None


def test_a_failing_menu_action_does_not_take_the_tray_down(backend):
    # pystray runs menu actions on the icon thread: an exception escaping there
    # takes the icon with it, and the tool goes on dictating with no sign of life
    # in the notification area - the one failure this module exists to prevent.
    def boom():
        raise RuntimeError("no microphone")

    built, _ = callbacks(on_select_mic=boom)
    instance = Tray(**built)
    with StartedTray(instance, backend):
        entry = dict(instance.menu_entries())["Mikrofon wählen"]
        entry()
        assert backend.icon.stopped is False
        assert "no microphone" in instance.error
        assert backend.icon.icon.getpixel(_CENTER) == _EXPECTED_COLORS["error"] + (255,)


# --- lifecycle ---------------------------------------------------------------

def test_a_new_tray_starts_out_ready():
    built, _ = callbacks()
    assert Tray(**built).state == "ready"


def test_running_shows_the_icon_with_the_current_state(backend):
    built, _ = callbacks()
    instance = Tray(**built)
    with StartedTray(instance, backend) as started:
        assert started.icon.visible is True
        assert started.icon.name == "dictate"
        assert started.icon.icon.getpixel(_CENTER) == _EXPECTED_COLORS["ready"] + (255,)
        assert started.icon.title == _EXPECTED_TITLES["ready"]


def test_running_builds_the_menu_from_the_entries(backend):
    built, _ = callbacks()
    instance = Tray(**built)
    with StartedTray(instance, backend):
        assert len(backend.menus) == 1
        assert labels(backend.menus[0]) == labels(instance.menu_entries())


def test_a_state_set_before_running_is_the_one_that_appears(backend):
    # The tool can find out it is in trouble before the tray is ever shown; an
    # error state set then must not be lost.
    built, _ = callbacks()
    instance = Tray(**built)
    instance.set_state("transcribing")
    with StartedTray(instance, backend) as started:
        pixel = started.icon.icon.getpixel(_CENTER)
    assert pixel == _EXPECTED_COLORS["transcribing"] + (255,)


def test_set_state_repaints_the_icon_and_the_tooltip(backend):
    built, _ = callbacks()
    instance = Tray(**built)
    with StartedTray(instance, backend) as started:
        instance.set_state("error")
        assert started.icon.icon.getpixel(_CENTER) == _EXPECTED_COLORS["error"] + (255,)
        assert started.icon.title == _EXPECTED_TITLES["error"]
    assert instance.state == "error"


def test_set_state_refuses_an_unknown_state(backend):
    built, _ = callbacks()
    instance = Tray(**built)
    with StartedTray(instance, backend) as started:
        with pytest.raises(ValueError):
            instance.set_state("unsinn")
        assert instance.state == "ready"
        pixel = started.icon.icon.getpixel(_CENTER)
    assert pixel == _EXPECTED_COLORS["ready"] + (255,)


def test_stopping_a_running_tray_stops_the_icon(backend):
    # StartedTray.__exit__ stops it and asserts that run() came back.
    built, _ = callbacks()
    instance = Tray(**built)
    with StartedTray(instance, backend) as started:
        assert started.icon.stopped is False
    assert backend.icon.stopped is True


def test_stopping_twice_is_harmless(backend):
    built, _ = callbacks()
    instance = Tray(**built)
    with StartedTray(instance, backend):
        instance.stop()
        instance.stop()
        assert backend.icon.stopped is True


def test_a_stop_before_running_shows_nothing_at_all(backend):
    # Quitting while the tool is still starting up must not leave an icon behind
    # that nothing will ever take down again.
    built, _ = callbacks()
    instance = Tray(**built)
    instance.stop()
    instance.run()
    assert backend.icons == []


def test_running_twice_shows_one_icon(backend):
    built, _ = callbacks()
    instance = Tray(**built)
    with StartedTray(instance, backend):
        instance.run()  # must return at once: no second icon, no second loop
        assert len(backend.icons) == 1


def test_a_stop_that_lands_while_the_icon_is_built_never_starts_it(backend, monkeypatch):
    # The window between run() deciding to show an icon and the icon existing.
    # An icon started after that stop would be a tray icon with nothing left to
    # take it down - the tool quit, and the dot stays forever.
    built, _ = callbacks()
    instance = Tray(**built)
    make_icon = backend.make_icon

    def stop_while_building(name, icon, title, menu):
        instance.stop()
        return make_icon(name, icon, title, menu)

    monkeypatch.setattr(tray, "_make_icon", stop_while_building)
    instance.run()
    assert backend.icon.runs == 0, "the icon was started although a stop was pending"
    assert backend.icon.stopped is False


def test_a_stop_during_start_up_does_not_strand_the_icon(backend, monkeypatch):
    # The race: stop() lands after the icon object exists but before its message
    # loop does, so pystray drops it on the floor - the icon would then run
    # forever with nothing left to stop it.
    built, _ = callbacks()
    instance = Tray(**built)
    make_icon = backend.make_icon

    def stop_before_the_loop_starts(name, icon, title, menu):
        fake = make_icon(name, icon, title, menu)
        loop = fake.run

        def stop_then_run(setup=None):
            instance.stop()
            return loop(setup)

        fake.run = stop_then_run
        return fake

    monkeypatch.setattr(tray, "_make_icon", stop_before_the_loop_starts)
    instance.run()
    assert backend.icon.stopped is True


# --- notifications -----------------------------------------------------------

def test_notify_shows_the_message_next_to_the_icon(backend):
    built, _ = callbacks()
    instance = Tray(**built)
    with StartedTray(instance, backend) as started:
        instance.notify("Transkription fehlgeschlagen")
        assert started.icon.notifications == [
            ("Transkription fehlgeschlagen", _EXPECTED_TITLES["ready"])
        ]


def test_a_notification_from_before_the_icon_exists_is_still_shown(backend):
    # "The microphone could not be opened" is exactly the kind of message the
    # tool produces while it is still starting up. Dropping it because no icon
    # exists yet would mean the user never learns why nothing happened.
    built, _ = callbacks()
    instance = Tray(**built)
    instance.notify("Kein Mikrofon gefunden")
    assert backend.icons == []
    with StartedTray(instance, backend) as started:
        assert [m for m, _ in started.icon.notifications] == ["Kein Mikrofon gefunden"]


def test_the_message_kept_from_start_up_is_shown_once(backend):
    built, _ = callbacks()
    instance = Tray(**built)
    instance.notify("Kein Mikrofon gefunden")
    with StartedTray(instance, backend) as started:
        instance.notify("Wörterbuch neu geladen")
        assert [m for m, _ in started.icon.notifications] == [
            "Kein Mikrofon gefunden",
            "Wörterbuch neu geladen",
        ]


# --- threads -----------------------------------------------------------------

def test_set_state_is_safe_from_other_threads(backend):
    # The recorder, the transcriber and the tray each live on their own thread.
    built, _ = callbacks()
    instance = Tray(**built)
    failures = []
    with StartedTray(instance, backend):
        def hammer():
            try:
                for _ in range(50):
                    for state in STATES:
                        instance.set_state(state)
            except Exception as exc:  # noqa: BLE001 - a failure IS the assertion
                failures.append(exc)

        threads = [threading.Thread(target=hammer) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
    assert failures == []
    assert not any(thread.is_alive() for thread in threads)


# --- no tray is needed to get here --------------------------------------------

def test_the_tray_works_without_any_tray(monkeypatch):
    # Construction, state, notifications and stop() have to work where there is
    # no notification area at all - which is how this suite, and any headless
    # run of it, gets to exercise the class.
    monkeypatch.setattr(tray, "_make_icon", _tripwire)
    monkeypatch.setattr(tray, "_make_menu", _tripwire)
    built, _ = callbacks()
    instance = Tray(**built)
    assert instance.state == "ready"
    instance.set_state("recording")
    assert instance.state == "recording"
    instance.notify("nothing on screen yet")
    instance.stop()


_NO_TRAY_SCRIPT = """
import sys
import types


class Tripwire(types.ModuleType):
    \"\"\"Any use of pystray at all fails: the module must not need it.\"\"\"

    def __getattr__(self, name):
        raise AssertionError("tray touched pystray." + name)


sys.path.insert(0, sys.argv[1])
sys.modules["pystray"] = Tripwire("pystray")

import tray

box = tray.Tray(on_quit=lambda: None, on_reload=lambda: None,
                on_select_mic=lambda: None, on_open_config=lambda: None)
box.set_state("error")
box.notify("no notification area here")
box.menu_entries()

try:
    box.run()
except AssertionError as exc:
    # run() is the one call that needs pystray, and therefore the one call a
    # headless environment cannot serve - everything above it has to work.
    assert "pystray" in str(exc), repr(exc)
else:
    raise AssertionError("run() built something without asking pystray")

box.stop()
print("ONLY_RUN_NEEDS_PYSTRAY")
"""


def test_importing_and_using_the_module_never_needs_pystray():
    # Fresh interpreter with a pystray that explodes on contact: importing tray
    # and driving a Tray has to work anyway, because the real icon is built
    # only inside run().
    root = str(Path(tray.__file__).parent)
    result = subprocess.run(
        [sys.executable, "-c", _NO_TRAY_SCRIPT, root],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ONLY_RUN_NEEDS_PYSTRAY", result.stdout


# --- module structure --------------------------------------------------------

def _module_tree():
    return ast.parse(Path(tray.__file__).read_text(encoding="utf-8"))


def _imports(tree, everywhere=False):
    """The modules tray.py imports, at module scope or anywhere."""
    nodes = ast.walk(tree) if everywhere else tree.body
    names = set()
    for node in nodes:
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_the_module_does_not_import_config():
    # Task 8 passes the settings in; reading the config here would tie the tray
    # to a file it has no business knowing about.
    assert "config" not in _imports(_module_tree())


def test_nothing_in_the_module_imports_config_either():
    # Same rule, not just at module scope: an import tucked inside a function is
    # just as much a dependency on the config file, and just as invisible to the
    # test above.
    assert "config" not in _imports(_module_tree(), everywhere=True)


def test_pystray_is_not_imported_at_module_scope():
    # The tripwire above only catches *use* of pystray: a bare `import pystray`
    # at module scope slips past it, because an entry in sys.modules is handed
    # back without any attribute lookup.
    assert "pystray" not in _imports(_module_tree())


def test_the_icon_is_drawn_and_never_read_from_a_file():
    # "No binary assets in the repo": an icon file would have to be committed,
    # reviewed as bytes and re-exported by hand. The image is drawn instead, so
    # there is nothing to open.
    called = set()
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                called.add(node.func.attr)
            elif isinstance(node.func, ast.Name):
                called.add(node.func.id)
    assert "open" not in called, "tray.py opens a file; the icon must be drawn"


def test_no_icon_file_is_committed_next_to_the_module():
    # The same constraint, checked against what is actually on disk.
    root = Path(tray.__file__).parent
    assets = sorted(
        path.name for path in root.iterdir()
        if path.suffix.lower() in _IMAGE_SUFFIXES
    )
    assert assets == [], f"binary icon assets committed in {root}: {assets}"


# --- file convention ---------------------------------------------------------

@pytest.mark.parametrize("path", [tray.__file__, __file__])
def test_source_file_uses_lf_endings_and_ends_with_a_newline(path):
    # Project convention for every committed source file: LF endings, no BOM,
    # and a final newline, so diffs and POSIX tooling stay sane.
    raw = Path(path).read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "file starts with a BOM"
    assert b"\r\n" not in raw, "file contains CRLF line endings"
    assert raw.endswith(b"\n"), "file does not end with a newline"
