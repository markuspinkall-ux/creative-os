"""Updates für die AppImage-Fassung von Studio (andere Linux-Systeme).

In Gibeon OS kommt Studio mit den System-Updates – dort ist das hier aus. Im AppImage fragt Studio
beim Start im Release „appimages“ nach studio.json. Gibt es eine neuere Version, zeigt Studio oben
eine Leiste; „Jetzt aktualisieren“ lädt das neue AppImage (Studio und Broadcast stecken zusammen
darin), ersetzt die Datei und startet neu. Einstellungen und Szenen bleiben, die liegen in ~/.config."""

import json
import os
import shutil
import subprocess
import threading
import urllib.request
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication

INFO_URL = "https://github.com/markuspinkall-ux/creative-os/releases/download/appimages/studio.json"


def _version_tuple(text):
    out = []
    for part in str(text).split("."):
        out.append(int(part) if part.isdigit() else 0)
    return tuple(out)


def installed_version():
    prefix = Path(os.environ.get("GIBEON_PREFIX") or "/usr")
    try:
        return json.loads((prefix / "share/gibeon-appimage/version.json").read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return ""


class AppUpdate(QObject):
    changed = Signal()
    _done = Signal(str, str)            # Art, JSON

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = os.environ.get("APPIMAGE", "")
        self.enabled = os.environ.get("GIBEON_APPIMAGE") == "studio" and bool(self.image)
        self.current = installed_version()
        self.info = {}
        self.state = ""                 # "" | available | loading | ready | error
        self.progress = 0.0
        self.error = ""
        self.dismissed = False
        self._done.connect(self._finish)

    # ---- Nachsehen -------------------------------------------------------------------------------
    @Slot()
    def check(self):
        if not self.enabled or self.state in ("loading", "ready"):
            return

        def work():
            try:
                with urllib.request.urlopen(INFO_URL, timeout=10) as r:
                    data = json.loads(r.read(200_000))
                self._done.emit("info", json.dumps(data))
            except Exception as exc:               # offline o. Ä.: einfach keine Leiste
                self._done.emit("noinfo", json.dumps(str(exc)))
        threading.Thread(target=work, daemon=True).start()

    # ---- Laden und ersetzen --------------------------------------------------------------------
    @Slot()
    def start(self):
        if self.state != "available":
            return
        self.state, self.progress, self.error = "loading", 0.0, ""
        self.changed.emit()
        url, size = self.info.get("url", ""), int(self.info.get("size") or 0)
        target = Path(self.image)
        part = target.with_name(target.name + ".neu")

        def work():
            try:
                with urllib.request.urlopen(url, timeout=30) as r, open(part, "wb") as f:
                    total = int(r.headers.get("Content-Length") or size or 0)
                    got = 0
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                        if total:
                            self._done.emit("progress", json.dumps(got / total))
                if total and part.stat().st_size != total:
                    raise OSError("Download unvollständig")
                os.chmod(part, 0o755)
                os.replace(part, target)       # die laufende Fassung bleibt bis zum Neustart gültig
                self._done.emit("ready", "{}")
            except Exception as exc:
                try:
                    part.unlink()
                except OSError:
                    pass
                self._done.emit("error", json.dumps(str(exc)))
        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def restart(self):
        """Neue Fassung starten – auch ein laufendes Broadcast im Hintergrund wird ersetzt."""
        if self.state != "ready":
            return
        daemon = subprocess.run(["pgrep", "-u", str(os.getuid()), "-f", "creative_broadcast.daemon"],
                                capture_output=True).returncode == 0
        if daemon:
            subprocess.run(["pkill", "-u", str(os.getuid()), "-f", "creative_broadcast.daemon"])
            subprocess.Popen([self.image, "--broadcastd"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.Popen([self.image], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        QGuiApplication.quit()

    @Slot()
    def later(self):
        self.dismissed = True
        self.changed.emit()

    def _finish(self, kind, payload):
        data = json.loads(payload)
        if kind == "info":
            if _version_tuple(data.get("version", "")) > _version_tuple(self.current) and data.get("url"):
                self.info, self.state = data, "available"
        elif kind == "progress":
            self.progress = float(data)
        elif kind == "ready":
            self.state, self.progress = "ready", 1.0
        elif kind == "error":
            self.state, self.error = "available", f"Update fehlgeschlagen: {data}"
        self.changed.emit()

    def _notes(self, key):
        return list((self.info.get("notizen") or {}).get(key) or [])

    phase = Property(str, lambda self: self.state, notify=changed)
    visible = Property(bool, lambda self: self.enabled and self.state != "" and not self.dismissed, notify=changed)
    version = Property(str, lambda self: self.info.get("version", ""), notify=changed)
    currentVersion = Property(str, lambda self: self.current, constant=True)
    sizeMb = Property(int, lambda self: int(self.info.get("size") or 0) // 1_000_000, notify=changed)
    progressValue = Property(float, lambda self: self.progress, notify=changed)
    errorText = Property(str, lambda self: self.error, notify=changed)
    studioNotes = Property("QVariantList", lambda self: self._notes("studio"), notify=changed)
    broadcastNotes = Property("QVariantList", lambda self: self._notes("broadcast"), notify=changed)
    writable = Property(bool, lambda self: bool(self.image) and os.access(os.path.dirname(self.image) or ".", os.W_OK)
                        and shutil.disk_usage(os.path.dirname(self.image) or ".").free > 600_000_000, constant=True)
