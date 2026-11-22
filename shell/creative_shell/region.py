"""Regionen: Gibeon OS teilt – nur mit Zustimmung – anonym mit, aus welchem Land es genutzt wird.

Gemeldet wird ausschließlich das Land (zwei Buchstaben, z. B. „DE“), abgeleitet aus der
eingestellten Zeitzone (sonst aus der Sprache). Keine IP wird gespeichert, keine Kennung,
kein Name. Einmal pro Monat („aktiv in diesem Monat“), beim ersten Mal zusätzlich „neu
installiert“. Die Zahlen sieht nur der Entwickler im Entwickler-Widget.

Zustimmung: beim Einrichten (Willkommen) oder in Einstellungen › System › Datenschutz.
Gespeichert in ~/.config/creative-os/region.json.

Die Sammelstelle (ein kleiner Cloudflare Worker, tools/regionen-worker) steht in
/usr/share/creative-os/regionen.json – ist dort keine Adresse eingetragen, wird nichts gemeldet.
"""

import json
import os
import time
import urllib.request
from pathlib import Path

SYSTEM_CONF = Path("/usr/share/creative-os/regionen.json")
ZONE_TAB = ("/usr/share/zoneinfo/zone.tab", "/usr/share/zoneinfo/zone1970.tab")


def _config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "creative-os"


def conf_path():
    return _config_dir() / "region.json"


def load():
    try:
        data = json.loads(conf_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data):
    path = conf_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".neu")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    tmp.replace(path)


def consent():
    """True/False – oder None, solange noch nicht gefragt wurde."""
    v = load().get("melden")
    return v if isinstance(v, bool) else None


def set_consent(value):
    data = load()
    data["melden"] = bool(value)
    save(data)


def endpoint():
    try:
        url = json.loads(SYSTEM_CONF.read_text(encoding="utf-8")).get("url", "")
    except (OSError, ValueError):
        url = ""
    return os.environ.get("GIBEON_REGIONEN_URL", url).rstrip("/")


def timezone():
    tz = os.environ.get("TZ", "").lstrip(":")
    if tz:
        return tz
    try:
        link = os.readlink("/etc/localtime")
        if "zoneinfo/" in link:
            return link.split("zoneinfo/", 1)[1]
    except OSError:
        pass
    try:
        return Path("/etc/timezone").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def country_from_tz(tz, tables=ZONE_TAB):
    if not tz:
        return ""
    for table in tables:
        try:
            for line in Path(table).read_text(encoding="utf-8").splitlines():
                if line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 3 and parts[2] == tz:
                    return parts[0].split(",")[0].upper()
        except OSError:
            continue
    return ""


def country_from_lang(lang=None):
    lang = lang if lang is not None else (os.environ.get("LC_ALL") or os.environ.get("LANG") or "")
    lang = lang.split(".", 1)[0]
    if "_" in lang:
        cc = lang.split("_", 1)[1][:2].upper()
        if cc.isalpha() and len(cc) == 2:
            return cc
    return ""


def country():
    return country_from_tz(timezone()) or country_from_lang()


def due(data, month):
    return data.get("melden") is True and data.get("gemeldet") != month


def report_if_due(now=None):
    """Einmal im Monat melden (nur mit Zustimmung und eingetragener Sammelstelle)."""
    data = load()
    month = time.strftime("%Y-%m", time.localtime(now))
    url = endpoint()
    land = country()
    if not due(data, month) or not url or not land:
        return False
    body = json.dumps({"land": land, "monat": month, "neu": not data.get("je_gemeldet")}).encode()
    req = urllib.request.Request(url + "/melden", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "GibeonOS"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status >= 300:
                return False
    except OSError:
        return False
    data.update({"gemeldet": month, "je_gemeldet": True})
    save(data)
    return True


try:
    from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
except ImportError:
    QObject = None

if QObject is not None:
    import threading

    class RegionConsent(QObject):
        """Für Willkommen und Einstellungen: Schalter „Land anonym mitteilen“."""
        changed = Signal()

        def _get(self):
            return consent() is True

        def _set(self, value):
            set_consent(value)
            self.changed.emit()
            if value:
                threading.Thread(target=report_if_due, daemon=True).start()

        @Slot(bool)
        def setEnabled(self, value):
            self._set(value)

        enabled = Property(bool, _get, _set, notify=changed)
        asked = Property(bool, lambda self: consent() is not None, notify=changed)
        land = Property(str, lambda self: country(), constant=True)

    def start_reporting(parent):
        """In der Shell: kurz nach dem Start und dann täglich prüfen, ob die Monatsmeldung fällig ist."""
        def run():
            threading.Thread(target=report_if_due, daemon=True).start()
        timer = QTimer(parent)
        timer.setInterval(24 * 3600 * 1000)
        timer.timeout.connect(run)
        timer.start()
        QTimer.singleShot(60_000, run)
        return timer
