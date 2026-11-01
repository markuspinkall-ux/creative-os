"""YouTube Music im Creative Player – über die offizielle Webseite.

Abgespielt wird ausschließlich im offiziellen YouTube-Music-Player
(music.youtube.com, eingebettet). Es wird nichts heruntergeladen und keine
inoffizielle Schnittstelle benutzt. Die Favoriten sind Lesezeichen: Titel,
Interpret, Vorschaubild und die Video-ID, damit ein Klick das Lied wieder im
offiziellen Player öffnet.
"""

import json
import os
import shutil
from pathlib import Path
from urllib.parse import quote_plus

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    Qt,
    Signal,
    Slot,
)

HOME = "https://music.youtube.com/"
CHARTS = "https://music.youtube.com/charts"

TITLE, ARTIST, THUMB, VIDEO, URL = range(Qt.ItemDataRole.UserRole + 1, Qt.ItemDataRole.UserRole + 6)


def _fav_file():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "creative-os" / "ytmusic-favoriten.json"


def load_favorites():
    try:
        data = json.loads(_fav_file().read_text(encoding="utf-8"))
        return [t for t in data if isinstance(t, dict) and t.get("videoId")] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_favorites(favs):
    path = _fav_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(favs, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        print(f"creative-media: Favoriten nicht gespeichert ({exc})")


def remove_old_cache():
    """Frühere Fassungen haben Lieder zwischengespeichert – die werden gelöscht."""
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    d = Path(base) / "creative-media" / "ytmusic"
    if d.is_dir():
        shutil.rmtree(d, ignore_errors=True)


def watch_url(video_id):
    return f"https://music.youtube.com/watch?v={video_id}"


def search_url(query):
    return f"https://music.youtube.com/search?q={quote_plus(query)}"


class YtMusicModel(QAbstractListModel):
    changed = Signal()
    openUrl = Signal(str)            # → Webansicht lädt diese Seite
    command = Signal(str)            # → Webansicht: play | pause | toggle | next | prev | stop

    def __init__(self, parent=None):
        super().__init__(parent)
        self._favs = load_favorites()
        self._now = {}               # gerade laufendes Lied (von der Webseite gemeldet)
        self._playing = False
        self._autoplay = False
        remove_old_cache()

    # ---- Liste der Favoriten ---------------------------------------------------------------
    def roleNames(self):
        return {TITLE: QByteArray(b"title"), ARTIST: QByteArray(b"artist"), THUMB: QByteArray(b"thumb"),
                VIDEO: QByteArray(b"videoId"), URL: QByteArray(b"url")}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._favs)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._favs):
            return None
        f = self._favs[index.row()]
        return {TITLE: f.get("title", ""), ARTIST: f.get("artist", ""), THUMB: f.get("thumb", ""),
                VIDEO: f["videoId"], URL: watch_url(f["videoId"]),
                Qt.ItemDataRole.DisplayRole: f.get("title", "")}.get(role)

    def _is_fav(self, vid):
        return bool(vid) and any(f["videoId"] == vid for f in self._favs)

    @Slot(str, result=bool)
    def isFavorite(self, vid):
        return self._is_fav(vid)

    @Slot()
    def toggleCurrentFavorite(self):
        vid = self._now.get("videoId")
        if not vid:
            return
        if self._is_fav(vid):
            self.removeFavorite(vid)
        else:
            self.beginInsertRows(QModelIndex(), 0, 0)
            self._favs.insert(0, {"title": self._now.get("title", ""), "artist": self._now.get("artist", ""),
                                  "thumb": self._now.get("thumb", ""), "videoId": vid, "duration": ""})
            self.endInsertRows()
            save_favorites(self._favs)
            self.changed.emit()

    @Slot(str)
    def removeFavorite(self, vid):
        for i, f in enumerate(self._favs):
            if f["videoId"] == vid:
                self.beginRemoveRows(QModelIndex(), i, i)
                del self._favs[i]
                self.endRemoveRows()
                save_favorites(self._favs)
                self.changed.emit()
                return

    # ---- Webseite steuern ---------------------------------------------------------------------
    @Slot(str)
    def playFavorite(self, vid):
        self._autoplay = False
        self.openUrl.emit(watch_url(vid))

    @Slot(str)
    def search(self, query):
        self._autoplay = False
        self.openUrl.emit(search_url(query))

    def search_and_play(self, query):
        """Sprachassistent: suchen und das erste Ergebnis im offiziellen Player starten."""
        self._autoplay = True
        self.openUrl.emit(search_url(query))

    @Slot(result=bool)
    def takeAutoplay(self):
        a, self._autoplay = self._autoplay, False
        return a

    @Slot("QVariantMap")
    def reportNow(self, info):
        """Die Webseite meldet alle 2 s, was gerade läuft (Titel, Interpret, Bild)."""
        info = dict(info or {})
        now = {"title": info.get("title") or "", "artist": info.get("artist") or "",
               "thumb": info.get("thumb") or "", "videoId": info.get("videoId") or ""}
        playing = bool(info.get("playing"))
        if now != self._now or playing != self._playing:
            self._now, self._playing = now, playing
            self.changed.emit()

    @Slot(str)
    def send(self, cmd):
        self.command.emit(cmd)

    # ---- Eigenschaften ---------------------------------------------------------------------------
    home = Property(str, lambda self: HOME, constant=True)
    charts = Property(str, lambda self: CHARTS, constant=True)
    favoriteCount = Property(int, lambda self: len(self._favs), notify=changed)
    nowTitle = Property(str, lambda self: self._now.get("title", ""), notify=changed)
    nowArtist = Property(str, lambda self: self._now.get("artist", ""), notify=changed)
    nowThumb = Property(str, lambda self: self._now.get("thumb", ""), notify=changed)
    nowVideo = Property(str, lambda self: self._now.get("videoId", ""), notify=changed)
    playing = Property(bool, lambda self: self._playing, notify=changed)
    currentFavorite = Property(bool, lambda self: self._is_fav(self._now.get("videoId", "")), notify=changed)
