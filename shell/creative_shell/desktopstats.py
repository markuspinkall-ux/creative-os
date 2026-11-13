"""Leistungsanzeige oben rechts auf dem Schreibtisch (wie im Taskmanager)."""

import threading

from PySide6.QtCore import Property, QFileSystemWatcher, QObject, QTimer, Signal, Slot

from . import config, sysstats
from .mainthread import post


class DesktopStats(QObject):
    changed = Signal()
    enabledChanged = Signal()
    positionChanged = Signal()
    _sampled = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tiles = []
        cfg = config.load()
        self._enabled = cfg["desktopStats"]
        position = cfg["desktopStatsPosition"]
        self._position = (tuple(position) if len(position) == 2
                          and all(type(value) in (int, float) and 0 <= value <= 1 for value in position)
                          else (-1.0, -1.0))
        self._sampler = None
        self._busy = False
        self._sampled.connect(self._apply)
        self._timer = QTimer(self)
        self._timer.setInterval(1500)
        self._timer.timeout.connect(self._tick)
        if self._enabled:
            self._timer.start()
            QTimer.singleShot(500, self._tick)
        config.config_dir().mkdir(parents=True, exist_ok=True)
        self._cfg_watch = QFileSystemWatcher([str(config.config_dir())], self)
        self._cfg_watch.directoryChanged.connect(
            lambda *_: QTimer.singleShot(150, lambda: self._follow(bool(config.load().get("desktopStats", True)))))

    def _tick(self):
        if self._busy:
            return
        self._busy = True

        def work():
            try:
                if self._sampler is None:
                    self._sampler = sysstats.Sampler()
                s = self._sampler.sample()
                post(self._sampled.emit, sysstats.tiles(s, self._sampler))
            except Exception as exc:          # Anzeige darf die Shell nie stören
                print(f"creative-shell: Leistungsanzeige: {exc}")
                post(self._sampled.emit, [])
        threading.Thread(target=work, daemon=True).start()

    def _apply(self, tiles):
        self._busy = False
        self._tiles = tiles
        self.changed.emit()

    def _follow(self, on):
        if on != self._enabled:
            self._switch(on)

    @Slot(bool)
    def setEnabled(self, on):
        if on == self._enabled:
            return
        config.set_value("desktopStats", on)
        self._switch(on)

    def _switch(self, on):
        self._enabled = on
        if on:
            self._timer.start()
            self._tick()
        else:
            self._timer.stop()
            self._tiles = []
            self.changed.emit()
        self.enabledChanged.emit()

    @Slot(float, float)
    def setPos(self, x, y):
        self._position = (min(1.0, max(0.0, x)), min(1.0, max(0.0, y)))
        config.set_value("desktopStatsPosition", list(self._position))
        self.positionChanged.emit()

    posX = Property(float, lambda self: self._position[0], notify=positionChanged)
    posY = Property(float, lambda self: self._position[1], notify=positionChanged)

    @Slot()
    def openTaskManager(self):
        from .runner import spawn_detached
        if not spawn_detached(["creative-taskmanager", "--leistung"]):
            spawn_detached(["plasma-systemmonitor"])

    tiles = Property("QVariantList", lambda self: self._tiles, notify=changed)
    enabled = Property(bool, lambda self: self._enabled, notify=enabledChanged)
