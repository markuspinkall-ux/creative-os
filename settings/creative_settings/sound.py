"""Ton: Ausgabegerät (Lautsprecher/Kopfhörer), Mikrofon, Lautstärke,
App-Lautstärken (welches Programm über welches Gerät spielt), Geräteprofile
(z. B. HDMI statt analog) und eine Pegelanzeige fürs Mikrofon.

Arbeitet mit PipeWire über `pactl` (JSON-Ausgabe). Änderungen von außen
(z. B. Kopfhörer eingesteckt) kommen über `pactl subscribe` sofort an.
"""

import json
import re
import struct

from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot

from creative_shell.runner import Runner


def _volume_percent(vol):
    values = []
    for ch in (vol or {}).values():
        m = re.match(r"(\d+)%", str(ch.get("value_percent", "")))
        if m:
            values.append(int(m.group(1)))
    return round(sum(values) / len(values)) if values else 0


def parse_devices(text, default_name, skip_monitors=False):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    devices = []
    for d in data:
        name = d.get("name", "")
        if skip_monitors and name.endswith(".monitor"):
            continue
        devices.append({
            "index": d.get("index"),
            "name": name,
            "label": d.get("description") or name,
            "volume": _volume_percent(d.get("volume")),
            "muted": bool(d.get("mute")),
            "isDefault": name == default_name,
        })
    devices.sort(key=lambda d: (not d["isDefault"], d["label"].casefold()))
    return devices


def parse_streams(text, kind):
    """Laufende Wiedergaben (sink-inputs) bzw. Aufnahmen (source-outputs)."""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out = []
    for s in data:
        props = s.get("properties") or {}
        app = props.get("application.name") or props.get("media.name") or "Programm"
        # Eigene Mess-Streams nicht anzeigen
        if app in ("Creative Visualizer", "PulseAudio Volume Control") or props.get("media.role") == "test":
            continue
        if kind == "input" and props.get("application.process.binary") in ("parec",) and \
                "Visualizer" in (props.get("application.name") or ""):
            continue
        out.append({
            "index": s.get("index"),
            "app": app,
            "media": props.get("media.name") or "",
            "icon": props.get("application.icon_name") or (props.get("application.process.binary") or "").lower(),
            "device": s.get("sink") if kind == "output" else s.get("source"),
            "volume": _volume_percent(s.get("volume")),
            "muted": bool(s.get("mute")),
            "corked": bool(s.get("corked")),
        })
    out.sort(key=lambda x: x["app"].casefold())
    return out


def parse_cards(text):
    try:
        data = json.loads(text)
    except ValueError:
        return []
    cards = []
    for c in data:
        props = c.get("properties") or {}
        profiles = []
        for name, p in (c.get("profiles") or {}).items():
            if name == "off" or p.get("available") is False:
                continue
            profiles.append({"name": name, "label": p.get("description") or name})
        if len(profiles) < 2:
            continue                       # nichts auszuwählen
        profiles.sort(key=lambda p: -int((c.get("profiles") or {}).get(p["name"], {}).get("priority", 0)))
        active = c.get("active_profile", "")
        cards.append({"name": c.get("name", ""), "label": props.get("device.description") or c.get("name", ""),
                      "profiles": profiles, "active": active,
                      "activeLabel": next((p["label"] for p in profiles if p["name"] == active), active)})
    return cards


class SoundModel(QObject):
    changed = Signal()
    levelChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = Runner(self, force_c_locale=True)
        self._available = True
        self._outputs, self._inputs = [], []
        self._apps, self._cards = [], []
        self._level = 0.0
        self._meter = None
        self._default_sink = self._default_source = ""
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self.refresh)
        self._sub = QProcess(self)
        self._sub.readyReadStandardOutput.connect(self._on_event)
        self._sub.start("pactl", ["subscribe"])
        self.refresh()

    def _on_event(self):
        data = self._sub.readAllStandardOutput().data().decode("utf-8", "replace")
        if any(k in data for k in ("sink", "source", "server", "card", "sink-input")):
            self._debounce.start()

    @Slot()
    def refresh(self):
        self._run.run(["pactl", "get-default-sink"], self._on_default_sink)

    def _on_default_sink(self, code, out, _err):
        if code == 127:
            self._available = False
            self.changed.emit()
            return
        self._default_sink = out.strip()
        self._run.run(["pactl", "get-default-source"], self._on_default_source)

    def _on_default_source(self, _code, out, _err):
        self._default_source = out.strip()
        self._run.run(["pactl", "-f", "json", "list", "sinks"], self._on_sinks)

    def _on_sinks(self, _code, out, _err):
        self._outputs = parse_devices(out, self._default_sink)
        self._run.run(["pactl", "-f", "json", "list", "sources"], self._on_sources)

    def _on_sources(self, _code, out, _err):
        self._inputs = parse_devices(out, self._default_source, skip_monitors=True)
        self._run.run(["pactl", "-f", "json", "list", "sink-inputs"], self._on_apps)

    def _on_apps(self, _code, out, _err):
        self._apps = parse_streams(out, "output")
        self._run.run(["pactl", "-f", "json", "list", "cards"], self._on_cards)

    def _on_cards(self, _code, out, _err):
        self._cards = parse_cards(out)
        self.changed.emit()

    # ---- Aktionen -------------------------------------------------------------
    @Slot(str)
    def setOutput(self, name):
        self._run.run(["pactl", "set-default-sink", name], lambda *_: self._debounce.start())

    @Slot(str)
    def setInput(self, name):
        self._run.run(["pactl", "set-default-source", name], lambda *_: self._debounce.start())

    @Slot(str, int)
    def setOutputVolume(self, name, percent):
        self._run.run(["pactl", "set-sink-volume", name, f"{max(0, min(150, percent))}%"])

    @Slot(str, int)
    def setInputVolume(self, name, percent):
        self._run.run(["pactl", "set-source-volume", name, f"{max(0, min(150, percent))}%"])

    @Slot(str, bool)
    def setOutputMuted(self, name, muted):
        self._run.run(["pactl", "set-sink-mute", name, "1" if muted else "0"], lambda *_: self._debounce.start())

    @Slot(str, bool)
    def setInputMuted(self, name, muted):
        self._run.run(["pactl", "set-source-mute", name, "1" if muted else "0"], lambda *_: self._debounce.start())

    # ---- Apps -----------------------------------------------------------------------
    @Slot(int, str)
    def moveApp(self, index, sink):
        self._run.run(["pactl", "move-sink-input", str(index), sink], lambda *_: self._debounce.start())

    @Slot(int, int)
    def setAppVolume(self, index, percent):
        self._run.run(["pactl", "set-sink-input-volume", str(index), f"{max(0, min(150, percent))}%"])

    @Slot(int, bool)
    def setAppMuted(self, index, muted):
        self._run.run(["pactl", "set-sink-input-mute", str(index), "1" if muted else "0"],
                      lambda *_: self._debounce.start())

    @Slot(str, str)
    def setProfile(self, card, profile):
        self._run.run(["pactl", "set-card-profile", card, profile], lambda *_: self._debounce.start())

    # ---- Mikrofon-Pegel ------------------------------------------------------------------
    @Slot(bool)
    def setMeter(self, on):
        """Pegelanzeige fürs Mikrofon – nur solange die Ton-Seite offen ist."""
        if on and self._meter is None:
            self._meter = QProcess(self)
            self._meter.readyReadStandardOutput.connect(self._on_meter)
            self._meter.start("parec", ["--device=@DEFAULT_SOURCE@", "--rate=16000", "--channels=1",
                                        "--format=s16le", "--raw", "--latency-msec=50",
                                        "--client-name=Creative Systemsteuerung", "--stream-name=Pegel"])
        elif not on and self._meter is not None:
            self._meter.kill()
            self._meter.deleteLater()
            self._meter = None
            self._level = 0.0
            self.levelChanged.emit()

    def _on_meter(self):
        data = self._meter.readAllStandardOutput().data()
        n = len(data) // 2
        if n == 0:
            return
        samples = struct.unpack(f"<{n}h", data[: n * 2])
        peak = max(abs(s) for s in samples) / 32768.0
        # weich abfallen lassen
        self._level = max(peak, self._level * 0.75)
        self.levelChanged.emit()

    @Slot()
    def openBroadcast(self):
        from creative_shell.runner import spawn_detached
        spawn_detached(["creative-broadcast"])

    @Slot()
    def testSound(self):
        for f in ("/usr/share/sounds/freedesktop/stereo/bell.oga",
                  "/usr/share/sounds/freedesktop/stereo/complete.oga"):
            self._run.run(["pw-play", f])
            break

    available = Property(bool, lambda self: self._available, notify=changed)
    outputs = Property("QVariantList", lambda self: self._outputs, notify=changed)
    inputs = Property("QVariantList", lambda self: self._inputs, notify=changed)
    apps = Property("QVariantList", lambda self: self._apps, notify=changed)
    cards = Property("QVariantList", lambda self: self._cards, notify=changed)
    level = Property(float, lambda self: self._level, notify=levelChanged)
