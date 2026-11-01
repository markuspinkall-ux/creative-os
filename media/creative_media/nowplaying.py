"""Meldet der Taskleiste, was der Creative Player gerade spielt."""

import json
import os
from pathlib import Path

from PySide6.QtCore import QObject, Slot


def _file():
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    d = Path(base) / "creative-media"
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    return d / "nowplaying.json"


class NowPlayingWriter(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._last = None

    @Slot(str, str, bool)
    def update(self, title, artist, playing):
        data = {"title": title, "artist": artist, "playing": bool(playing and title)}
        if data == self._last:
            return
        self._last = data
        try:
            f = _file()
            tmp = f.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(f)
        except OSError:
            pass

    def clear(self):
        try:
            _file().unlink()
        except OSError:
            pass
