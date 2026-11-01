"""IPTV-Senderliste aus einer M3U-Quelle.

Wie im Team Eleven Media Player 1.4.0: voreingestellte deutsche Senderliste,
Suche, Kategorien, eigene Quelle eintragbar, Aktualisieren. Die Liste wird
zwischengespeichert, damit sie auch beim nächsten Start sofort da ist.
"""

import os
import re
import threading
import time
import urllib.request
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    Qt,
    Signal,
    Slot,
)

NAME, GROUP, LOGO, URL, NUMBER = range(Qt.ItemDataRole.UserRole + 1, Qt.ItemDataRole.UserRole + 6)
ALL = "Alle"
ATTR = re.compile(r'([\w-]+)="([^"]*)"')


def cache_file():
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "creative-media" / "iptv.m3u"


def parse_m3u(text):
    channels, pending = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            attrs = dict(ATTR.findall(line))
            rest = ATTR.sub("", line)
            name = rest.split(",", 1)[1].strip() if "," in rest else ""
            pending = {"name": name or attrs.get("tvg-name", ""),
                       "group": attrs.get("group-title", "").strip(),
                       "logo": attrs.get("tvg-logo", "")}
        elif line.startswith("#"):
            continue
        elif pending is not None:
            if line.startswith(("http://", "https://", "rtmp://", "rtsp://")):
                pending["url"] = line
                channels.append(pending)
            pending = None
    for n, ch in enumerate(channels, 1):
        ch["number"] = n
        if not ch["name"]:
            ch["name"] = f"Sender {n}"
    return channels


class IptvModel(QAbstractListModel):
    changed = Signal()
    loaded = Signal(object, str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._all, self._shown = [], []
        self._filter, self._category = "", ALL
        self._loading, self._status = False, ""
        self.loaded.connect(self._on_loaded)
        cached = cache_file()
        if cached.exists():
            try:
                self._all = parse_m3u(cached.read_text(encoding="utf-8", errors="replace"))
                age = time.time() - cached.stat().st_mtime
                self._status = "Gespeicherte Liste" if age > 86400 else "Liste ist aktuell"
            except OSError:
                pass
        self._apply()
        if not self._all or (cached.exists() and time.time() - cached.stat().st_mtime > 86400):
            self.reload()

    # ---- Laden ------------------------------------------------------------------
    @Slot()
    def reload(self):
        if self._loading:
            return
        self._loading = True
        self._status = "Senderliste wird geladen …"
        self.changed.emit()
        source = self._settings.iptvSource
        threading.Thread(target=self._download, args=(source,), daemon=True).start()

    def _download(self, source):
        try:
            if source.startswith(("http://", "https://")):
                req = urllib.request.Request(source, headers={"User-Agent": "CreativePlayer/0.1"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    text = resp.read(20 * 1024 * 1024).decode("utf-8", "replace")
            else:
                text = Path(source.removeprefix("file://")).read_text(encoding="utf-8", errors="replace")
            channels = parse_m3u(text)
            if not channels:
                self.loaded.emit(None, "In dieser Quelle wurden keine Sender gefunden.")
                return
            path = cache_file()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            self.loaded.emit(channels, "")
        except Exception as exc:  # Netzwerkfehler sollen nie den Player stören
            self.loaded.emit(None, f"Senderliste konnte nicht geladen werden ({type(exc).__name__}).")

    def _on_loaded(self, channels, error):
        self._loading = False
        if channels is not None:
            self._all = channels
            self._status = "Liste ist aktuell"
            self._apply()
        else:
            self._status = error
            self.changed.emit()

    @Slot(str)
    def setSource(self, source):
        source = source.strip()
        if source and source != self._settings.iptvSource:
            self._settings.iptvSource = source
            self.reload()

    # ---- Filtern ----------------------------------------------------------------
    def _apply(self):
        self.beginResetModel()
        terms = self._filter.casefold().split()
        self._shown = [c for c in self._all
                       if (self._category == ALL or c["group"] == self._category)
                       and all(t in c["name"].casefold() for t in terms)]
        self.endResetModel()
        self.changed.emit()

    def _categories(self):
        groups = []
        for c in self._all:
            if c["group"] and c["group"] not in groups:
                groups.append(c["group"])
        return [ALL] + sorted(groups, key=str.casefold)

    def _set_filter(self, text):
        if text != self._filter:
            self._filter = text
            self._apply()

    def _set_category(self, cat):
        if cat != self._category:
            self._category = cat or ALL
            self._apply()

    # ---- Model ------------------------------------------------------------------
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._shown)

    def roleNames(self):
        return {NAME: QByteArray(b"name"), GROUP: QByteArray(b"group"), LOGO: QByteArray(b"logo"),
                URL: QByteArray(b"url"), NUMBER: QByteArray(b"number")}

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._shown):
            return None
        c = self._shown[index.row()]
        return {NAME: c["name"], Qt.ItemDataRole.DisplayRole: c["name"], GROUP: c["group"],
                LOGO: c["logo"], URL: c["url"], NUMBER: c["number"]}.get(role)

    @Slot(int, result="QVariantMap")
    def get(self, row):
        if 0 <= row < len(self._shown):
            c = self._shown[row]
            return {"title": f"{c['number']} · {c['name']}", "subtitle": c["group"] or "Live", "url": c["url"]}
        return {}

    @Slot(str, result=int)
    def indexOfUrl(self, url):
        return next((n for n, c in enumerate(self._shown) if c["url"] == url), -1)

    filterText = Property(str, lambda self: self._filter, _set_filter, notify=changed)
    category = Property(str, lambda self: self._category, _set_category, notify=changed)
    categories = Property("QVariantList", _categories, notify=changed)
    count = Property(int, lambda self: len(self._shown), notify=changed)
    total = Property(int, lambda self: len(self._all), notify=changed)
    loading = Property(bool, lambda self: self._loading, notify=changed)
    status = Property(str, lambda self: self._status, notify=changed)
    sourceName = Property(str, lambda self: self._settings.iptvSource.rstrip("/").rsplit("/", 1)[-1], notify=changed)
