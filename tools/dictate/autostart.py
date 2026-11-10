"""Windows autostart for dictate: one hidden launcher in the Startup folder.

Starting a tool by hand is the first thing everybody does and the first thing
everybody forgets. This module puts dictate into the Startup folder so it is
listening when the machine is, and takes it back out again.

The launcher is a ``.vbs`` file, not a shortcut or a registry entry, and that is
the whole trick:

* ``pythonw.exe`` has no console. Run under wscript with the window style 0,
  dictate starts with nothing on screen - no black rectangle behind the tray
  icon, no window to click away.
* Writing one small text file is reviewable. A registry value or a binary
  ``.lnk`` is not, and the thing that runs at every logon is exactly the thing
  that should be readable.

Example:

    from autostart import install_autostart, uninstall_autostart
    from pathlib import Path

    launcher = install_autostart(Path("tools/dictate/dictate.py").resolve())
    ...
    uninstall_autostart()

The Startup folder is reached through ``%APPDATA%``, which is the same folder
``shell:startup`` opens. :func:`startup_folder` and :func:`pythonw_for` are the
two seams the test suite replaces: nothing here touches the real Startup
folder or the real interpreter.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# The file the Startup folder gets. It is one launcher for one tool, so the
# name is fixed rather than derived from the script: reinstalling overwrites it
# and uninstalling removes it without having to know what was installed.
LAUNCHER_NAME = "dictate.vbs"

# ``shell:startup`` is this folder. %APPDATA% is the roaming application data
# of the user who is logged in, which is exactly where the shell looks.
_STARTUP_SUBFOLDERS = (
    "Microsoft", "Windows", "Start Menu", "Programs", "Startup"
)

# The one line that has to work. {command} is the quoted interpreter and script;
# 0 is the hidden window style and False means "do not wait for it to finish".
VBS_TEMPLATE = 'CreateObject("WScript.Shell").Run "{command}", 0, False'


def launcher_body(command: str) -> str:
    """Return the launcher source that runs ``command`` hidden.

    The command is a Windows command line, so it is full of double quotes - and
    inside a VBScript string literal a double quote is written twice. Every
    quote in ``command`` is doubled on the way in.

    That is not decoration. A launcher written with the raw command does not
    compile: the parser reads the command's own quotes as the end of the string
    and the rest of the line as source, so the tool never starts at logon and
    says nothing about it. ``cscript.exe`` reports the difference directly::

        CreateObject("WScript.Shell").Run ""C:\\v\\pythonw.exe" "C:\\t\\dictate.py"", 0, False
        ... Microsoft VBScript compilation error: Expected end of statement

    The escaped form compiles and runs; ``tests/test_wiring.py`` compiles the
    generated launcher with the real cscript.exe to keep it that way.
    """
    return VBS_TEMPLATE.replace("{command}", command.replace('"', '""'))


def autostart_command(pythonw: Path, script: Path) -> str:
    """Return the command line the launcher runs: ``"<pythonw>" "<script>"``.

    Both paths are quoted. The venv lives under
    ``C:\\Users\\<name>\\AppData\\...``, and an unquoted path with a space in it
    would run whatever came before the space - silently, on every logon.
    """
    return f'"{Path(pythonw)}" "{Path(script)}"'


def pythonw_for(python: Path) -> Path:
    """Return the console-less interpreter that belongs next to ``python``.

    ``python.exe`` and ``pythonw.exe`` ship as a pair in one Scripts folder.
    Swapping the name keeps the entry pointing at *this* environment - a
    pythonw.exe from somewhere else would load another interpreter's packages.
    """
    return Path(python).with_name("pythonw.exe")


def startup_folder() -> Path:
    """Return this user's Startup folder, the one ``shell:startup`` opens.

    ``%APPDATA%`` is read from the environment rather than from a registry key,
    so it is the same for the user running the installer and for the shell that
    runs the launcher. When it is not set at all - a stripped service account,
    an unusual sandbox - the default location under the profile is used, which
    is where the shell looks for those users too.
    """
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = str(Path.home() / "AppData" / "Roaming")
    return Path(appdata).joinpath(*_STARTUP_SUBFOLDERS)


def install_autostart(script: Path) -> Path:
    """Write the hidden launcher for ``script`` into the Startup folder.

    ``script`` is the path of ``dictate.py`` itself; the interpreter is the one
    that is running this. Returns the launcher that was written. Installing
    twice writes the same file with the same content, so a second call is
    harmless and can be used to repair a hand-edited launcher.
    """
    command = autostart_command(pythonw_for(Path(sys.executable)), Path(script))
    folder = startup_folder()
    folder.mkdir(parents=True, exist_ok=True)
    launcher = folder / LAUNCHER_NAME
    # utf-8, and LF: wscript does not care, a diff of the file does.
    launcher.write_text(launcher_body(command), encoding="utf-8", newline="\n")
    return launcher


def uninstall_autostart() -> None:
    """Remove the launcher, if it is there.

    Uninstalling twice is not an error: the point of this function is that the
    launcher is gone afterwards, whether or not it ever was there.
    """
    launcher = startup_folder() / LAUNCHER_NAME
    try:
        launcher.unlink()
    except FileNotFoundError:
        pass
