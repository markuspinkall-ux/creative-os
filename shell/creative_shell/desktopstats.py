"""Leistungsanzeige oben rechts auf dem Schreibtisch (wie im Taskmanager)."""

import threading

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from . import config, sysstats


class DesktopStats(QObject):
    changed = Signal()
    enabledChanged = Signal()
    _sampled = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tiles = []
        self._enabled = bool(config.load().get("desktopStats", True))
        self._sampler = None
        self._busy = False
        self._sampled.connect(self._apply)
        self._timer = QTimer(self)
        self._timer.setInterval(1500)
        self._timer.timeout.connect(self._tick)
        if self._enabled:
            self._timer.start()
            QTimer.singleShot(500, self._tick)

    def _tick(self):
        if self._busy:
            return
        self._busy = True

        def work():
            try:
                if self._sampler is None:
                    self._sampler = sysstats.Sampler()
                s = self._sampler.sample()
                self._sampled.emit(sysstats.tiles(s, self._sampler))
            except Exception as exc:          # Anzeige darf die Shell nie stören
                print(f"creative-shell: Leistungsanzeige: {exc}")
                self._sampled.emit([])
        threading.Thread(target=work, daemon=True).start()

    def _apply(self, tiles):
        self._busy = False
        self._tiles = tiles
        self.changed.emit()

    @Slot(bool)
    def setEnabled(self, on):
        if on == self._enabled:
            return
        self._enabled = on
        config.set_value("desktopStats", on)
        if on:
            self._timer.start()
            self._tick()
        else:
            self._timer.stop()
            self._tiles = []
            self.changed.emit()
        self.enabledChanged.emit()

    @Slot()
    def openTaskManager(self):
        from .runner import spawn_detached
        if not spawn_detached(["creative-taskmanager", "--leistung"]):
            spawn_detached(["plasma-systemmonitor"])

    tiles = Property("QVariantList", lambda self: self._tiles, notify=changed)
    enabled = Property(bool, lambda self: self._enabled, notify=enabledChanged)
