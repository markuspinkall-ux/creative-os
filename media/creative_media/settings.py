"""Einstellungen des Players (~/.config/creative-os/media.json)."""

import json
import os
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal

DEFAULT_IPTV = "https://raw.githubusercontent.com/josxha/german-tv-m3u/main/german-tv.m3u"


def _path():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "creative-os" / "media.json"


class Settings(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = {"iptvSource": DEFAULT_IPTV, "volume": 0.7, "lastChannel": "", "navOpen": False}
        try:
            with _path().open(encoding="utf-8") as fh:
                stored = json.load(fh)
            if isinstance(stored, dict):
                for key in self._data:
                    if key in stored and (type(stored[key]) is type(self._data[key])
                                          or (type(self._data[key]) is float and type(stored[key]) is int)):
                        self._data[key] = stored[key]
        except (OSError, ValueError):
            pass

    def _save(self):
        path = _path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            print(f"creative-media: Einstellungen nicht gespeichert ({exc})")

    def _setter(key):
        def setter(self, value):
            if self._data.get(key) != value:
                self._data[key] = value
                self._save()
                self.changed.emit()
        return setter

    iptvSource = Property(str, lambda self: self._data["iptvSource"], _setter("iptvSource"), notify=changed)
    volume = Property(float, lambda self: float(self._data["volume"]), _setter("volume"), notify=changed)
    lastChannel = Property(str, lambda self: self._data["lastChannel"], _setter("lastChannel"), notify=changed)
    navOpen = Property(bool, lambda self: bool(self._data["navOpen"]), _setter("navOpen"), notify=changed)
