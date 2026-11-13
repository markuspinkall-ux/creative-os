"""Schreibtisch-Symbole: zeigt den Inhalt des Ordners „Schreibtisch“
auf dem Hintergrundbild – wie bei Windows.

Löschen geht immer in den Papierkorb, nichts wird überschrieben.
"""

import os
import shutil
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import (
    Property, QAbstractListModel, QByteArray, QFileSystemWatcher, QMimeDatabase, QMimeData,
    QModelIndex, QObject, QSortFilterProxyModel, Qt, QTimer, QUrl, Signal, Slot,
)
from PySide6.QtGui import QDesktopServices, QGuiApplication

from . import config
from .runner import spawn_detached
from .mainthread import post

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
    if not os.path.lexists(candidate):
        return candidate
    stem, suffix = name, ""
    if "." in name[1:]:
        stem, _, ext = name.rpartition(".")
        suffix = "." + ext
    n = 2
    while os.path.lexists(folder / f"{stem} ({n}){suffix}"):
        n += 1
    return folder / f"{stem} ({n}){suffix}"


def transfer(sources, target_dir, mode="auto"):
    """Dateien in target_dir ablegen – nie überschreiben, nie in sich selbst.
    mode: auto (gleiches Laufwerk → verschieben, sonst kopieren) | copy | move.
    Gibt (erledigt, fehlgeschlagen) zurück."""
    target_dir = Path(target_dir)
    try:
        target_real, target_dev = target_dir.resolve(), target_dir.stat().st_dev
    except OSError:
        return 0, len(sources)
    done = failed = 0
    for path in sources:
        src = Path(path)
        try:
            src_real = src.resolve()
            if src_real == target_real or (src.is_dir() and not src.is_symlink()
                                           and target_real.is_relative_to(src_real)):
                continue  # nicht in sich selbst
            copy = mode == "copy" or (mode == "auto" and src.lstat().st_dev != target_dev)
            if not copy and src.parent.resolve() == target_real:
                continue  # liegt schon hier
            dst = unique_path(target_dir, src.name)
            if copy:
                if src.is_dir() and not src.is_symlink():
                    shutil.copytree(src, dst, symlinks=True)
                else:
                    shutil.copy2(src, dst, follow_symlinks=False)
            else:
                shutil.move(str(src), str(dst))
            done += 1
        except (OSError, shutil.Error):
            failed += 1
    return done, failed


class ScreenIcons(QSortFilterProxyModel):
    def __init__(self, desktop, screen):
        super().__init__(desktop)
        self.screen = screen
        self.available = set()
        self.primary = ""
        self.setSourceModel(desktop)

    def set_screens(self, available, primary):
        available = set(available)
        if available != self.available or primary != self.primary:
            self.available, self.primary = available, primary
            self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        source = self.sourceModel()
        path = source.data(source.index(row, 0, parent), ROLE_IDS["path"])
        target = source.screen_assignments.get(path)
        return self.screen == (target if target in self.available else self.primary)

    @Slot(int, result=int)
    def sourceRow(self, row):
        return self.mapToSource(self.index(row, 0)).row()


class DesktopModel(QAbstractListModel):
    selectionChanged = Signal()
    cellsChanged = Signal()
    clipboardChanged = Signal()
    pasteFinished = Signal(bool)
    dropFinished = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pasting = False
        QGuiApplication.clipboard().dataChanged.connect(self.clipboardChanged.emit)
        self.pasteFinished.connect(self._finishPaste)
        self.dropFinished.connect(self._finishDrop)
        self._dir = desktop_dir()
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        self._mime = QMimeDatabase()
        self._rows = []
        self.screen_assignments = {
            path: screen for path, screen in config.load()["desktopIconScreens"].items()
            if isinstance(screen, str)
        }
        self._screen_models = {}
        raw = config.load().get("desktopIconCells") or {}
        self._cells = {scr: {p: [int(c[0]), int(c[1])] for p, c in (cells or {}).items()
                             if isinstance(c, (list, tuple)) and len(c) == 2}
                       for scr, cells in raw.items() if isinstance(cells, dict)}
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
        listed = False
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
            listed = True
        except OSError:
            pass
        rows.sort(key=lambda r: (not r["isDir"], r["name"].casefold()))
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()
        if listed:                     # nur bei gelesenem Ordner aufräumen
            self._forget_missing()
        if str(self._dir) not in self._watcher.directories() and self._dir.is_dir():
            self._watcher.addPath(str(self._dir))
        self.selectionChanged.emit()

    @Slot(str, "QStringList", str, result=QObject)
    def screenModel(self, screen, available, primary):
        model = self._screen_models.get(screen)
        if model is None:
            model = self._screen_models[screen] = ScreenIcons(self, screen)
        model.set_screens(available, primary if primary in available else next(iter(available), screen))
        return model

    @Slot("QStringList", str)
    def moveToScreen(self, paths, screen):
        present = {row["path"] for row in self._rows}
        assignments = dict(self.screen_assignments)
        for path in paths:
            if path in present:
                assignments[path] = screen
        if assignments != self.screen_assignments and config.set_value("desktopIconScreens", assignments):
            self.screen_assignments = assignments
            for model in self._screen_models.values():
                model.invalidateFilter()

    # ---- Freie Plätze (wie bei Windows: Symbol dorthin ziehen, wo es liegen soll) ----
    def _save_cells(self):
        config.set_value("desktopIconCells", self._cells)
        self.cellsChanged.emit()

    @Slot(str, str, int, int)
    def placeDragged(self, path, screen, col, row):
        """Gezogenes Symbol (samt Auswahl) auf diesem Monitor an Spalte/Zeile ablegen.
        Mehrere Symbole kommen untereinander; was dort lag, sucht sich einen freien Platz."""
        selected = self.selectedPaths()
        paths = [path] + [p for p in selected if p != path] if path in selected else [path]
        present = {r["path"] for r in self._rows}
        paths = [p for p in paths if p in present]
        if not paths:
            return
        self.moveToScreen(paths, screen)
        cells = self._cells.setdefault(screen, {})
        for scr, other in self._cells.items():          # Platz auf anderen Monitoren vergessen
            if scr != screen:
                for p in paths:
                    other.pop(p, None)
        for i, p in enumerate(paths):
            target = [max(0, col), max(0, row + i)]
            for q, c in list(cells.items()):
                if c == target and q not in paths:
                    del cells[q]                         # verdrängtes Symbol ordnet sich neu ein
            cells[p] = target
        self._save_cells()

    def _forget_missing(self):
        present = {r["path"] for r in self._rows}
        changed = False
        for cells in self._cells.values():
            for p in [p for p in cells if p not in present]:
                del cells[p]
                changed = True
        if changed:
            self._save_cells()

    cells = Property("QVariantMap", lambda self: {k: dict(v) for k, v in self._cells.items()}, notify=cellsChanged)

    @Slot(str, str)
    def moveDraggedToScreen(self, path, screen):
        """Gezogenes Symbol (samt Auswahl, wenn es dazugehört) auf einen Monitor."""
        paths = self.selectedPaths()
        self.moveToScreen(paths if path in paths else [path], screen)

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

    @Slot("QVariantList")
    def selectRows(self, rows):
        selected = set(rows)
        for index, row in enumerate(self._rows):
            row["selected"] = index in selected
        if self._rows:
            self.dataChanged.emit(self.index(0), self.index(len(self._rows) - 1), [ROLE_IDS["selected"]])
        self.selectionChanged.emit()

    @Slot()
    def copySelected(self):
        urls = [QUrl.fromLocalFile(path) for path in self.selectedPaths()]
        if urls:
            data = QMimeData()
            data.setText("\n".join(url.toString() for url in urls))
            data.setUrls(urls)
            QGuiApplication.clipboard().setMimeData(data)

    def _clipboardPaths(self):
        data = QGuiApplication.clipboard().mimeData()
        if not data:
            return []
        urls = data.urls() if data.hasUrls() else [QUrl(line) for line in data.text().splitlines()]
        return list(dict.fromkeys(url.toLocalFile() for url in urls if url.isLocalFile()))

    canPaste = Property(bool, lambda self: not self._pasting and bool(self._clipboardPaths()),
                        notify=clipboardChanged)

    @Slot()
    def paste(self):
        sources = self._clipboardPaths()
        if self._pasting or not sources:
            return
        self._pasting = True
        self.clipboardChanged.emit()

        def copy():
            ok = True
            try:
                for path in sources:
                    source = Path(path)
                    if not source.name or source.resolve() in (self._dir.resolve(), *self._dir.resolve().parents):
                        ok = False
                        continue
                    target = unique_path(self._dir, source.name)
                    result = subprocess.run(["cp", "-a", "--update=none-fail", "-T", "--", path, str(target)],
                                            capture_output=True)
                    ok = result.returncode == 0 and ok
            except (OSError, RuntimeError):
                ok = False
            finally:
                post(self.pasteFinished.emit, ok)

        threading.Thread(target=copy, daemon=True).start()

    @Slot(bool)
    def _finishPaste(self, ok):
        self._pasting = False
        self.clipboardChanged.emit()
        self.refresh()
        if not ok:
            spawn_detached(["notify-send", "Schreibtisch", "Einige Dateien konnten nicht kopiert werden."])

    # ---- Ziehen & Ablegen ------------------------------------------------------
    @Slot("QVariantList", str, str)
    def dropUrls(self, urls, target, mode):
        """Auf den Schreibtisch (target = "") oder auf einen Ordner darauf abgelegte Dateien."""
        sources = []
        for u in urls or []:
            url = u if isinstance(u, QUrl) else QUrl(str(u))
            if url.isLocalFile() and url.toLocalFile():
                sources.append(url.toLocalFile())
        sources = list(dict.fromkeys(sources))
        if not sources:
            return
        target = target or str(self._dir)

        def work():
            _done, failed = transfer(sources, target, mode)
            post(self.dropFinished.emit, failed)

        threading.Thread(target=work, daemon=True).start()

    def _finishDrop(self, failed):
        self.refresh()
        if failed:
            spawn_detached(["notify-send", "Schreibtisch",
                            f"{failed} {'Element konnte' if failed == 1 else 'Elemente konnten'} nicht abgelegt werden."])

    @Slot(str, result=str)
    def dragUris(self, path):
        """Was beim Ziehen mitgeht: die Auswahl (wenn das Symbol dazugehört), sonst nur dieses."""
        paths = self.selectedPaths()
        if path not in paths:
            paths = [path]
        return "\r\n".join(QUrl.fromLocalFile(p).toString() for p in paths)

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
        """Ausgewählte Dateien und Ordner in den Papierkorb (lassen sich dort zurückholen)."""
        for r in self._selected():
            ok = False
            if shutil.which("gio"):
                ok = subprocess.run(["gio", "trash", "--", r["path"]], capture_output=True).returncode == 0
            if not ok:
                try:
                    from PySide6.QtCore import QFile
                    QFile.moveToTrash(r["path"])
                except Exception:
                    pass
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
