"""Downloadable widget data and the desktop Twitch/clock models."""

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from . import config

CLOCK_URL = ("https://raw.githubusercontent.com/markuspinkall-ux/creative-os/"
             "main/widgets/catalog/analog-clock.json")
CHANNEL = re.compile(r"[a-z0-9_]{1,25}")
DURATION = re.compile(r"\d+\s+(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?)(?:\b|$)", re.I)


def read_small(url):
    request = Request(url, headers={"User-Agent": "CreativeWidgets/1.0"})
    with urlopen(request, timeout=5) as response:
        data = response.read(4097)
    if len(data) > 4096:
        raise ValueError("Antwort zu groß.")
    return data.decode("utf-8").strip()


def clock_descriptor(raw):
    data = json.loads(raw)
    if not isinstance(data, dict) or data != {
        "id": "analog-clock", "version": 1, "face": "graphit"
    }:
        raise ValueError("Dieses Widget-Paket wird von Creative OS nicht unterstützt.")
    return data


def channels_from(text):
    names = []
    for token in re.split(r"[\s,]+", text.lower().strip()):
        if not token:
            continue
        name = re.sub(r"^https://(?:www\.)?twitch\.tv/", "", token).rstrip("/")
        if not CHANNEL.fullmatch(name):
            raise ValueError("Bitte Twitch-Benutzernamen oder Twitch-Kanal-Links eingeben.")
        if name not in names:
            names.append(name)
    if len(names) > 8:
        raise ValueError("Bis zu acht Twitch-Kanäle sind möglich.")
    return names


def twitch_status(name):
    offline = "creative-widgets-offline"
    query = urlencode({"offline_msg": offline})
    try:
        result = read_small(f"https://decapi.me/twitch/uptime/{name}?{query}")
    except (OSError, ValueError):
        return {"name": name, "status": "unknown"}
    return {"name": name, "status": (
        "offline" if result == offline else "live" if DURATION.match(result) else "unknown"
    )}


class WidgetExtras(QObject):
    changed = Signal()
    _ready = Signal(object)

    def __init__(self):
        super().__init__()
        self._settings = config.load()["desktopExtras"]
        self._rows = []
        self._busy = False
        self._ready.connect(self._apply)
        self._timer = QTimer(self)
        self._timer.setInterval(120_000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        QTimer.singleShot(0, self.refresh)

    def _save(self, **changes):
        settings = {**self._settings, **changes}
        if not config.set_value("desktopExtras", settings):
            return False
        self._settings = settings
        self.changed.emit()
        return True

    def installClock(self, raw):
        if not self._save(clock=clock_descriptor(raw), clockEnabled=True):
            raise ValueError("Das Widget konnte nicht gespeichert werden.")

    def setEnabled(self, name, enabled):
        if name == "clock" and not self.clockInstalled:
            raise ValueError("Lade zuerst die analoge Uhr herunter.")
        if name not in ("clock", "twitch"):
            raise ValueError("Unbekanntes Widget.")
        if not self._save(**{name + "Enabled": enabled}):
            raise ValueError("Die Einstellung konnte nicht gespeichert werden.")
        if name == "twitch" and enabled:
            self.refresh()

    def saveChannels(self, text):
        names = channels_from(text)
        if not self._save(channels=names):
            raise ValueError("Die Kanäle konnten nicht gespeichert werden.")
        self._rows = []
        self.changed.emit()
        self.refresh()

    def channel_names(self):
        saved = self._settings.get("channels", [])
        return tuple(n for n in saved[:8] if isinstance(n, str) and CHANNEL.fullmatch(n)) if isinstance(saved, list) else ()

    @Slot(str, float, float)
    def setPosition(self, name, x, y):
        if name in ("clock", "twitch"):
            self._save(**{name + "Pos": [max(0, min(1, x)), max(0, min(1, y))]})

    def _position(self, name, axis):
        value = self._settings.get(name + "Pos")
        if isinstance(value, list) and len(value) == 2 and all(
            type(n) in (float, int) and 0 <= n <= 1 for n in value
        ):
            return float(value[axis])
        return -1.0

    @Slot()
    def refresh(self):
        names = self.channel_names()
        if self._busy or not self.twitchEnabled or not names:
            return
        self._busy = True
        self.changed.emit()

        def work():
            with ThreadPoolExecutor(max_workers=4) as pool:
                rows = list(pool.map(twitch_status, names))
            self._ready.emit((names, rows))

        threading.Thread(target=work, daemon=True).start()

    def _apply(self, result):
        names, rows = result
        self._busy = False
        if names != self.channel_names():
            self.refresh()
        elif self.twitchEnabled:
            self._rows = rows
        self.changed.emit()

    clockInstalled = Property(bool, lambda self: self._settings.get("clock") == {
        "id": "analog-clock", "version": 1, "face": "graphit"
    }, notify=changed)
    clockEnabled = Property(bool, lambda self: self.clockInstalled and self._settings.get("clockEnabled", False), notify=changed)
    twitchEnabled = Property(bool, lambda self: bool(self._settings.get("twitchEnabled", False)), notify=changed)
    twitchRows = Property("QVariantList", lambda self: self._rows, notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    clockX = Property(float, lambda self: self._position("clock", 0), notify=changed)
    clockY = Property(float, lambda self: self._position("clock", 1), notify=changed)
    twitchX = Property(float, lambda self: self._position("twitch", 0), notify=changed)
    twitchY = Property(float, lambda self: self._position("twitch", 1), notify=changed)
