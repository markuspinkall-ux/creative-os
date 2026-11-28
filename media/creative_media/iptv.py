"""IPTV-Senderliste aus einer M3U-Quelle.

Wie im Team Eleven Media Player 1.4.0: voreingestellte deutsche Senderliste,
Suche, Kategorien, Aktualisieren. Dazu „Meine Senderlisten“: beliebig viele
Quellen – Internetadressen oder M3U-Dateien vom eigenen Rechner (Knopf
„M3U-Datei laden …“ mit dem Gibeon-Dateiwähler, Hineinziehen oder Doppelklick im Dateimanager). Geladene
Dateien werden in den Player kopiert, damit sie auch nach dem Verschieben oder
Löschen des Originals bleiben. Jede Liste wird zwischengespeichert, damit sie
beim nächsten Start sofort da ist.
"""

import hashlib
import os
import re
import shutil
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
STREAM_SCHEMES = ("http://", "https://", "rtmp://", "rtmps://", "rtsp://", "rtp://", "udp://", "mms://", "srt://")
M3U_SUFFIXES = (".m3u", ".m3u8")
MAX_BYTES = 20 * 1024 * 1024
DEFAULT_LIST_NAME = "Deutsche Sender (Standard)"


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "creative-media"


def cache_file(source):
    """Zwischenspeicher je Quelle – beim Wechseln der Liste bleibt jede erhalten."""
    key = hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]
    return cache_dir() / "iptv" / f"{key}.m3u"


def lists_dir():
    """Hierhin werden geladene M3U-Dateien kopiert."""
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "creative-media" / "iptv-listen"


def local_path(source):
    """Dateipfad aus „/pfad“ oder „file:///pfad“ – sonst None (Internetadresse)."""
    source = (source or "").strip()
    if source.startswith("file://"):
        from urllib.parse import unquote, urlparse
        return Path(unquote(urlparse(source).path))
    if source.startswith(("/", "~")):
        return Path(source).expanduser()
    return None


def is_m3u_file(path):
    return str(path).lower().endswith(M3U_SUFFIXES)


def decode(data):
    """UTF-8 (auch mit BOM); ältere Listen aus Windows-Programmen sind oft Latin-1."""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", "replace")


def read_local(path):
    with Path(path).open("rb") as fh:
        return decode(fh.read(MAX_BYTES))


def _name_from_url(url):
    tail = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"\.(m3u8?|ts|mpd)$", "", tail, flags=re.I)


def parse_m3u(text):
    """Liest erweiterte M3U-Listen (#EXTINF) und einfache Listen, die nur Adressen enthalten."""
    channels, pending, group = [], None, ""
    for raw in text.splitlines():
        line = raw.strip().lstrip("\ufeff")
        if not line:
            continue
        if line.startswith("#EXTINF"):
            attrs = dict(ATTR.findall(line))
            rest = ATTR.sub("", line)
            name = rest.split(",", 1)[1].strip() if "," in rest else ""
            pending = {"name": name or attrs.get("tvg-name", "").strip(),
                       "group": attrs.get("group-title", "").strip() or group,
                       "logo": attrs.get("tvg-logo", "")}
        elif line.startswith("#EXTGRP:"):
            group = line.split(":", 1)[1].strip()
            if pending is not None and not pending["group"]:
                pending["group"] = group
        elif line.startswith("#"):
            continue
        elif line.lower().startswith(STREAM_SCHEMES):
            ch = pending or {"name": _name_from_url(line), "group": group, "logo": ""}
            ch["url"] = line
            channels.append(ch)
            pending = None
        else:
            pending = None
    for n, ch in enumerate(channels, 1):
        ch["number"] = n
        if not ch["name"]:
            ch["name"] = f"Sender {n}"
    return channels


def list_name(source):
    """Anzeigename einer Quelle: Dateiname ohne Endung bzw. letzter Teil der Adresse."""
    path = local_path(source)
    tail = path.name if path else source.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"\.m3u8?$", "", tail, flags=re.I) or "Senderliste"


def normalize_lists(stored, current, default):
    """Gespeicherte Listen bereinigen; ältere Einstellungen (nur eine Quelle) übernehmen."""
    lists, seen = [], set()
    for item in stored if isinstance(stored, list) else []:
        if isinstance(item, dict) and isinstance(item.get("source"), str) and item["source"].strip():
            src = item["source"].strip()
            if src not in seen:
                seen.add(src)
                name = item.get("name") if isinstance(item.get("name"), str) else ""
                lists.append({"name": name.strip() or list_name(src), "source": src})
    if not lists:
        lists.append({"name": DEFAULT_LIST_NAME, "source": default})
        seen.add(default)
    if current and current not in seen:
        lists.append({"name": list_name(current), "source": current})
    return lists


def copy_into_library(path, target_dir=None):
    """Kopiert eine M3U-Datei in den Player (eindeutiger Name, gleiche Datei nicht doppelt)."""
    path = Path(path)
    target_dir = Path(target_dir or lists_dir())
    if target_dir in path.parents:
        return path                                   # liegt schon im Player
    target_dir.mkdir(parents=True, exist_ok=True)
    data = path.read_bytes()
    stem = re.sub(r"[^\w .()+-]", "_", path.stem).strip() or "senderliste"
    suffix = path.suffix.lower() if path.suffix.lower() in M3U_SUFFIXES else ".m3u"
    n = 1
    while True:
        target = target_dir / (f"{stem}{suffix}" if n == 1 else f"{stem} ({n}){suffix}")
        if not target.exists():
            break
        if target.read_bytes() == data:                # dieselbe Datei schon einmal geladen
            return target
        n += 1
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(target)
    return target


class IptvModel(QAbstractListModel):
    changed = Signal()
    loaded = Signal(object, str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._all, self._shown = [], []
        self._filter, self._category = "", ALL
        self._loading, self._status = False, ""
        self._generation = 0
        self.loaded.connect(self._on_loaded)
        from .settings import DEFAULT_IPTV
        self._default = DEFAULT_IPTV
        lists = normalize_lists(settings.iptvLists, settings.iptvSource, DEFAULT_IPTV)
        if lists != settings.iptvLists:
            settings.iptvLists = lists
        old = cache_dir() / "iptv.m3u"                  # Zwischenspeicher vor den Senderlisten
        if old.exists() and not cache_file(settings.iptvSource).exists():
            try:
                cache_file(settings.iptvSource).parent.mkdir(parents=True, exist_ok=True)
                old.replace(cache_file(settings.iptvSource))
            except OSError:
                pass
        self._apply()
        self._load_cached_or_reload()

    def _source(self):
        return self._settings.iptvSource

    def _load_cached_or_reload(self):
        source = self._source()
        cached = cache_file(source)
        fresh = False
        if local_path(source) is None and cached.exists():
            try:
                self._all = parse_m3u(read_local(cached))
                fresh = time.time() - cached.stat().st_mtime <= 86400
                self._status = "Liste ist aktuell" if fresh else "Gespeicherte Liste"
            except OSError:
                self._all = []
        else:
            self._all = []
        self._apply()
        if not fresh:
            self.reload()

    # ---- Laden ------------------------------------------------------------------
    @Slot()
    def reload(self):
        self._generation += 1
        self._loading = True
        self._status = "Senderliste wird geladen …"
        self.changed.emit()
        threading.Thread(target=self._download, args=(self._source(), self._generation), daemon=True).start()

    def _download(self, source, generation):
        try:
            path = local_path(source)
            if path is not None:
                if not path.exists():
                    self.loaded.emit((generation, None), "Die M3U-Datei wurde nicht gefunden.")
                    return
                text = read_local(path)
            else:
                req = urllib.request.Request(source, headers={"User-Agent": "GibeonPlayer/0.2"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    text = decode(resp.read(MAX_BYTES))
            channels = parse_m3u(text)
            if not channels:
                self.loaded.emit((generation, None), "In dieser Liste wurden keine Sender gefunden.")
                return
            if path is None:
                cached = cache_file(source)
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text(text, encoding="utf-8")
            self.loaded.emit((generation, channels), "")
        except Exception as exc:  # Netzwerkfehler sollen nie den Player stören
            self.loaded.emit((generation, None), f"Senderliste konnte nicht geladen werden ({type(exc).__name__}).")

    def _on_loaded(self, result, error):
        generation, channels = result
        if generation != self._generation:
            return                                      # inzwischen andere Liste gewählt
        self._loading = False
        if channels is not None:
            self._all = channels
            self._status = "Liste ist aktuell"
            self._apply()
        else:
            self._status = error
            self.changed.emit()

    # ---- Meine Senderlisten -----------------------------------------------------
    def _lists(self):
        current = self._source()
        return [{"name": item["name"], "source": item["source"], "current": item["source"] == current,
                 "isFile": local_path(item["source"]) is not None} for item in self._settings.iptvLists]

    def _add_list(self, source, name=""):
        lists = [dict(item) for item in self._settings.iptvLists]
        if not any(item["source"] == source for item in lists):
            lists.append({"name": name or list_name(source), "source": source})
            self._settings.iptvLists = lists

    @Slot(str)
    def selectList(self, source):
        if source and source != self._source():
            self._category = ALL
            self._settings.iptvSource = source
            self._load_cached_or_reload()
        elif source:
            self.reload()

    @Slot(str)
    def setSource(self, source):
        """Internetadresse (oder Dateipfad) eintragen – landet in „Meine Senderlisten“."""
        source = source.strip()
        if not source:
            return
        path = local_path(source)
        if path is not None:
            self.importFile(str(path))
            return
        if "://" not in source:
            source = "https://" + source
        self._add_list(source)
        self.selectList(source)

    @Slot(str, result=str)
    def importFile(self, path_or_url):
        """M3U-Datei vom Rechner laden. Gibt eine Fehlermeldung zurück (leer = geklappt)."""
        path = local_path(path_or_url) or Path(path_or_url)
        try:
            if not path.is_file():
                raise FileNotFoundError
            channels = parse_m3u(read_local(path))
        except OSError:
            channels = None
        if channels is None:
            self._status = "Die Datei konnte nicht gelesen werden."
            self.changed.emit()
            return self._status
        if not channels:
            self._status = f"In „{path.name}“ wurden keine Sender gefunden."
            self.changed.emit()
            return self._status
        try:
            stored = copy_into_library(path)
        except OSError:
            stored = path                                # notfalls direkt vom Original lesen
        source = str(stored)
        self._add_list(source, list_name(path.name))
        self._settings.iptvSource = source
        self._category = ALL
        self._all = channels
        self._generation += 1
        self._loading = False
        self._status = f"{len(channels)} Sender aus „{path.name}“ geladen"
        self._apply()
        return ""

    @Slot(str)
    def removeList(self, source):
        lists = [dict(item) for item in self._settings.iptvLists if item["source"] != source]
        path = local_path(source)
        if path is not None and lists_dir() in path.parents:
            try:
                path.unlink()
            except OSError:
                pass
        else:
            try:
                cache_file(source).unlink()
            except OSError:
                pass
        if not lists:
            lists = [{"name": DEFAULT_LIST_NAME, "source": self._default}]
        self._settings.iptvLists = lists
        if source == self._source():
            self.selectList(lists[0]["source"])
        else:
            self.changed.emit()

    @Slot(str, str)
    def renameList(self, source, name):
        name = name.strip()
        if not name:
            return
        lists = [dict(item, name=name) if item["source"] == source else dict(item)
                 for item in self._settings.iptvLists]
        self._settings.iptvLists = lists
        self.changed.emit()

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
    lists = Property("QVariantList", _lists, notify=changed)
    sourceName = Property(str, lambda self: next((i["name"] for i in self._settings.iptvLists
                                                  if i["source"] == self._source()),
                                                 list_name(self._source())), notify=changed)
