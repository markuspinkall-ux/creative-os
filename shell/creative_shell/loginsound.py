"""Anmelde-Ton: spielt einmal pro Sitzung den Klang „desktop-login“, sobald der
Desktop erscheint – das Gegenstück zum Abmelde-Ton „desktop-logout“ von KDE.

Abschaltbar in den Einstellungen → Ton („Ton beim Anmelden“, Schlüssel loginSound).
"""

import os
import shutil
from pathlib import Path

from . import config
from .runner import spawn_detached

# Gleiches Klangthema wie der Abmelde-Ton zuerst (KDE „ocean“), dann freedesktop
CANDIDATES = [
    "/usr/share/sounds/ocean/stereo/desktop-login.oga",
    "/usr/share/sounds/freedesktop/stereo/desktop-login.oga",
    "/usr/share/sounds/freedesktop/stereo/service-login.oga",
]


def sound_file(candidates=CANDIDATES):
    return next((path for path in candidates if os.path.isfile(path)), "")


def player():
    for name in ("pw-play", "paplay", "canberra-gtk-play"):
        if shutil.which(name):
            return name
    return ""


def marker():
    """Pro Sitzung nur einmal – auch wenn die Shell neu startet (z. B. nach einem Absturz)."""
    runtime = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    session = os.environ.get("XDG_SESSION_ID") or str(os.getppid())
    return Path(runtime) / f"creative-login-sound-{session}"


def play_login_sound():
    if not config.load().get("loginSound", True):
        return False
    flag = marker()
    if flag.exists():
        return False
    path, program = sound_file(), player()
    if not path or not program:
        return False
    try:
        flag.touch()
    except OSError:
        pass
    args = [program, "-f", path] if program == "canberra-gtk-play" else [program, path]
    return bool(spawn_detached(args))
