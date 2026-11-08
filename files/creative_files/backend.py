"""Verbindung zwischen Datei-Logik (fsops) und Oberfläche (QML).

Ein Objekt „fm“ steuert ein Fenster: aktuelle Seite (Dieser PC, Ordner,
Papierkorb), Verlauf, Auswahl, Zwischenablage und „Rückgängig“.
Langsame Dinge (Kopieren, Ordnergröße) laufen im Hintergrund.
"""

import os
import shutil
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QFileSystemWatcher,
    QMimeDatabase,
    QModelIndex,
    QObject,
    Qt,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices, QGuiApplication

from . import fsops

ROLES = ["name", "path", "isDir", "typeName", "sizeText", "dateText", "tint", "ext", "selected", "extra"]
ROLE_IDS = {name: Qt.ItemDataRole.UserRole + 1 + i for i, name in enumerate(ROLES)}

QUICK = [
    ("DESKTOP", ["Schreibtisch", "Desktop"], "Desktop", "#5a6b8c"),
    ("DOWNLOAD", ["Downloads"], "Downloads", "#6fdcc0"),
    ("DOCUMENTS", ["Dokumente", "Documents"], "Dokumente", "#8fb3ff"),
    ("PICTURES", ["Bilder", "Pictures"], "Bilder", "#ffb07a"),
    ("MUSIC", ["Musik", "Music"], "Musik", "#f2a0b4"),
    ("VIDEOS", ["Videos"], "Videos", "#b79bff"),
]


FOLDER_DEFAULT = "#5a6b8c"


def file_color(mime):
    """Einheitliche Farbe je Dateiart (statt bunter Fremd-Symbole)."""
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


def xdg_dir(kind, fallbacks):
    if shutil.which("xdg-user-dir"):
        try:
            out = subprocess.run(["xdg-user-dir", kind], capture_output=True, text=True, timeout=3).stdout.strip()
            if out and Path(out).is_dir() and Path(out) != fsops.HOME:
                return Path(out)
        except (OSError, subprocess.SubprocessError):
            pass
    for name in fallbacks:
        if (fsops.HOME / name).is_dir():
            return fsops.HOME / name
    return None


class FileList(QAbstractListModel):
    """Die Einträge der aktuellen Seite samt Auswahl."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all, self._rows, self._filter = [], [], ""

    def set_items(self, items):
        self.beginResetModel()
        self._all = items
        self._apply()
        self.endResetModel()

    def set_filter(self, text):
        self.beginResetModel()
        self._filter = text
        self._apply()
        self.endResetModel()

    def _apply(self):
        t = self._filter.casefold().strip()
        self._rows = [i for i in self._all if not t or t in i["name"].casefold()]
        for i in self._rows:
            i.setdefault("selected", False)

    def rows(self):
        return self._rows

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def roleNames(self):
        return {rid: QByteArray(name.encode()) for name, rid in ROLE_IDS.items()}

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        item = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return item["name"]
        for name, rid in ROLE_IDS.items():
            if rid == role:
                return item.get(name, "")
        return None

    def set_selected(self, rows):
        rows = set(rows)
        for n, item in enumerate(self._rows):
            item["selected"] = n in rows
        if self._rows:
            self.dataChanged.emit(self.index(0), self.index(len(self._rows) - 1), [ROLE_IDS["selected"]])

    def selected(self):
        return [i for i in self._rows if i.get("selected")]


class FileManager(QObject):
    changed = Signal()          # Seite, Verlauf, Statuszeile
    locationChanged = Signal()  # anderer Ordner/andere Seite
    selectionChanged = Signal()
    toastChanged = Signal()
    drivesChanged = Signal()
    busyChanged = Signal()
    workDone = Signal(object)   # aus Hintergrund-Threads
    propertiesReady = Signal(object)
    cloudFolderReady = Signal(object)

    def __init__(self, start_path=None, parent=None):
        super().__init__(parent)
        self._mime = QMimeDatabase()
        self._files = FileList(self)
        self._page = "pc"           # pc | folder | trash
        self._path = ""
        self._folder_request = 0
        self._history, self._pos = [], -1
        self._anchor = -1
        self._clip, self._clip_cut = [], False
        self._undo = None
        self._toast, self._toast_undo = "", False
        self._busy, self._busy_text = False, ""
        self._drives = []
        self._view = "list"
        self._quick = []
        for kind, fallbacks, label, color in QUICK:
            p = xdg_dir(kind, fallbacks)
            if p:
                self._quick.append({"name": label, "path": str(p), "color": color})

        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(lambda _p: self._reload_timer.start())
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(300)
        self._reload_timer.timeout.connect(self.refresh)
        self._drive_timer = QTimer(self)
        self._drive_timer.setInterval(4000)
        self._drive_timer.timeout.connect(self._load_drives)
        self._drive_timer.start()
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.setInterval(8000)
        self._toast_timer.timeout.connect(self._clear_toast)
        self.workDone.connect(self._on_work_done)
        self.cloudFolderReady.connect(self._show_cloud_folder)

        self._load_drives()
        if start_path and Path(start_path).is_dir():
            self.navigate(str(Path(start_path).resolve()))
        else:
            self.openPage("pc")

    # ---- Seiten & Verlauf -----------------------------------------------------
    def _go(self, page, path, record=True):
        self._page, self._path = page, path
        if record:
            self._history = self._history[: self._pos + 1] + [(page, path)]
            self._pos = len(self._history) - 1
        for d in self._watcher.directories():
            self._watcher.removePath(d)
        if page == "folder" and not fsops.is_google_drive(path):
            self._watcher.addPath(path)
        self._anchor = -1
        self.files.set_filter("")
        self.refresh()
        self.locationChanged.emit()

    @Slot(str)
    def navigate(self, path):
        p = Path(path).expanduser()
        if not fsops.is_google_drive(p) and not p.is_dir():
            self._show_toast(f"„{p.name or path}“ ist nicht erreichbar.")
            return
        self._go("folder", str(p))

    @Slot(str)
    def openPage(self, page):
        self._go(page, "")

    @Slot()
    def back(self):
        if self._pos > 0:
            self._pos -= 1
            self._go(*self._history[self._pos], record=False)

    @Slot()
    def forward(self):
        if self._pos < len(self._history) - 1:
            self._pos += 1
            self._go(*self._history[self._pos], record=False)

    @Slot()
    def up(self):
        if self._page == "folder":
            parent = Path(self._path).parent
            if str(parent) != self._path:
                self.navigate(str(parent))
            else:
                self.openPage("pc")

    @Slot()
    def refresh(self):
        self._folder_request += 1
        if self._page == "folder" and fsops.is_google_drive(self._path):
            self.files.set_items([])
            self._load_cloud_folder(self._path, self._folder_request)
        elif self._page == "folder":
            try:
                entries = fsops.list_folder(self._path)
            except OSError as exc:
                self._show_toast(f"Ordner kann nicht geöffnet werden: {exc.strerror or exc}")
                entries = []
            self.files.set_items([self._decorate(e) for e in entries])
        elif self._page == "trash":
            items = []
            for t in fsops.trash_items():
                item = self._decorate(t)
                item["dateText"] = t["deleted"].replace("T", " ")[:16]
                item["extra"] = str(Path(t["original"]).parent)
                item["trashName"] = t["trashName"]
                items.append(item)
            self.files.set_items(items)
        else:
            self.files.set_items([])
        self.changed.emit()
        self.selectionChanged.emit()

    def _load_cloud_folder(self, path, request):
        def read():
            try:
                mount = fsops.google_drive_path()
                if not mount or not mount.is_mount():
                    raise OSError("Google Drive ist nicht eingebunden.")
                entries, error = fsops.list_folder(path), ""
            except OSError as exc:
                entries, error = [], exc.strerror or str(exc)
            self.cloudFolderReady.emit((request, entries, error))

        threading.Thread(target=read, daemon=True).start()

    @Slot(object)
    def _show_cloud_folder(self, result):
        request, entries, error = result
        if request != self._folder_request:
            return
        if error:
            self._show_toast(f"Ordner kann nicht geöffnet werden: {error}")
        self.files.set_items([self._decorate(entry, extension_only=True) for entry in entries])
        self.changed.emit()
        self.selectionChanged.emit()

    def _decorate(self, e, extension_only=False):
        if e["isDir"]:
            type_name, color, ext = "Ordner", self._folder_color(e["path"]), ""
        else:
            mime = (self._mime.mimeTypeForFile(e["path"], QMimeDatabase.MatchMode.MatchExtension)
                    if extension_only else self._mime.mimeTypeForFile(e["path"]))
            type_name = mime.comment() or "Datei"
            color = file_color(mime.name())
            ext = Path(e["name"]).suffix[1:5].upper()
        return {
            "name": e["name"], "path": e["path"], "isDir": e["isDir"], "typeName": type_name,
            "sizeText": "" if e["isDir"] else fsops.format_size(e.get("size")),
            "dateText": fsops.format_date(e["mtime"]) if e.get("mtime") else "",
            "tint": color, "ext": ext, "selected": False, "extra": "",
        }

    def _folder_color(self, path):
        for q in self._quick:
            if q["path"] == path:
                return q["color"]
        return FOLDER_DEFAULT

    # ---- Öffnen ---------------------------------------------------------------
    @Slot(int)
    def activate(self, row):
        rows = self.files.rows()
        if not 0 <= row < len(rows):
            return
        item = rows[row]
        if self._page == "trash":
            self._show_toast("Zum Öffnen erst wiederherstellen.")
        elif item["isDir"]:
            self.navigate(item["path"])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(item["path"]))

    @Slot()
    def openSelection(self):
        sel = self.files.selected()
        if len(sel) == 1:
            self.activate(self.files.rows().index(sel[0]))
        else:
            for item in sel:
                if not item["isDir"]:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(item["path"]))

    @Slot()
    def openTerminalHere(self):
        folder = self._path if self._page == "folder" else str(fsops.HOME)
        for term in (["konsole", "--workdir", folder], ["ptyxis", "--working-directory", folder],
                     ["foot", "-D", folder]):
            if shutil.which(term[0]):
                subprocess.Popen(term, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return

    # ---- Auswahl --------------------------------------------------------------
    @Slot(int, str)
    def select(self, row, mode):
        """mode: single | toggle | range | keep (Rechtsklick auf Ausgewähltes)"""
        current = {n for n, i in enumerate(self.files.rows()) if i.get("selected")}
        if mode == "keep" and row in current:
            return
        if mode == "toggle":
            current ^= {row}
            self._anchor = row
        elif mode == "range" and self._anchor >= 0:
            lo, hi = sorted((self._anchor, row))
            current = set(range(lo, hi + 1))
        else:
            current = {row} if row >= 0 else set()
            self._anchor = row
        self.files.set_selected(current)
        self.selectionChanged.emit()

    @Slot()
    def selectAll(self):
        self.files.set_selected(range(len(self.files.rows())))
        self.selectionChanged.emit()

    @Slot()
    def clearSelection(self):
        self.files.set_selected([])
        self.selectionChanged.emit()

    @Slot(str)
    def setFilter(self, text):
        self.files.set_filter(text)
        self.selectionChanged.emit()

    def _selected_paths(self):
        return [i["path"] for i in self.files.selected()]

    # ---- Neu, Umbenennen ------------------------------------------------------
    @Slot(str, result=str)
    def newFolder(self, name):
        if self._page != "folder":
            return "Hier kann kein Ordner angelegt werden."
        err = fsops.check_name(name)
        if err:
            return err
        target = Path(self._path) / name.strip()
        if target.exists():
            return "Diesen Namen gibt es hier schon."
        try:
            target.mkdir()
        except OSError as exc:
            return self._friendly(exc)
        self._undo = ("newfolder", str(target))
        self.refresh()
        self._select_path(str(target))
        self._show_toast(f"Ordner „{target.name}“ angelegt", undo=True)
        return ""

    @Slot(str, result=str)
    def newTextFile(self, name):
        if self._page != "folder":
            return "Hier kann keine Datei angelegt werden."
        err = fsops.check_name(name)
        if err:
            return err
        name = name.strip()
        if "." not in name:
            name += ".txt"
        target = Path(self._path) / name
        if target.exists():
            return "Diesen Namen gibt es hier schon."
        try:
            target.touch()
        except OSError as exc:
            return self._friendly(exc)
        self._undo = ("newfolder", str(target))
        self.refresh()
        self._select_path(str(target))
        return ""

    @Slot(str, result=str)
    def renameSelected(self, new_name):
        sel = self.files.selected()
        if len(sel) != 1:
            return "Bitte genau eine Datei auswählen."
        err = fsops.check_name(new_name)
        if err:
            return err
        src = Path(sel[0]["path"])
        dst = src.with_name(new_name.strip())
        if dst == src:
            return ""
        if dst.exists():
            return "Diesen Namen gibt es hier schon."
        try:
            src.rename(dst)
        except OSError as exc:
            return self._friendly(exc)
        self._undo = ("rename", str(dst), str(src))
        self.refresh()
        self._select_path(str(dst))
        return ""

    def _select_path(self, path):
        for n, i in enumerate(self.files.rows()):
            if i["path"] == path:
                self.select(n, "single")
                return

    # ---- Zwischenablage -------------------------------------------------------
    @Slot()
    def copySelection(self):
        self._set_clip(self._selected_paths(), cut=False)

    @Slot()
    def cutSelection(self):
        self._set_clip(self._selected_paths(), cut=True)

    def _set_clip(self, paths, cut):
        if not paths:
            return
        self._clip, self._clip_cut = paths, cut
        # Auch für andere Programme (z. B. Bild in Discord einfügen)
        QGuiApplication.clipboard().setText("\n".join(QUrl.fromLocalFile(p).toString() for p in paths))
        n = len(paths)
        what = f"„{Path(paths[0]).name}“" if n == 1 else f"{n} Elemente"
        self._show_toast(f"{what} {'ausgeschnitten' if cut else 'kopiert'} – mit Einfügen ablegen")
        self.changed.emit()

    @Slot()
    def paste(self):
        if self._page != "folder" or not self._clip or self._busy:
            return
        sources, cut, target = list(self._clip), self._clip_cut, self._path
        if cut and any(fsops.is_google_drive(p) for p in [target, *sources]):
            self._show_toast("Für Google Drive bitte Kopieren statt Ausschneiden verwenden.")
            return
        if cut:
            self._clip = []
        self._run_bg("Verschiebe …" if cut else "Kopiere …",
                     lambda: ("move" if cut else "copy", (fsops.move_into if cut else fsops.copy_into)(sources, target)))

    # ---- Papierkorb -----------------------------------------------------------
    @Slot()
    def trashSelection(self):
        if self._page != "folder" or self._busy:
            return
        paths = self._selected_paths()
        if not paths:
            return

        def work():
            names = []
            for p in paths:
                names.append(fsops.move_to_trash(p))
            return ("trash", list(zip(paths, names)))

        self._run_bg("In den Papierkorb …", work)

    @Slot()
    def restoreSelection(self):
        if self._page != "trash":
            return
        restored = 0
        for item in self.files.selected():
            try:
                fsops.restore_from_trash(item["trashName"])
                restored += 1
            except OSError as exc:
                self._show_toast(self._friendly(exc))
        self.refresh()
        if restored:
            self._show_toast(f"{restored} {'Element' if restored == 1 else 'Elemente'} wiederhergestellt")

    @Slot()
    def emptyTrash(self):
        try:
            fsops.empty_trash()
        except OSError as exc:
            self._show_toast(f"Papierkorb konnte nicht vollständig geleert werden: {exc}")
        else:
            self._show_toast("Papierkorb geleert")
        self.refresh()

    # ---- Rückgängig -----------------------------------------------------------
    @Slot()
    def undo(self):
        op, self._undo = self._undo, None
        self._clear_toast()
        if not op:
            return
        try:
            kind = op[0]
            if kind == "rename":
                Path(op[1]).rename(op[2])
            elif kind == "newfolder":
                p = Path(op[1])
                if p.is_dir() and not any(p.iterdir()):
                    p.rmdir()
                elif p.is_file() and p.stat().st_size == 0:
                    p.unlink()
            elif kind == "trash":
                for _original, trash_name in op[1]:
                    if trash_name:
                        fsops.restore_from_trash(trash_name)
            elif kind == "copy":
                for _src, dst in op[1]:
                    fsops.move_to_trash(dst)   # Kopien nie hart löschen
            elif kind == "move":
                for src, dst in op[1]:
                    target = fsops.unique_path(Path(src).parent, Path(src).name)
                    shutil.move(dst, target)
            self._show_toast("Rückgängig gemacht")
        except OSError as exc:
            self._show_toast("Konnte nicht rückgängig gemacht werden: " + self._friendly(exc))
        self.refresh()

    # ---- Hintergrund-Arbeit ---------------------------------------------------
    def _run_bg(self, text, fn):
        self._busy, self._busy_text = True, text
        self.busyChanged.emit()

        def runner():
            try:
                self.workDone.emit(("ok", fn()))
            except Exception as exc:  # jede Panne landet als Hinweis, nie als Absturz
                self.workDone.emit(("error", exc))

        threading.Thread(target=runner, daemon=True).start()

    def _on_work_done(self, result):
        self._busy = False
        self.busyChanged.emit()
        status, value = result
        if status == "error":
            self._show_toast(self._friendly(value))
            self.refresh()
            return
        kind, pairs = value
        self._undo = (kind, pairs)
        self.refresh()
        n = len(pairs)
        if n == 0:
            return
        what = f"„{Path(pairs[0][0]).name}“" if n == 1 else f"{n} Elemente"
        verb = {"copy": "kopiert", "move": "verschoben", "trash": "in den Papierkorb verschoben"}[kind]
        self._show_toast(f"{what} {'wurde' if n == 1 else 'wurden'} {verb}", undo=True)

    # ---- Eigenschaften --------------------------------------------------------
    @Slot()
    def requestProperties(self):
        sel = self.files.selected()
        if not sel:
            return
        item = sel[0]
        p = Path(item["path"])
        try:
            st = p.lstat()
            changed = fsops.format_date(st.st_mtime)
        except OSError:
            changed = ""
        info = {"name": item["name"] if len(sel) == 1 else f"{len(sel)} Elemente",
                "type": item["typeName"] if len(sel) == 1 else "Mehrere",
                "location": str(p.parent), "changed": changed if len(sel) == 1 else "",
                "size": "wird berechnet …", "tint": item["tint"], "ext": item["ext"], "isDir": item["isDir"]}
        self.propertiesReady.emit(info)
        paths = [i["path"] for i in sel]

        def work():
            total, count = 0, 0
            for path in paths:
                pp = Path(path)
                if pp.is_dir() and not pp.is_symlink():
                    t, c, _ = fsops.folder_size(pp)
                    total += t
                    count += c
                else:
                    try:
                        total += pp.lstat().st_size
                    except OSError:
                        pass
                    count += 1
            text = fsops.format_size(total)
            if count > 1 or any(Path(x).is_dir() for x in paths):
                text += f" · {count} {'Datei' if count == 1 else 'Dateien'}"
            info2 = dict(info)
            info2["size"] = text
            self.propertiesReady.emit(info2)

        threading.Thread(target=work, daemon=True).start()

    # ---- Laufwerke ------------------------------------------------------------
    def _load_drives(self):
        def work():
            try:
                drives = fsops.list_drives()
            except Exception:
                drives = []
            QTimer.singleShot(0, self, lambda: self._set_drives(drives))

        threading.Thread(target=work, daemon=True).start()

    def _set_drives(self, drives):
        out = []
        for d in drives:
            size, used = d.get("size"), d.get("used")
            if d["mounted"] and size and (d.get("free") is not None or used is not None):
                free = d.get("free", max(0, size - used)) if used is not None else d["free"]
                info = f"{fsops.format_size(free)} frei von {fsops.format_size(size)}"
                frac = max(0, min(1, (used or 0) / size))
            elif d["mounted"]:
                info = "Speicherbelegung nicht verfügbar"
                frac = 0
            else:
                info = "Nicht verbunden – zum Öffnen anklicken"
                frac = 0
            out.append({**d, "info": info, "usedFraction": frac})
        cloud = fsops.google_drive_path()
        if cloud and (Path.home() / ".config/creative-drive/rclone.conf").is_file():
            try:
                mounted = cloud.is_mount()
            except OSError:
                mounted = False
            out.append({"name": "Google Drive", "tag": "Cloud", "system": False,
                        "removable": False, "mounted": mounted, "mountPath": str(cloud),
                        "device": "", "cloud": True, "usedFraction": 0,
                        "info": "Online-Speicher" if mounted else "Zum Einbinden anklicken"})
        if out != self._drives:
            self._drives = out
            self.drivesChanged.emit()

    @Slot(int)
    def openDrive(self, index):
        if not 0 <= index < len(self._drives):
            return
        d = self._drives[index]
        if d.get("cloud"):
            mount = fsops.google_drive_path()
            try:
                if mount and mount.is_mount():
                    self.navigate(str(mount))
                else:
                    subprocess.Popen(["creative-settings", "--page", "google-drive"])
            except OSError:
                self._show_toast("Google Drive ist nicht erreichbar.")
            return
        if d["system"]:
            self.navigate(str(fsops.HOME))
        elif d["mounted"]:
            self.navigate(d["mountPath"])
        else:
            r = subprocess.run(["udisksctl", "mount", "-b", d["device"]], capture_output=True, text=True)
            if r.returncode == 0 and " at " in r.stdout:
                self.navigate(r.stdout.strip().split(" at ", 1)[1].rstrip("."))
                self._load_drives()
            else:
                self._show_toast("Laufwerk konnte nicht geöffnet werden.")

    @Slot(int)
    def ejectDrive(self, index):
        if not 0 <= index < len(self._drives):
            return
        d = self._drives[index]
        if self._page == "folder" and d["mountPath"] and self._path.startswith(d["mountPath"]):
            self.openPage("pc")
        ok = False
        if d["mountPath"] and shutil.which("gio"):
            ok = subprocess.run(["gio", "mount", "-e", d["mountPath"]], capture_output=True).returncode == 0
        if not ok:
            ok = subprocess.run(["udisksctl", "unmount", "-b", d["device"]], capture_output=True).returncode == 0
        self._show_toast(f"„{d['name']}“ kann jetzt sicher entfernt werden." if ok
                         else f"„{d['name']}“ wird noch benutzt – bitte offene Dateien schließen.")
        self._load_drives()

    # ---- Hinweise ---------------------------------------------------------------
    def _show_toast(self, text, undo=False):
        self._toast, self._toast_undo = text, undo and self._undo is not None
        self._toast_timer.start()
        self.toastChanged.emit()

    def _clear_toast(self):
        self._toast, self._toast_undo = "", False
        self.toastChanged.emit()

    @staticmethod
    def _friendly(exc):
        if isinstance(exc, PermissionError):
            return "Dafür fehlen die Berechtigungen."
        if isinstance(exc, FileNotFoundError):
            return "Die Datei gibt es nicht mehr."
        if isinstance(exc, ValueError):
            return str(exc)
        if isinstance(exc, OSError) and exc.errno == 28:
            return "Auf dem Laufwerk ist nicht genug Platz."
        return str(getattr(exc, "strerror", None) or exc)

    # ---- Eigenschaften für QML --------------------------------------------------
    def _crumbs(self):
        if self._page == "pc":
            return [{"name": "Dieser PC", "path": ""}]
        if self._page == "trash":
            return [{"name": "Papierkorb", "path": ""}]
        p = Path(self._path)
        home = fsops.HOME
        crumbs = []
        if p == home or home in p.parents:
            crumbs.append({"name": "Persönlicher Ordner", "path": str(home)})
            for part in p.relative_to(home).parts:
                crumbs.append({"name": part, "path": str(Path(crumbs[-1]["path"]) / part)})
        else:
            acc = Path(p.anchor)
            crumbs.append({"name": "Dieser PC", "path": ""})
            for part in p.parts[1:]:
                acc = acc / part
                crumbs.append({"name": part, "path": str(acc)})
        return crumbs

    def _status(self):
        n = len(self.files.rows())
        sel = self.files.selected()
        text = f"{n} {'Element' if n == 1 else 'Elemente'}"
        if sel:
            text += f" · {len(sel)} ausgewählt"
            sizes = [i for i in sel if not i["isDir"]]
            if len(sel) == 1 and sizes:
                text += f" ({sel[0]['sizeText']})"
        return text

    def _set_view(self, v):
        if v in ("list", "tiles") and v != self._view:
            self._view = v
            self.changed.emit()

    # Die Liste muss als Qt-Eigenschaft sichtbar sein, sonst sieht QML sie nicht
    files = Property(QObject, lambda self: self._files, constant=True)
    page = Property(str, lambda self: self._page, notify=changed)
    currentPath = Property(str, lambda self: self._path, notify=changed)
    crumbs = Property("QVariantList", _crumbs, notify=changed)
    canBack = Property(bool, lambda self: self._pos > 0, notify=changed)
    canForward = Property(bool, lambda self: self._pos < len(self._history) - 1, notify=changed)
    canUp = Property(bool, lambda self: self._page == "folder", notify=changed)
    canPaste = Property(bool, lambda self: self._page == "folder" and bool(self._clip), notify=changed)
    view = Property(str, lambda self: self._view, _set_view, notify=changed)
    quickPlaces = Property("QVariantList", lambda self: self._quick, constant=True)
    drives = Property("QVariantList", lambda self: self._drives, notify=drivesChanged)
    status = Property(str, _status, notify=selectionChanged)
    selectedCount = Property(int, lambda self: len(self.files.selected()), notify=selectionChanged)
    selectedName = Property(str, lambda self: (self.files.selected() or [{"name": ""}])[0]["name"],
                            notify=selectionChanged)
    toast = Property(str, lambda self: self._toast, notify=toastChanged)
    toastCanUndo = Property(bool, lambda self: self._toast_undo, notify=toastChanged)
    busy = Property(bool, lambda self: self._busy, notify=busyChanged)
    busyText = Property(str, lambda self: self._busy_text, notify=busyChanged)
    homePath = Property(str, lambda self: str(fsops.HOME), constant=True)
