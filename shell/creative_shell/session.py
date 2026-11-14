"""Benutzername sowie Sperren, Abmelden, Neustart, Ausschalten und Server-Modus."""

import getpass
import os
import pwd
import shutil
import subprocess
import sys

from PySide6.QtCore import Property, QObject, Signal, Slot

try:
    from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
except ImportError:  # ohne QtDBus kein „Nicht sperren“
    QDBusConnection = None

from . import avatar as profile
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
        self._avatar = ""
        self._preview = ""
        self.refreshAvatar()
        self._server = False
        self.refreshServer()
        self._awake_bus = None
        self._awake_count = 0

    userName = Property(str, lambda self: self._name, notify=changed)
    fullName = Property(str, lambda self: profile.full_name(), notify=changed)
    # Kürzel aus Vor- und Nachname („MP“); „initial“ bleibt als alter Name erhalten
    initial = Property(str, lambda self: profile.initials(), notify=changed)
    initials = Property(str, lambda self: profile.initials(), notify=changed)

    # ---- Profilbild ----------------------------------------------------------------
    avatarChanged = Signal()

    def _avatar_url(self):
        path = profile.avatar_path()
        if not path:
            return ""
        # Zeitstempel im Link, damit QML ein neues Bild nicht aus dem Cache zeigt
        return f"file://{path}?v={int(os.stat(path).st_mtime_ns)}"

    avatar = Property(str, lambda self: self._avatar, notify=avatarChanged)
    avatarPreview = Property(str, lambda self: self._preview, notify=avatarChanged)

    @Slot()
    def refreshAvatar(self):
        url = self._avatar_url()
        if url != self._avatar:
            self._avatar = url
            self.avatarChanged.emit()

    @Slot(str, result=str)
    def previewAvatar(self, url):
        """Bild wählen → runde Vorschau. Gibt einen Fehlertext zurück ("" = gut)."""
        path = url[7:] if url.startswith("file://") else url
        from urllib.parse import unquote
        result = profile.make_preview(unquote(path))
        if result.startswith("!"):
            return result[1:]
        self._preview = f"file://{result}?v={int(os.stat(result).st_mtime_ns)}"
        self.avatarChanged.emit()
        return ""

    @Slot(result=str)
    def applyAvatar(self):
        error = profile.apply_preview()
        if not error:
            self._preview = ""
            self.refreshAvatar()
            self.avatarChanged.emit()
        return error

    @Slot()
    def discardAvatar(self):
        profile.discard_preview()
        self._preview = ""
        self.avatarChanged.emit()

    @Slot()
    def removeAvatar(self):
        profile.remove_avatar()
        self._avatar = ""
        self.avatarChanged.emit()
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

    # ---- Nicht sperren (nur für diese Sitzung) --------------------------------------
    # Hält eine Sperre über org.freedesktop.ScreenSaver: keine automatische Bildschirmsperre
    # (Anmeldebildschirm), kein Abdunkeln, kein Bildschirm aus. Die Sperre hängt an einer
    # eigenen D-Bus-Verbindung – trennen gibt sie frei, und mit dem Abmelden endet sie ohnehin.
    keepAwakeChanged = Signal()

    def _set_keep_awake(self, on):
        if on == (self._awake_bus is not None) or QDBusConnection is None:
            return
        if on:
            self._awake_count += 1
            name = f"creative-wach-{self._awake_count}"
            bus = QDBusConnection.connectToBus(QDBusConnection.BusType.SessionBus, name)
            iface = QDBusInterface("org.freedesktop.ScreenSaver", "/ScreenSaver",
                                   "org.freedesktop.ScreenSaver", bus)
            reply = iface.call("Inhibit", "Creative OS", "Nicht sperren (Schnellzugriff)")
            if not bus.isConnected() or reply.type() != QDBusMessage.MessageType.ReplyMessage:
                print("Nicht sperren: ScreenSaver.Inhibit ging nicht:",
                      reply.errorName(), reply.errorMessage(), file=sys.stderr)
                QDBusConnection.disconnectFromBus(name)
                return
            self._awake_bus = name
        else:
            QDBusConnection.disconnectFromBus(self._awake_bus)
            self._awake_bus = None
        self.keepAwakeChanged.emit()

    keepAwake = Property(bool, lambda self: self._awake_bus is not None, notify=keepAwakeChanged)
    keepAwakeAvailable = Property(bool, lambda self: QDBusConnection is not None, constant=True)

    @Slot(bool)
    def setKeepAwake(self, on):
        self._set_keep_awake(bool(on))

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
