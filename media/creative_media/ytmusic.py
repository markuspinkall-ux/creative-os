"""YouTube Music im Creative Player: Top 10 und Suche, direkt abspielen.

Die Titel kommen über ytmusicapi (YouTube Music), der Ton über yt-dlp,
abgespielt wird im Player selbst – ohne Browser und ohne Werbung.
Fehlt ytmusicapi, wird ersatzweise über yt-dlp gesucht.
"""

import json
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    Qt,
    Signal,
    Slot,
)

# ytmusicapi liegt im Abbild in einem eigenen Ordner
for _vendor in (Path("/usr/lib/creative-media/vendor"), Path(__file__).resolve().parent.parent / "vendor"):
    if _vendor.is_dir() and str(_vendor) not in sys.path:
        sys.path.append(str(_vendor))

try:
    from ytmusicapi import YTMusic
except Exception:          # nicht installiert oder kaputt → Ersatzweg
    YTMusic = None

TITLE, ARTIST, DURATION, THUMB, VIDEO, RANK = range(Qt.ItemDataRole.UserRole + 1, Qt.ItemDataRole.UserRole + 7)
COUNTRY = "DE"


def _thumb(thumbs):
    """Größtes Vorschaubild (für die Liste reichen ~120 px, für die Leiste mehr)."""
    if not thumbs:
        return ""
    best = max(thumbs, key=lambda t: (t.get("width") or 0))
    url = best.get("url", "")
    # Google-Bilder lassen sich über die Adresse vergrößern
    if "=w" in url and "googleusercontent" in url:
        url = url.split("=w")[0] + "=w240-h240-l90-rj"
    return url


def _fmt(seconds):
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return ""
    return f"{s // 60}:{s % 60:02d}"


def _track(item):
    """Ein Eintrag aus ytmusicapi in unser Format."""
    vid = item.get("videoId")
    if not vid:
        return None
    artists = ", ".join(a.get("name", "") for a in (item.get("artists") or []) if a.get("name"))
    duration = item.get("duration") or _fmt(item.get("duration_seconds"))
    return {"title": item.get("title") or "Unbekannt", "artist": artists, "duration": duration or "",
            "thumb": _thumb(item.get("thumbnails")), "videoId": vid}


# ---- Quellen --------------------------------------------------------------------------
def _api():
    return YTMusic(language="de", location=COUNTRY) if YTMusic else None


def fetch_top(limit=10):
    api = _api()
    if api:
        try:
            charts = api.get_charts(country=COUNTRY)
            playlist = None
            # Neuere Fassungen: Liste von Wiedergabelisten („Top 100 Songs …“, „Top 100 Musikvideos …“)
            for key in ("songs", "videos", "trending"):
                part = charts.get(key)
                if isinstance(part, dict) and part.get("playlist"):
                    playlist = part["playlist"]
                elif isinstance(part, dict) and part.get("items"):
                    tracks = [t for t in (_track(i) for i in part["items"]) if t]
                    if tracks:
                        return tracks[:limit]
                elif isinstance(part, list):
                    for p in part:
                        if p.get("playlistId"):
                            playlist = p["playlistId"]
                            break
                if playlist:
                    break
            if playlist:
                if playlist.startswith("VL"):
                    playlist = playlist[2:]
                data = api.get_playlist(playlist, limit=limit)
                tracks = [t for t in (_track(i) for i in data.get("tracks", [])) if t]
                if tracks:
                    return tracks[:limit]
        except Exception as exc:
            print(f"creative-media: Top 10 über YouTube Music fehlgeschlagen ({exc})")
    return _ytdlp_search("Top Hits Deutschland aktuell", limit)


def search(query, limit=25):
    api = _api()
    if api:
        try:
            found = api.search(query, filter="songs", limit=limit)
            tracks = [t for t in (_track(i) for i in found) if t]
            if tracks:
                return tracks[:limit]
        except Exception as exc:
            print(f"creative-media: Suche über YouTube Music fehlgeschlagen ({exc})")
    return _ytdlp_search(query, limit)


def _ytdlp_search(query, limit):
    if not shutil.which("yt-dlp"):
        return []
    r = subprocess.run(
        ["yt-dlp", "--no-warnings", "--flat-playlist", "-J", f"ytsearch{limit}:{query}"],
        capture_output=True, text=True, timeout=40,
    )
    try:
        entries = json.loads(r.stdout).get("entries") or []
    except ValueError:
        return []
    out = []
    for e in entries:
        if not e.get("id"):
            continue
        out.append({"title": e.get("title") or "Unbekannt", "artist": e.get("channel") or e.get("uploader") or "",
                    "duration": _fmt(e.get("duration")), "thumb": _thumb(e.get("thumbnails")),
                    "videoId": e["id"]})
    return out


def stream_url(video_id):
    """Direkte Ton-Adresse für den Player (gilt einige Stunden)."""
    r = subprocess.run(
        ["yt-dlp", "--no-warnings", "--no-playlist", "-f", "bestaudio[ext=m4a]/bestaudio/best", "-g",
         f"https://music.youtube.com/watch?v={video_id}"],
        capture_output=True, text=True, timeout=40,
    )
    lines = [l for l in r.stdout.strip().splitlines() if l.startswith("http")]
    return lines[0] if lines else ""


# ---- Modell für die Oberfläche ---------------------------------------------------------------
class YtMusicModel(QAbstractListModel):
    changed = Signal()
    _loaded = Signal(str, object, str)          # mode, tracks, error
    _resolved = Signal(int, str, str)           # token, url, error
    ready = Signal(str, str, str, str)          # url, title, artist, thumb
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shown = []
        self._mode = "top"
        self._query = ""
        self._loading = False
        self._status = ""
        self._queue = []
        self._pos = -1
        self._token = 0
        self._resolving = False
        self._top_cache = None
        self._loaded.connect(self._on_loaded)
        self._resolved.connect(self._on_resolved)

    @staticmethod
    def _ok():
        return bool(shutil.which("yt-dlp"))

    # ---- Liste ------------------------------------------------------------------------
    def roleNames(self):
        return {TITLE: QByteArray(b"title"), ARTIST: QByteArray(b"artist"), DURATION: QByteArray(b"duration"),
                THUMB: QByteArray(b"thumb"), VIDEO: QByteArray(b"videoId"), RANK: QByteArray(b"rank")}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._shown)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._shown):
            return None
        t = self._shown[index.row()]
        return {TITLE: t["title"], ARTIST: t["artist"], DURATION: t["duration"], THUMB: t["thumb"],
                VIDEO: t["videoId"], RANK: index.row() + 1, Qt.ItemDataRole.DisplayRole: t["title"]}.get(role)

    def _run(self, mode, job):
        self._loading = True
        self._status = ""
        self.changed.emit()

        def work():
            try:
                self._loaded.emit(mode, job(), "")
            except Exception as exc:
                self._loaded.emit(mode, [], str(exc))
        threading.Thread(target=work, daemon=True).start()

    def _on_loaded(self, mode, tracks, error):
        if mode != self._mode:
            return
        self.beginResetModel()
        self._shown = list(tracks)
        self.endResetModel()
        if mode == "top" and tracks:
            self._top_cache = list(tracks)
        self._loading = False
        if error or not tracks:
            self._status = ("YouTube Music ist gerade nicht erreichbar. Besteht eine Internetverbindung?"
                            if mode == "top" or error else f"Nichts gefunden für „{self._query}“.")
        self.changed.emit()

    @Slot()
    def loadTop(self):
        self._mode, self._query = "top", ""
        if not self._ok():
            self._status = "Für YouTube Music fehlt yt-dlp."
            self.changed.emit()
            return
        if self._top_cache:
            self.beginResetModel()
            self._shown = list(self._top_cache)
            self.endResetModel()
            self._status = ""
            self.changed.emit()
            return
        self._run("top", fetch_top)

    @Slot()
    def reloadTop(self):
        self._top_cache = None
        self.loadTop()

    @Slot(str)
    def search(self, query):
        q = query.strip()
        if not q:
            self.loadTop()
            return
        self._mode, self._query = "search", q
        self._run("search", lambda: search(q))

    # ---- Abspielen --------------------------------------------------------------------------
    @Slot(int)
    def play(self, row):
        """Startet einen Titel aus der aktuellen Liste – die Liste wird zur Warteschlange."""
        if not 0 <= row < len(self._shown):
            return
        self._queue = list(self._shown)
        self._go(row)

    @Slot(int, bool)
    def step(self, delta, shuffle=False):
        if not self._queue:
            return
        if shuffle:
            import random
            row = random.randrange(len(self._queue))
        else:
            row = (self._pos + delta) % len(self._queue)
        self._go(row)

    def _go(self, row):
        self._pos = row
        self._token += 1
        token, track = self._token, self._queue[row]
        self._resolving = True
        self.changed.emit()

        def work():
            try:
                url = stream_url(track["videoId"])
                self._resolved.emit(token, url, "" if url else "kein Ton gefunden")
            except Exception as exc:
                self._resolved.emit(token, "", str(exc))
        threading.Thread(target=work, daemon=True).start()

    def _on_resolved(self, token, url, error):
        if token != self._token:
            return                                       # inzwischen anderer Titel gewählt
        self._resolving = False
        self.changed.emit()
        track = self._queue[self._pos] if 0 <= self._pos < len(self._queue) else None
        if url and track:
            self.ready.emit(url, track["title"], track["artist"], track["thumb"])
        else:
            self.failed.emit("Dieser Titel lässt sich gerade nicht abspielen.")

    @Slot()
    def clearQueue(self):
        self._queue, self._pos = [], -1
        self._token += 1
        self._resolving = False
        self.changed.emit()

    def _current(self):
        return self._queue[self._pos]["videoId"] if 0 <= self._pos < len(self._queue) else ""

    mode = Property(str, lambda self: self._mode, notify=changed)
    query = Property(str, lambda self: self._query, notify=changed)
    loading = Property(bool, lambda self: self._loading, notify=changed)
    resolving = Property(bool, lambda self: self._resolving, notify=changed)
    status = Property(str, lambda self: self._status, notify=changed)
    currentId = Property(str, _current, notify=changed)
    count = Property(int, lambda self: len(self._shown), notify=changed)
    queueCount = Property(int, lambda self: len(self._queue), notify=changed)
