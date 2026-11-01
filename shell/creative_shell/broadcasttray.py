"""Creative Broadcast im Tray: Symbol zeigt, ob Mikrofon-Filter oder Kamera-Effekt an sind.

Liest nur die Dateien des Hintergrunddienstes (creative-broadcastd) – kostet nichts.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot


def _cfg_file():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "creative-os" / "broadcast.json"


def _status_file():
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(base) / "creative-broadcast" / "status.json"


def _read(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


class BroadcastTray(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._available = shutil.which("creative-broadcast") is not None
        self._state = (False, False, "", "")
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._tick)
        if self._available:
            self._timer.start()
            QTimer.singleShot(800, self._tick)

    def _tick(self):
        cfg = _read(_cfg_file())
        st = _read(_status_file())
        state = (bool(cfg.get("voice")), bool(cfg.get("camera")),
                 str(st.get("voice", "")), str(st.get("camera", "")))
        if state != self._state:
            self._state = state
            self.changed.emit()

    @Slot()
    def open(self):
        subprocess.Popen(["creative-broadcast"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _tip(self):
        voice, cam, vst, cst = self._state
        parts = ["Creative Broadcast"]
        parts.append("Mikrofon: " + ("rauschfrei" if voice else "aus"))
        if cam:
            parts.append("Kamera: " + ("wird benutzt" if cst.startswith("aktiv") else "bereit"))
        else:
            parts.append("Kamera: aus")
        return " · ".join(parts)

    available = Property(bool, lambda self: self._available, constant=True)
    active = Property(bool, lambda self: self._state[0] or self._state[1], notify=changed)
    cameraInUse = Property(bool, lambda self: self._state[1] and self._state[3].startswith("aktiv"), notify=changed)
    tooltip = Property(str, _tip, notify=changed)
