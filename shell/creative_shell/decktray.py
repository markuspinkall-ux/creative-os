"""Deck im Tray: Klick öffnet den Editor, das Symbol zeigt, ob ein Stream Deck verbunden ist.

Der Gerätedienst (creative-deck --hintergrund) startet mit der Sitzung über den
Supervisor; hier wird nur seine Statusdatei gelesen – kostet nichts.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot


def _status_file():
    base = os.environ.get("XDG_RUNTIME_DIR") or str(Path.home() / ".cache")
    return Path(base) / "creative-deck" / "status.json"


def read_devices(path=None):
    """Namen der verbundenen Geräte laut Dienst – leer, wenn keins da ist oder der Dienst ruht."""
    try:
        data = json.loads((path or _status_file()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict) or data.get("beendet"):
        return []
    out = []
    for dev in data.get("geraete") or []:
        if isinstance(dev, dict):
            out.append(str(dev.get("modell") or "Stream Deck"))
    return out


class DeckTray(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._available = shutil.which("creative-deck") is not None
        self._devices = []
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self._tick)
        if self._available:
            self._timer.start()
            QTimer.singleShot(900, self._tick)

    def _tick(self):
        devices = read_devices()
        if devices != self._devices:
            self._devices = devices
            self.changed.emit()

    @Slot()
    def open(self):
        subprocess.Popen(["creative-deck"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _tip(self):
        if not self._devices:
            return "Deck · kein Stream Deck verbunden"
        return "Deck · " + ", ".join(self._devices) + " verbunden"

    available = Property(bool, lambda self: self._available, constant=True)
    connected = Property(bool, lambda self: bool(self._devices), notify=changed)
    tooltip = Property(str, _tip, notify=changed)
