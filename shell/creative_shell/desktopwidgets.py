"""Asynchronous RSS and weather data for the desktop."""

import json
import threading
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from . import config


def read(url):
    request = urllib.request.Request(url, headers={"User-Agent": "CreativeOS Desktop Widgets"})
    with urllib.request.urlopen(request, timeout=8) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("Antwort zu groß")
    return data


def rss(feeds):
    rows = []
    failed = 0
    for url in feeds:
        try:
            data = read(url)
            if b"<!DOCTYPE" in data.upper():
                raise ValueError("DTD nicht unterstützt")
            root = ET.fromstring(data)
            for entry in (root.findall("./channel/item") or root.findall("{*}entry"))[:4]:
                title = entry.find("{*}title")
                link = entry.find("{*}link")
                href = (link.get("href") or link.text or "").strip() if link is not None else ""
                if title is not None and urllib.parse.urlsplit(href).scheme in ("http", "https"):
                    rows.append({"title": "".join(title.itertext()).strip()[:220], "url": href})
        except (OSError, ValueError, ET.ParseError):
            failed += 1
    return rows[:12], "Einige Feeds konnten nicht geladen werden." if failed else ""


def weather(place):
    url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
        {"name": place, "count": 5, "language": "de"})
    results = json.loads(read(url)).get("results", [])
    if not results:
        raise ValueError("Ort nicht gefunden. Ort oder Postleitzahl eingeben.")
    location = results[0]
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": location["latitude"], "longitude": location["longitude"],
        "current": "temperature_2m,weather_code",
        "daily": "weather_code,temperature_2m_min,temperature_2m_max",
        "forecast_days": 2, "timezone": "auto",
    })
    data = json.loads(read(url))
    current, daily = data["current"], data["daily"]

    def condition(code):
        if code == 0:
            return "Sonnig"
        if code <= 3:
            return "Bewölkt"
        if code <= 48:
            return "Nebel"
        if code in (71, 73, 75, 77, 85, 86):
            return "Schnee"
        if code >= 95:
            return "Gewitter"
        return "Niederschlag"

    label = ", ".join(location[key] for key in ("name", "admin1", "country") if location.get(key))
    return [
        {"title": label},
        {"title": f"Jetzt: {current['temperature_2m']:g} °C · {condition(current['weather_code'])}"},
        {"title": f"Morgen: {daily['temperature_2m_min'][1]:g} bis {daily['temperature_2m_max'][1]:g} °C · "
                  + condition(daily["weather_code"][1])},
    ], ""


class DesktopWidget(QObject):
    changed = Signal()
    _ready = Signal(object)

    def __init__(self, kind):
        super().__init__()
        self._key = "desktopWidget" + kind
        self._weather = kind == "Weather"
        self._settings = config.load()[self._key]
        self._rows, self._message = [], ""
        self._busy = False
        self._ready.connect(self._apply)
        self._timer = QTimer(self)
        self._timer.setInterval(900_000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        QTimer.singleShot(0, self.refresh)

    def _save(self, **changes):
        self._settings.update(changes)
        config.set_value(self._key, self._settings)
        self.changed.emit()

    @Slot()
    def toggle(self):
        self._save(enabled=not self.enabled)
        self.refresh()

    @Slot(float, float)
    def setPos(self, x, y):
        self._save(x=x, y=y)

    @Slot(str, result=str)
    def saveInput(self, value):
        value = value.strip()
        if not self._weather:
            urls = list(dict.fromkeys(value.split()))
            if len(urls) > 5 or any(not u.startswith(("https://", "http://")) for u in urls):
                return "Bis zu fünf HTTP- oder HTTPS-Feed-Adressen eingeben."
            value = "\n".join(urls)
        self._rows = []
        self._message = ""
        self._save(value=value)
        self.refresh()
        return ""

    @Slot()
    def refresh(self):
        value = self.value
        if self._busy or not self.enabled or not value:
            return
        self._busy = True
        self._message = "Wird geladen …"
        self.changed.emit()

        def run():
            try:
                rows, message = weather(value) if self._weather else rss(value.splitlines())
            except (OSError, ValueError, KeyError, IndexError) as exc:
                rows, message = [], str(exc)
            self._ready.emit((value, rows, message))

        threading.Thread(target=run, daemon=True).start()

    def _apply(self, result):
        self._busy = False
        value, rows, message = result
        if value != self.value:
            self._message = ""
            self.changed.emit()
            self.refresh()
            return
        if rows:
            self._rows = rows
        self._message = message or ("Keine Einträge gefunden." if not rows else "")
        self.changed.emit()

    enabled = Property(bool, lambda self: bool(self._settings.get("enabled")), notify=changed)
    value = Property(str, lambda self: self._settings.get("value", ""), notify=changed)
    posX = Property(float, lambda self: self._settings.get("x", -1.0), notify=changed)
    posY = Property(float, lambda self: self._settings.get("y", -1.0), notify=changed)
    rows = Property("QVariantList", lambda self: self._rows, notify=changed)
    message = Property(str, lambda self: self._message, notify=changed)
