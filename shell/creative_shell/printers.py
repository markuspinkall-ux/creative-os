"""Druckerstatus über CUPS (lpstat)."""

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from .runner import Runner, spawn_detached


class PrinterModel(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = Runner(self, force_c_locale=True)
        self._available = False
        self._name = ""
        self._state = "none"  # none | idle | printing | disabled
        self._jobs = 0
        self._printers = {}
        self._timer = QTimer(self)
        self._timer.setInterval(15000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    @Slot()
    def refresh(self):
        self._run.run(["lpstat", "-p"], self._on_printers)

    def _on_printers(self, code, out, _err):
        printers = {}
        for line in out.splitlines():
            if not line.startswith("printer "):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            name = parts[1]
            if "disabled" in line:
                printers[name] = "disabled"
            elif "now printing" in line:
                printers[name] = "printing"
            else:
                printers[name] = "idle"
        self._printers = printers
        self._run.run(["lpstat", "-d"], self._on_default)

    def _on_default(self, code, out, _err):
        name = ""
        if ":" in out and "no system default" not in out:
            name = out.split(":", 1)[1].strip()
        if not name and self._printers:
            name = sorted(self._printers)[0]
        self._name = name
        self._available = bool(self._printers)
        self._state = self._printers.get(name, "none")
        self._run.run(["lpstat", "-o"], self._on_jobs)

    def _on_jobs(self, code, out, _err):
        self._jobs = len([l for l in out.splitlines() if l.strip()])
        self.changed.emit()

    def _status_text(self):
        if not self._available:
            return "Kein Drucker eingerichtet"
        text = {"idle": "Bereit", "printing": "Druckt gerade", "disabled": "Angehalten"}.get(self._state, "Unbekannt")
        if self._jobs == 1:
            text += " · 1 Auftrag"
        elif self._jobs > 1:
            text += f" · {self._jobs} Aufträge"
        return text

    @Slot()
    def openSettings(self):
        if not spawn_detached(["creative-settings", "--page", "printers"]):
            if not spawn_detached(["system-config-printer"]):
                spawn_detached(["xdg-open", "http://localhost:631/"])

    available = Property(bool, lambda self: self._available, notify=changed)
    name = Property(str, lambda self: self._name.replace("_", " "), notify=changed)
    state = Property(str, lambda self: self._state, notify=changed)
    jobs = Property(int, lambda self: self._jobs, notify=changed)
    attention = Property(bool, lambda self: self._state == "disabled", notify=changed)
    statusText = Property(str, _status_text, notify=changed)
