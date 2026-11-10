"""Benutzername sowie Sperren, Abmelden, Neustart, Ausschalten und Server-Modus."""

import getpass
import os
import pwd
import shutil
import subprocess

from PySide6.QtCore import Property, QObject, Signal, Slot

from .runner import spawn_detached

SERVERMODE = "/usr/libexec/creative-servermode"


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

    serverChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._name = _display_name()
        self._server = False
        self.refreshServer()

    userName = Property(str, lambda self: self._name, notify=changed)
    initial = Property(str, lambda self: (self._name[:1] or "?").upper(), notify=changed)
    # Server-Modus nur anbieten, wenn „Mein Server“ eingeschaltet ist
    serverModeAvailable = Property(bool, lambda self: self._server, notify=serverChanged)

    @Slot()
    def refreshServer(self):
        ok = False
        if os.path.exists(SERVERMODE) and shutil.which("systemctl"):
            try:
                ok = subprocess.run(["systemctl", "is-enabled", "--quiet", "creative-server.service"],
                                    timeout=2).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                ok = False
        if ok != self._server:
            self._server = ok
            self.serverChanged.emit()

    @Slot()
    def serverMode(self):
        """Alles schließen, nur „Mein Server“ bleibt online. Zurück über den Anmeldebildschirm."""
        session = os.environ.get("XDG_SESSION_ID")
        if session and self._server:
            spawn_detached(["pkexec", SERVERMODE, "on", session])

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
