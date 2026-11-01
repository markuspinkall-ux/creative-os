"""Ton: Ausgabegerät (Lautsprecher/Kopfhörer), Mikrofon, Lautstärke.

Arbeitet mit PipeWire über `pactl` (JSON-Ausgabe). Änderungen von außen
(z. B. Kopfhörer eingesteckt) kommen über `pactl subscribe` sofort an.
"""

import json
import re

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
            "name": name,
            "label": d.get("description") or name,
            "volume": _volume_percent(d.get("volume")),
            "muted": bool(d.get("mute")),
            "isDefault": name == default_name,
        })
    devices.sort(key=lambda d: (not d["isDefault"], d["label"].casefold()))
    return devices


class SoundModel(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = Runner(self, force_c_locale=True)
        self._available = True
        self._outputs, self._inputs = [], []
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
        if any(k in data for k in ("sink", "source", "server", "card")):
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

    @Slot()
    def testSound(self):
        for f in ("/usr/share/sounds/freedesktop/stereo/bell.oga",
                  "/usr/share/sounds/freedesktop/stereo/complete.oga"):
            self._run.run(["pw-play", f])
            break

    available = Property(bool, lambda self: self._available, notify=changed)
    outputs = Property("QVariantList", lambda self: self._outputs, notify=changed)
    inputs = Property("QVariantList", lambda self: self._inputs, notify=changed)
