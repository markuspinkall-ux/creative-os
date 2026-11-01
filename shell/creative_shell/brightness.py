"""Helligkeit für alle Bildschirme.

- Laptop-Displays über brightnessctl (Backlight)
- Externe Monitore über ddcutil (DDC/CI) – damit lassen sich auch deine drei
  Monitore direkt aus dem Tray regeln, ohne die Knöpfe am Gerät.

DDC ist langsam (bis ~0,5 s pro Befehl), darum laufen die Befehle in einer
Warteschlange und Schieberegler-Bewegungen werden zusammengefasst.
"""

from collections import deque

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from .runner import Runner


class BrightnessModel(QObject):
    displaysChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = Runner(self, force_c_locale=True)
        self._displays = []  # {"key","name","value","kind","target","max"}
        self._pending = {}
        self._queue = deque()
        self._ddc_busy = False
        self._loading = False

        self._flush = QTimer(self)
        self._flush.setSingleShot(True)
        self._flush.setInterval(250)
        self._flush.timeout.connect(self._apply_pending)
        self.refresh()

    # ---- Erkennen -----------------------------------------------------------
    @Slot()
    def refresh(self):
        if self._loading:
            return
        self._loading = True
        self._found = []
        self._run.run(["brightnessctl", "-m", "-l", "-c", "backlight"], self._on_backlight)

    def _on_backlight(self, code, out, _err):
        for line in out.splitlines():
            parts = line.split(",")
            if len(parts) >= 5 and parts[1] == "backlight":
                try:
                    value = int(parts[3].rstrip("%"))
                except ValueError:
                    continue
                self._found.append(
                    {"key": "bl:" + parts[0], "name": "Eingebauter Bildschirm", "value": value,
                     "kind": "backlight", "target": parts[0], "max": 100}
                )
        self._enqueue_ddc(["ddcutil", "detect", "--terse"], self._on_ddc_detect)

    def _on_ddc_detect(self, code, out, _err):
        monitors = []
        current = None
        for raw in out.splitlines():
            line = raw.strip()
            if line.startswith("Display "):
                current = {"display": line.split()[1], "model": ""}
                monitors.append(current)
            elif line.startswith("Invalid display"):
                current = None
            elif current is not None and line.startswith("Monitor:"):
                fields = line.split(":", 1)[1].strip().split(":")
                current["model"] = fields[1].strip() if len(fields) >= 2 else fields[0].strip()
        if not monitors:
            self._finish()
            return
        remaining = {"n": len(monitors)}
        for mon in monitors:
            self._enqueue_ddc(
                ["ddcutil", "getvcp", "10", "--display", mon["display"], "--terse"],
                lambda c, o, e, mon=mon: self._on_ddc_value(mon, o, remaining),
            )

    def _on_ddc_value(self, mon, out, remaining):
        parts = out.split()
        # Erwartet: VCP 10 C <aktuell> <maximum>
        if len(parts) >= 5 and parts[0] == "VCP" and parts[2] == "C":
            try:
                cur, mx = int(parts[3]), max(int(parts[4]), 1)
                name = mon["model"] or f"Monitor {mon['display']}"
                self._found.append(
                    {"key": "ddc:" + mon["display"], "name": name, "value": round(cur * 100 / mx),
                     "kind": "ddc", "target": mon["display"], "max": mx}
                )
            except ValueError:
                pass
        remaining["n"] -= 1
        if remaining["n"] == 0:
            self._finish()

    def _finish(self):
        self._found.sort(key=lambda d: (d["kind"] != "backlight", d["target"]))
        self._displays = self._found
        self._loading = False
        self.displaysChanged.emit()

    # ---- Setzen -------------------------------------------------------------
    @Slot(str, int)
    def setValue(self, key, percent):
        percent = max(1, min(100, int(percent)))  # nie ganz schwarz
        for d in self._displays:
            if d["key"] == key:
                d["value"] = percent
                self._pending[key] = d
        self._flush.start()

    def _apply_pending(self):
        pending, self._pending = self._pending, {}
        for d in pending.values():
            if d["kind"] == "backlight":
                self._run.run(["brightnessctl", "-q", "-d", d["target"], "set", f"{d['value']}%"])
            else:
                raw = str(round(d["value"] * d["max"] / 100))
                self._enqueue_ddc(["ddcutil", "setvcp", "10", raw, "--display", d["target"], "--noverify"])

    # ---- DDC-Warteschlange ----------------------------------------------------
    def _enqueue_ddc(self, args, callback=None):
        self._queue.append((args, callback))
        self._next_ddc()

    def _next_ddc(self):
        if self._ddc_busy or not self._queue:
            return
        self._ddc_busy = True
        args, callback = self._queue.popleft()

        def done(code, out, err):
            self._ddc_busy = False
            if callback:
                callback(code, out, err)
            self._next_ddc()

        self._run.run(args, done)

    displays = Property("QVariantList", lambda self: self._displays, notify=displaysChanged)
