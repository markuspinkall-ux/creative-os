"""Papierkorb im Tray: zeigt, ob etwas drin ist; öffnen und leeren.

Es ist derselbe Papierkorb wie im Dateimanager „Dateien“
(freedesktop-Standard unter ~/.local/share/Trash).
"""

import os
import shutil
from pathlib import Path

from PySide6.QtCore import Property, QFileSystemWatcher, QObject, QTimer, Signal, Slot

from .runner import spawn_detached


def trash_dir():
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "Trash"


class TrashModel(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._count = 0
        files = trash_dir() / "files"
        try:
            files.mkdir(parents=True, exist_ok=True)
            (trash_dir() / "info").mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        self._watcher = QFileSystemWatcher(self)
        self._watcher.addPath(str(files))
        self._watcher.directoryChanged.connect(lambda _p: self._timer.start())
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.refresh)
        self.refresh()

    @Slot()
    def refresh(self):
        try:
            count = sum(1 for _ in os.scandir(trash_dir() / "files"))
        except OSError:
            count = 0
        if count != self._count:
            self._count = count
            self.changed.emit()

    @Slot()
    def open(self):
        if not spawn_detached(["creative-files", "trash:"]):
            spawn_detached(["xdg-open", "trash:///"])

    @Slot()
    def empty(self):
        if shutil.which("gio") and spawn_detached(["gio", "trash", "--empty"]):
            QTimer.singleShot(800, self.refresh)
            return
        td = trash_dir()
        for sub in ("files", "info"):
            d = td / sub
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
                d.mkdir(exist_ok=True)
        self._watcher.addPath(str(td / "files"))
        self.refresh()

    count = Property(int, lambda self: self._count, notify=changed)
    full = Property(bool, lambda self: self._count > 0, notify=changed)
