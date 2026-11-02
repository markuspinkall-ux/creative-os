"""Schreibtisch-Symbole: zeigt den Inhalt des Ordners „Schreibtisch“
auf dem Hintergrundbild – wie bei Windows.

Löschen geht immer in den Papierkorb, nichts wird überschrieben.
"""

import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import (
    Property, QAbstractListModel, QByteArray, QFileSystemWatcher, QMimeDatabase,
    QModelIndex, QObject, Qt, QTimer, QUrl, Signal, Slot,
)
from PySide6.QtGui import QDesktopServices

from .runner import spawn_detached

ROLES = ["name", "path", "isDir", "tint", "ext", "selected"]
ROLE_IDS = {n: Qt.ItemDataRole.UserRole + 1 + i for i, n in enumerate(ROLES)}


def desktop_dir():
    if shutil.which("xdg-user-dir"):
        try:
            out = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, timeout=3).stdout.strip()
            if out and Path(out) != Path.home():
                return Path(out)
        except (OSError, subprocess.SubprocessError):
            pass
    for name in ("Schreibtisch", "Desktop"):
        if (Path.home() / name).is_dir():
            return Path.home() / name
    return Path.home() / "Schreibtisch"


def file_color(mime):
    if mime == "application/pdf":
        return "#e5484d"
    major = mime.split("/", 1)[0]
    if major == "image":
        return "#b79bff"
    if major == "audio":
        return "#f2a0b4"
    if major == "video":
        return "#ffb07a"
    if any(k in mime for k in ("spreadsheet", "presentation", "csv")):
        return "#6fdcc0"
    if major == "text" or any(k in mime for k in ("document", "msword", "rtf")):
        return "#8fb3ff"
    return "#7f8898"


def unique_path(folder, name):
    candidate = folder / name
    if not candidate.exists():
        return candidate
    stem, suffix = name, ""
    if "." in name[1:]:
        stem, _, ext = name.rpartition(".")
        suffix = "." + ext
    n = 2
    while (folder / f"{stem} ({n}){suffix}").exists():
        n += 1
    return folder / f"{stem} ({n}){suffix}"


class DesktopModel(QAbstractListModel):
    selectionChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dir = desktop_dir()
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        self._mime = QMimeDatabase()
        self._rows = []
        self._watcher = QFileSystemWatcher(self)
        self._watcher.addPath(str(self._dir))
        self._watcher.directoryChanged.connect(lambda _p: self._timer.start())
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.refresh)
        self.refresh()

    # ---- Modell ---------------------------------------------------------------
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def roleNames(self):
        return {rid: QByteArray(n.encode()) for n, rid in ROLE_IDS.items()}

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        item = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return item["name"]
        for n, rid in ROLE_IDS.items():
            if rid == role:
                return item[n]
        return None

    @Slot()
    def refresh(self):
        selected = {r["path"] for r in self._rows if r["selected"]}
        rows = []
        try:
            with os.scandir(self._dir) as it:
                for e in it:
                    if e.name.startswith("."):
                        continue
                    try:
                        is_dir = e.is_dir()
                    except OSError:
                        is_dir = False
                    if is_dir:
                        tint, ext = "#5a6b8c", ""
                    else:
                        tint = file_color(self._mime.mimeTypeForFile(e.path).name())
                        ext = Path(e.name).suffix[1:5].upper()
                    rows.append({"name": e.name, "path": e.path, "isDir": is_dir, "tint": tint,
                                 "ext": ext, "selected": e.path in selected})
        except OSError:
            pass
        rows.sort(key=lambda r: (not r["isDir"], r["name"].casefold()))
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()
        if str(self._dir) not in self._watcher.directories() and self._dir.is_dir():
            self._watcher.addPath(str(self._dir))
        self.selectionChanged.emit()

    # ---- Auswahl --------------------------------------------------------------
    @Slot(int, bool)
    def select(self, row, toggle):
        for n, r in enumerate(self._rows):
            if toggle:
                if n == row:
                    r["selected"] = not r["selected"]
            else:
                r["selected"] = n == row
        if self._rows:
            self.dataChanged.emit(self.index(0), self.index(len(self._rows) - 1), [ROLE_IDS["selected"]])
        self.selectionChanged.emit()

    @Slot(int)
    def selectKeep(self, row):
        if 0 <= row < len(self._rows) and not self._rows[row]["selected"]:
            self.select(row, False)

    @Slot()
    def clearSelection(self):
        self.select(-1, False)

    def _selected(self):
        return [r for r in self._rows if r["selected"]]

    # ---- Aktionen -------------------------------------------------------------
    @Slot(int)
    def open(self, row):
        if 0 <= row < len(self._rows):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._rows[row]["path"]))

    @Slot()
    def openSelected(self):
        for r in self._selected():
            QDesktopServices.openUrl(QUrl.fromLocalFile(r["path"]))

    @Slot()
    def trashSelected(self):
        for r in self._selected():
            if shutil.which("gio"):
                subprocess.run(["gio", "trash", "--", r["path"]], capture_output=True)
        self.refresh()

    @Slot()
    def newFolder(self):
        target = unique_path(self._dir, "Neuer Ordner")
        try:
            target.mkdir()
        except OSError:
            return
        self.refresh()
        for n, r in enumerate(self._rows):
            if r["path"] == str(target):
                self.select(n, False)

    @Slot()
    def openFolder(self):
        if not spawn_detached(["creative-files", str(self._dir)]):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._dir)))

    @Slot()
    def openInFiles(self):
        sel = self._selected()
        target = sel[0]["path"] if len(sel) == 1 and sel[0]["isDir"] else str(self._dir)
        if not spawn_detached(["creative-files", target]):
            QDesktopServices.openUrl(QUrl.fromLocalFile(target))

    @Slot(result="QVariantList")
    def selectedPaths(self):
        return [r["path"] for r in self._selected()]

    selectedCount = Property(int, lambda self: len(self._selected()), notify=selectionChanged)
    folder = Property(str, lambda self: str(self._dir), constant=True)
