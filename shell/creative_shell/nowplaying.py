"""„Gerade läuft“ für die Taskleiste: Interpret und Titel des aktuellen Liedes.

Quellen:
  1. Creative Player (lokale Musik, YouTube Music) – schreibt nach
     $XDG_RUNTIME_DIR/creative-media/nowplaying.json
  2. Alle anderen Player über MPRIS (Brave, Spotify, VLC …)
Läuft nichts, ist die Anzeige leer.
"""

import json
import os
import subprocess
import threading
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from . import config


def _player_file():
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(base) / "creative-media" / "nowplaying.json"


def _busctl(*args, timeout=2):
    try:
        r = subprocess.run(["busctl", "--user", *args], capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _mpris_players():
    out = _busctl("list", "--json=short")
    try:
        names = [e.get("name", "") for e in json.loads(out or "[]")]
    except ValueError:
        names = []
    return [n for n in names if n.startswith("org.mpris.MediaPlayer2.")]


def _mpris_prop(name, prop):
    out = _busctl("get-property", "--json=short", name, "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", prop)
    try:
        return json.loads(out).get("data") if out else None
    except ValueError:
        return None


def _meta_value(meta, key):
    v = (meta or {}).get(key)
    if isinstance(v, dict):
        v = v.get("data")
    if isinstance(v, list):
        v = ", ".join(str(x) for x in v if x)
    return str(v or "").strip()


def read_now():
    """→ dict(title, artist, source) oder None."""
    # 1. Creative Player
    try:
        f = _player_file()
        if f.exists() and time.time() - f.stat().st_mtime < 3600:
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("playing") and d.get("title"):
                return {"title": d["title"], "artist": d.get("artist", ""), "source": "creative-player"}
    except (OSError, ValueError):
        pass
    # 2. MPRIS (andere Programme)
    for name in _mpris_players():
        if "creative" in name.lower():
            continue
        if _mpris_prop(name, "PlaybackStatus") != "Playing":
            continue
        meta = _mpris_prop(name, "Metadata") or {}
        title = _meta_value(meta, "xesam:title")
        artist = _meta_value(meta, "xesam:artist")
        if title:
            return {"title": title, "artist": artist, "source": name}
    return None


class NowPlaying(QObject):
    changed = Signal()
    _result = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._now = None
        self._busy = False
        self._result.connect(self._apply)
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        QTimer.singleShot(1200, self._tick)

    def _tick(self):
        if self._busy:
            return
        # In Systemsteuerung › Darstellung abschaltbar (gilt sofort)
        try:
            on = bool(config.load().get("taskbarNowPlaying", True))
        except Exception:
            on = True
        if not on:
            self._apply(None)
            return
        self._busy = True

        def work():
            try:
                self._result.emit(read_now())
            except Exception:
                self._result.emit(None)
        threading.Thread(target=work, daemon=True).start()

    def _apply(self, now):
        self._busy = False
        if now != self._now:
            self._now = now
            self.changed.emit()

    @Slot()
    def raiseSource(self):
        """Klick auf die Anzeige holt den Player nach vorn."""
        src = (self._now or {}).get("source", "")
        if src == "creative-player":
            subprocess.Popen(["creative-player"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif src:
            threading.Thread(target=lambda: _busctl("call", src, "/org/mpris/MediaPlayer2",
                                                    "org.mpris.MediaPlayer2", "Raise"), daemon=True).start()

    active = Property(bool, lambda self: self._now is not None, notify=changed)
    title = Property(str, lambda self: (self._now or {}).get("title", ""), notify=changed)
    artist = Property(str, lambda self: (self._now or {}).get("artist", ""), notify=changed)
