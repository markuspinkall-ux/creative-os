"""Musik- und Videobibliothek aus den eigenen Ordnern.

Durchsucht im Hintergrund die Ordner „Musik“ bzw. „Videos“ (so wie sie im
System eingestellt sind). Titel, Künstler, Album und Dauer kommen aus den
Datei-Tags, sonst aus dem Dateinamen.
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
    QModelIndex,
    QObject,
    Qt,
    QUrl,
    Signal,
    Slot,
)

try:
    import mutagen  # Tags auslesen (python3-mutagen)
except ImportError:
    mutagen = None

AUDIO_EXT = {".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wav", ".wma"}
VIDEO_EXT = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v", ".wmv", ".ts", ".mpg", ".mpeg"}

TITLE, SUBTITLE, ARTIST, ALBUM, DURATION, URL = range(Qt.ItemDataRole.UserRole + 1, Qt.ItemDataRole.UserRole + 7)


def user_dir(kind, fallback):
    if shutil.which("xdg-user-dir"):
        try:
            out = subprocess.run(["xdg-user-dir", kind], capture_output=True, text=True, timeout=3).stdout.strip()
            if out and out != str(Path.home()) and Path(out).is_dir():
                return Path(out)
        except (OSError, subprocess.SubprocessError):
            pass
    for name in fallback:
        p = Path.home() / name
        if p.is_dir():
            return p
    return Path.home() / fallback[0]


def fmt_duration(seconds):
    if not seconds or seconds <= 0:
        return ""
    seconds = int(round(seconds))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def read_item(path, video):
    title, artist, album, length = path.stem, "", "", 0
    if mutagen is not None:
        try:
            info = mutagen.File(str(path), easy=True)
            if info is not None:
                tags = info.tags or {}
                title = (tags.get("title") or [title])[0] or title
                artist = (tags.get("artist") or [""])[0]
                album = (tags.get("album") or [""])[0]
                length = getattr(info.info, "length", 0) or 0
        except Exception:  # kaputte Tags dürfen die Liste nie verhindern
            pass
    if video:
        subtitle = path.parent.name
    else:
        subtitle = " · ".join(x for x in (artist, album) if x) or path.parent.name
    return {
        "title": title, "subtitle": subtitle, "artist": artist, "album": album,
        "duration": fmt_duration(length), "url": QUrl.fromLocalFile(str(path)).toString(),
        "sort": (artist.casefold(), album.casefold(), title.casefold()) if not video else (title.casefold(),),
    }


class LibraryModel(QAbstractListModel):
    scanned = Signal(object)
    changed = Signal()

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self._video = kind == "video"
        self._folder = user_dir("VIDEOS" if self._video else "MUSIC",
                                ["Videos"] if self._video else ["Musik", "Music"])
        self._all, self._shown, self._filter = [], [], ""
        self._scanning = False
        self.scanned.connect(self._on_scanned)
        self.rescan()

    # ---- Einlesen -------------------------------------------------------------
    @Slot()
    def rescan(self):
        if self._scanning:
            return
        self._scanning = True
        self.changed.emit()
        threading.Thread(target=self._scan, daemon=True).start()

    def _scan(self):
        exts = VIDEO_EXT if self._video else AUDIO_EXT
        items = []
        if self._folder.is_dir():
            for root, _dirs, files in os.walk(self._folder):
                for name in files:
                    p = Path(root) / name
                    if p.suffix.lower() in exts:
                        items.append(read_item(p, self._video))
        items.sort(key=lambda i: i["sort"])
        self.scanned.emit(items)

    def _on_scanned(self, items):
        self._all = items
        self._scanning = False
        self._apply()

    def _apply(self):
        self.beginResetModel()
        terms = self._filter.casefold().split()
        if terms:
            self._shown = [i for i in self._all
                           if all(t in f"{i['title']} {i['artist']} {i['album']}".casefold() for t in terms)]
        else:
            self._shown = list(self._all)
        self.endResetModel()
        self.changed.emit()

    # ---- Model ----------------------------------------------------------------
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._shown)

    def roleNames(self):
        return {TITLE: QByteArray(b"title"), SUBTITLE: QByteArray(b"subtitle"), ARTIST: QByteArray(b"artist"),
                ALBUM: QByteArray(b"album"), DURATION: QByteArray(b"duration"), URL: QByteArray(b"url")}

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._shown):
            return None
        item = self._shown[index.row()]
        return {TITLE: item["title"], Qt.ItemDataRole.DisplayRole: item["title"], SUBTITLE: item["subtitle"],
                ARTIST: item["artist"], ALBUM: item["album"], DURATION: item["duration"],
                URL: item["url"]}.get(role)

    @Slot(int, result="QVariantMap")
    def get(self, row):
        if 0 <= row < len(self._shown):
            i = self._shown[row]
            return {"title": i["title"], "subtitle": i["subtitle"], "url": i["url"]}
        return {}

    def _get_filter(self):
        return self._filter

    def _set_filter(self, text):
        if text != self._filter:
            self._filter = text
            self._apply()

    filterText = Property(str, _get_filter, _set_filter, notify=changed)
    count = Property(int, lambda self: len(self._shown), notify=changed)
    total = Property(int, lambda self: len(self._all), notify=changed)
    scanning = Property(bool, lambda self: self._scanning, notify=changed)
    folder = Property(str, lambda self: str(self._folder), notify=changed)
