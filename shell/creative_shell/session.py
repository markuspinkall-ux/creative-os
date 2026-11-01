"""Benutzername sowie Sperren, Abmelden, Neustart und Ausschalten."""

import getpass
import os
import pwd

from PySide6.QtCore import Property, QObject, Signal, Slot

from .runner import spawn_detached


def _display_name():
    try:
        gecos = pwd.getpwuid(os.getuid()).pw_gecos.split(",")[0].strip()
        if gecos:
            return gecos.split()[0]
    except KeyError:
        pass
    return getpass.getuser()


class SessionModel(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._name = _display_name()

    userName = Property(str, lambda self: self._name, notify=changed)
    initial = Property(str, lambda self: (self._name[:1] or "?").upper(), notify=changed)

    @Slot()
    def lock(self):
        # Bildschirmsperre von KWin (Graphit-Sperrbildschirm), sonst über logind
        spawn_detached(["sh", "-c",
                        "gdbus call --session --dest org.freedesktop.ScreenSaver "
                        "--object-path /ScreenSaver --method org.freedesktop.ScreenSaver.Lock "
                        ">/dev/null 2>&1 || loginctl lock-session"])

    @Slot()
    def logout(self):
        session = os.environ.get("XDG_SESSION_ID")
        if session:
            spawn_detached(["loginctl", "terminate-session", session])

    @Slot()
    def suspend(self):
        spawn_detached(["systemctl", "suspend"])

    @Slot()
    def reboot(self):
        spawn_detached(["systemctl", "reboot"])

    @Slot()
    def poweroff(self):
        spawn_detached(["systemctl", "poweroff"])

    @Slot()
    def openSettings(self):
        if not spawn_detached(["creative-settings"]):
            spawn_detached(["systemsettings"])
