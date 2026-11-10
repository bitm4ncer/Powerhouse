"""The tray icon: the always-visible sign of what dictate is doing.

A push-to-talk tool is quiet almost all of the time and completely silent while
it works, which is exactly when the user wants to know whether their microphone
is still listening. The tray icon is that sign: one coloured dot, four states,
and a menu for the four things a user may want to do without hunting down a
console window.

Two layers, deliberately separated:

* :func:`state_color`, :func:`title_for` and :func:`make_icon` are pure. They
  turn a state name into a colour, a tooltip and a 64x64 RGBA image, and they
  need no tray, no desktop and not even pystray.
* :class:`Tray` owns the real icon: it paints the current state, repaints on
  every :meth:`Tray.set_state` and forwards the menu actions to the four
  callbacks it was built with.

The icon is drawn in code with Pillow and never loaded from a file. A committed
``.ico`` is a binary asset: unreviewable in a diff, unmergeable, and stale the
moment somebody changes a colour. Four circles cost nothing.

Example:

    from tray import Tray

    tray = Tray(on_quit=app.quit, on_reload=dictionary.reload,
                on_select_mic=mic_picker, on_open_config=open_config)
    tray.set_state("ready")
    tray.run()          # main thread; blocks until tray.stop()

:mod:`config` owns the user-facing names; this module takes plain parameters, so
nothing here depends on the configuration file.

:meth:`Tray.run` is the only place that builds a real pystray icon, and it does
so through the module-level ``_make_icon`` and ``_make_menu`` seams - which is
what lets the whole class, start-up races included, be exercised without a
notification area and without importing pystray at all.
"""

from __future__ import annotations

import functools
import threading
from typing import Callable

from PIL import Image, ImageDraw

# --- the states --------------------------------------------------------------

# The four things dictate can be doing. Every one of them has a colour and a
# tooltip; a fifth has to be added to all three tables, not just to this tuple.
STATES = ("ready", "recording", "transcribing", "error")

# The name the taskbar and the tooltip use for the tool.
APP_NAME = "dictate"

STATE_COLORS: dict[str, tuple[int, int, int]] = {
    "ready": (46, 160, 67),         # green
    "recording": (215, 58, 73),     # red
    "transcribing": (219, 154, 4),  # amber: still working, not waiting
    "error": (120, 120, 120),       # grey: not listening, and it did not work
}

# The tooltip of each state. German, because the menu is; the words matter as
# much as the colour - Windows' own themes and colour-blind users need both.
STATE_TITLES: dict[str, str] = {
    "ready": f"{APP_NAME} - bereit",
    "recording": f"{APP_NAME} - nimmt auf",
    "transcribing": f"{APP_NAME} - schreibt mit",
    "error": f"{APP_NAME} - Fehler",
}

# What the tray shows before anyone says otherwise: listening, not talking.
INITIAL_STATE = "ready"

# The drawn icon. 64x64 is what the Windows shell wants; Windows scales it down
# to the notification area itself.
ICON_SIZE = 64
ICON_MARGIN = 4

# The tray menu, in the order it is shown: the label the user reads, and the name
# of the callback that is run. Kept as data rather than as pystray objects so the
# labels and the wiring can be inspected without a notification area.
MENU_ITEMS = (
    ("Mikrofon wählen", "on_select_mic"),
    ("Wörterbuch neu laden", "on_reload"),
    ("Config öffnen", "on_open_config"),
    ("Beenden", "on_quit"),
)


# --- the pure layer ----------------------------------------------------------

def _check_state(state: str) -> None:
    """Refuse anything that is not one of :data:`STATES`.

    The ``isinstance`` test is what turns a wrong *type* into this error as well:
    a list is unhashable and would raise TypeError out of a plain dict lookup,
    and a caller that passed the wrong thing deserves to be told what it should
    have passed.
    """
    if not isinstance(state, str) or state not in STATE_COLORS:
        raise ValueError(
            f"Unknown tray state: {state!r}. "
            f"Allowed values: {', '.join(STATES)}"
        )


def state_color(state: str) -> tuple[int, int, int]:
    """The RGB the icon is drawn in for ``state``.

    Raises ``ValueError`` for anything that is not one of :data:`STATES`. A
    caller that asks for a state the tray cannot show finds out here, not in the
    middle of a recording with a microphone open.
    """
    _check_state(state)
    return STATE_COLORS[state]


def title_for(state: str) -> str:
    """The tooltip text for ``state``. Raises ``ValueError`` like :func:`state_color`."""
    _check_state(state)
    return STATE_TITLES[state]


def _shade(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    """The same colour, darker - used for the ring around the dot.

    A dot with no edge disappears into a light taskbar; the ring keeps it a shape
    on any background.
    """
    return tuple(max(0, min(255, round(channel * factor))) for channel in color)


def make_icon(state: str) -> Image.Image:
    """Draw the 64x64 RGBA icon for ``state`` and return it.

    A filled circle in the state's colour on a transparent background, drawn
    here rather than loaded from an ``.ico``: see the module docstring. The image
    is new every call, so the caller may keep and repaint it.
    """
    color = state_color(state)  # validated before a single pixel is drawn
    image = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse(
        (
            ICON_MARGIN,
            ICON_MARGIN,
            ICON_SIZE - ICON_MARGIN - 1,
            ICON_SIZE - ICON_MARGIN - 1,
        ),
        fill=(*color, 255),
        outline=(*_shade(color, 0.55), 255),
        width=2,
    )
    return image


# --- the pystray seams -------------------------------------------------------

# pystray is imported inside these two functions rather than at module scope: a
# test - or anything else that only wants the colours - must be able to import
# this module and build a Tray without pulling in the Win32 shell backend at all.
# They are also the only two places pystray objects are created, which is what
# lets the test suite replace them.


def _make_menu(entries: list[tuple[str, Callable[[], None]]]):
    """Build the real pystray menu from ``(label, action)`` pairs."""
    import pystray

    return pystray.Menu(
        *(pystray.MenuItem(label, action) for label, action in entries)
    )


def _make_icon(name: str, image: Image.Image, title: str, menu):
    """Build the real pystray icon - the one place that needs a desktop."""
    import pystray

    return pystray.Icon(name, image, title, menu)


# --- the tray ----------------------------------------------------------------

class Tray:
    """The notification-area icon that shows what dictate is doing.

    Built from the four callbacks the menu needs: :meth:`run` shows the icon, the
    menu offers the four actions in :data:`MENU_ITEMS`, and each of those runs the
    callback it is wired to.

    The state is set with :meth:`set_state` from anywhere - the recorder, the
    transcriber and the wiring layer each have their own thread - and the icon
    is repainted from whichever of them gets there first.

    :meth:`run` is blocking: it runs the icon's message loop on the calling
    thread and returns when :meth:`stop` was called. pystray wants that call on
    the main thread, so the tray is the application's main loop - the mouse hook,
    the recorder and the transcriber each get a thread of their own, and
    :meth:`stop`, from any of them, is what brings it down again. :meth:`stop` is
    also safe before :meth:`run`, twice, and while the icon is still starting up.

    Nothing on the surface of this class needs a notification area except
    :meth:`run` itself, which is why the test suite can drive all of it.

    Example:

        tray = Tray(on_quit=app.quit, on_reload=dictionary.reload,
                    on_select_mic=mic_picker, on_open_config=open_config)
        tray.run()      # the main thread's job; it returns when stop() is called
        # the hook thread reports through tray.set_state(), and the quitting
        # button calls tray.stop() from wherever it likes

    A menu action that raises does not take the icon down with it: pystray runs
    menu actions on the icon thread, and the icon going silent is the one failure
    this module exists to prevent. The first failure is recorded in
    :attr:`error` and the dot turns grey, like every other failure.
    """

    def __init__(
        self,
        on_quit: Callable[[], None],
        on_reload: Callable[[], None],
        on_select_mic: Callable[[], None],
        on_open_config: Callable[[], None],
    ) -> None:
        self.error: str | None = None
        self._actions = {
            "on_quit": on_quit,
            "on_reload": on_reload,
            "on_select_mic": on_select_mic,
            "on_open_config": on_open_config,
        }
        self._state = INITIAL_STATE
        self._pending_message: str | None = None
        self._icon = None
        self._started = False
        # The state, the icon and the pending message are shared between the
        # thread that runs the icon and every thread that reports a state.
        self._lock = threading.Lock()
        self._stopped = threading.Event()

    @property
    def state(self) -> str:
        """The state the tray is currently in."""
        return self._state

    # --- what the user can see ------------------------------------------------

    def menu_entries(self) -> list[tuple[str, Callable[[], None]]]:
        """The menu as ``(label, action)`` pairs, in the order it is shown.

        The actions take no arguments - pystray calls a menu action with the icon
        and the menu item, and both are dropped - so the callbacks this class was
        built with can be plain ``def f(): ...``. Free of pystray as well, so the
        labels and the wiring can be inspected - and called - without a
        notification area. :meth:`run` turns them into the real menu.
        """
        return [
            (label, self._guard(label, self._actions[name]))
            for label, name in MENU_ITEMS
        ]

    def set_state(self, state: str) -> None:
        """Show ``state``: repaint the dot and its tooltip.

        Safe to call from any thread, and safe to call before :meth:`run`: a
        state set before the icon exists is the one that appears when it does,
        because the tool can fail before it has finished starting up.

        Raises ``ValueError`` for a state that is not in :data:`STATES`, without
        changing anything.
        """
        title = title_for(state)  # raises before the state is touched
        with self._lock:
            self._state = state
            icon = self._icon
        if icon is None:
            return  # nothing on screen; run() paints the state that is current
        icon.icon = make_icon(state)
        icon.title = title

    def notify(self, message: str) -> None:
        """Show ``message`` as a notification next to the icon.

        A notification that arrives before the icon exists is not lost: the last
        one is kept and shown as soon as the icon is up. "The microphone could
        not be opened" is exactly what a user sees while the tool is still
        starting up, and it is not something to drop on the floor.
        """
        with self._lock:
            icon = self._icon
            if icon is None:
                self._pending_message = message
                return
            title = title_for(self._state)
        icon.notify(message, title)

    # --- lifecycle ------------------------------------------------------------

    def run(self) -> None:
        """Show the tray icon and run its message loop until :meth:`stop`.

        Blocking, like pystray's own ``run``: this call returns only once the
        icon has been stopped, and pystray wants it on the main thread, so it is
        the application's main loop. Calling it a second time does nothing at
        all - one Tray is one icon, and a second loop would fight the first over
        the same menu.
        """
        with self._lock:
            if self._started:
                return
            self._started = True
            state = self._state
        if self._stopped.is_set():
            # stop() arrived before there was anything to show.
            return
        icon = _make_icon(
            APP_NAME, make_icon(state), title_for(state),
            _make_menu(self.menu_entries()),
        )
        with self._lock:
            if self._stopped.is_set():
                # stop() landed while the icon was being built. Nothing has been
                # shown yet, so there is nothing to take down.
                return
            self._icon = icon
        try:
            icon.run(setup=self._when_ready)
        finally:
            with self._lock:
                self._icon = None

    def stop(self) -> None:
        """Ask the message loop to end, and return :meth:`run`.

        Safe from any thread - that is the point, since the menu, the hook and
        the transcriber all live somewhere else - and safe to call twice, before
        :meth:`run` or while it is still starting up.

        pystray drops a stop that arrives before its loop is running, so
        :meth:`run` re-checks the flag once the loop is up - see
        :meth:`_when_ready`.
        """
        self._stopped.set()
        with self._lock:
            icon = self._icon
        if icon is None:
            return  # never started, or already stopped
        icon.stop()

    # --- internals ------------------------------------------------------------

    def _when_ready(self, icon) -> None:
        """Show the icon. Runs on pystray's setup thread, once the loop is up.

        This is also where a stop that arrived too early is caught: pystray's
        ``stop`` is a no-op until its loop is running, so a stop landing between
        the icon being built and the loop starting would leave an icon nothing
        will ever take down again.
        """
        if self._stopped.is_set():
            icon.stop()
            return
        icon.visible = True
        with self._lock:
            message, self._pending_message = self._pending_message, None
        if message is not None:
            icon.notify(message, icon.title)

    def _guard(self, label: str, callback: Callable[[], None]) -> Callable[[], None]:
        """Wrap one menu action so a failure cannot take the icon down.

        Two jobs in one wrapper. pystray calls a menu action with the icon and
        the menu item; the callbacks dictate hands this module take no arguments
        at all, so both are dropped here rather than at every callback. And an
        exception escaping the icon thread ends the tool's only sign of life, so
        it is caught, recorded in :attr:`error` and turned into the grey
        ``error`` dot - the user can see that something went wrong, and the menu
        is still there to retry it.
        """

        @functools.wraps(callback)
        def action(*args, **kwargs):
            try:
                return callback()
            except Exception as exc:
                if self.error is None:
                    self.error = f"{label} failed: {exc}"
                self.set_state("error")

        return action
