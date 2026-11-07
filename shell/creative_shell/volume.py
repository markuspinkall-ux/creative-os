"""Lautstärke des Standardausgangs für den Schnellzugriff."""

import re

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from .runner import Runner

DEFAULT_SINK = "@DEFAULT_AUDIO_SINK@"


class VolumeModel(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self._run = Runner(self, force_c_locale=True)
        self._value = 0
        self._muted = False
        self._available = False
        self._busy = False
        self._pending = {}
        self._poll = QTimer(self)
        self._poll.setInterval(3000)
        self._poll.timeout.connect(self.refresh)
        self._poll.start()
        self.refresh()

    @Slot()
    def refresh(self):
        if self._busy:
            return
        self._busy = True

        def done(code, out, _err):
            self._busy = False
            match = re.search(r"Volume:\s*(\d+(?:\.\d+)?)", out) if code == 0 else None
            if not self._pending:
                before = (self._available, self._value, self._muted)
                self._available = bool(match)
                if match:
                    self._value = round(float(match[1]) * 100)
                    self._muted = "[MUTED]" in out
                if before != (self._available, self._value, self._muted):
                    self.changed.emit()
            self._apply()

        self._run.run(["wpctl", "get-volume", DEFAULT_SINK], done, timeout_ms=2000)

    @Slot(int)
    def setVolume(self, value):
        self._value = max(0, min(100, value))
        self._pending["set-volume"] = f"{self._value}%"
        self.changed.emit()
        self._apply()

    @Slot()
    def toggleMute(self):
        self._muted = not self._muted
        self._pending["set-mute"] = "1" if self._muted else "0"
        self.changed.emit()
        self._apply()

    def _apply(self):
        if self._busy or not self._pending:
            return
        command = next(iter(self._pending))
        value = self._pending.pop(command)
        self._busy = True

        def done(_code, _out, _err):
            self._busy = False
            if self._pending:
                self._apply()
            else:
                self.refresh()

        self._run.run(["wpctl", command, DEFAULT_SINK, value], done, timeout_ms=2000)

    available = Property(bool, lambda self: self._available, notify=changed)
    value = Property(int, lambda self: self._value, notify=changed)
    muted = Property(bool, lambda self: self._muted, notify=changed)
