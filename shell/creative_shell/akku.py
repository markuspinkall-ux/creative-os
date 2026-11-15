"""Akku für Laptops: Ladestand, Laden/Entladen, Restzeit – aus /sys/class/power_supply.

Ohne Akku (Desktop-PC) ist alles unsichtbar. Bei 15 % und 5 % (nur beim Entladen) kommt
je einmal eine Mitteilung; nach dem Einstecken beginnt das von vorn.
"""

import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

ROOT = Path(os.environ.get("CREATIVE_POWER_SUPPLY", "/sys/class/power_supply"))
LOW = 15
CRITICAL = 5


def _read(path):
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _num(path):
    try:
        return float(_read(path))
    except ValueError:
        return None


def read_state(root=ROOT):
    """Alle Akkus zusammen (manche Laptops haben zwei) + Netzteil."""
    batteries, plugged = [], False
    try:
        entries = sorted(root.iterdir())
    except OSError:
        entries = []
    for d in entries:
        kind = _read(d / "type")
        if kind == "Mains" and _read(d / "online") == "1":
            plugged = True
        if kind != "Battery" or _read(d / "present") == "0" or _read(d / "scope") == "Device":
            continue                        # „Device“ = Maus/Controller-Akku, nicht der Laptop
        b = {"status": _read(d / "status")}
        # Energie (µWh/µW) oder Ladung (µAh/µA) – je nach Gerät
        for now, full, rate in (("energy_now", "energy_full", "power_now"), ("charge_now", "charge_full", "current_now")):
            if (d / now).exists():
                b["now"], b["full"], b["rate"] = _num(d / now), _num(d / full), _num(d / rate)
                break
        b["capacity"] = _num(d / "capacity")
        batteries.append(b)
    if not batteries:
        return {"present": False}
    now = sum(b.get("now") or 0 for b in batteries)
    full = sum(b.get("full") or 0 for b in batteries)
    rate = sum(abs(b.get("rate") or 0) for b in batteries)
    if full > 0:
        percent = round(100 * now / full)
    else:
        caps = [b["capacity"] for b in batteries if b["capacity"] is not None]
        percent = round(sum(caps) / len(caps)) if caps else 0
    percent = max(0, min(100, percent))
    states = {b["status"] for b in batteries}
    charging = "Charging" in states
    discharging = "Discharging" in states and not charging
    if discharging:
        plugged = False
    full_state = not discharging and not charging and (percent >= 99 or states <= {"Full", "Not charging"})
    minutes = None
    if rate > 0 and full > 0:
        if charging:
            minutes = round(60 * (full - now) / rate)
        elif discharging:
            minutes = round(60 * now / rate)
    if minutes is not None and not 0 < minutes < 48 * 60:
        minutes = None
    return {"present": True, "percent": percent, "charging": charging, "plugged": plugged or charging,
            "full": bool(full_state) and not charging, "minutes": minutes,
            "discharging": discharging}


def dauer(minutes):
    if minutes is None:
        return ""
    h, m = divmod(minutes, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


def status_text(s):
    if not s.get("present"):
        return ""
    if s["charging"]:
        return f"Lädt – voll in {dauer(s['minutes'])}" if s["minutes"] else "Lädt"
    if s["full"]:
        return "Voll geladen"
    if s["plugged"]:
        return "Am Netzteil"
    if s["minutes"]:
        return f"Noch etwa {dauer(s['minutes'])}"
    return "Im Akkubetrieb"


class Akku(QObject):
    changed = Signal()

    def __init__(self, parent=None, root=None, interval=15000):
        super().__init__(parent)
        self._root = Path(root) if root else ROOT
        self._s = {"present": False}
        self._warned = set()
        self.notifications = []           # für Tests: was gemeldet wurde
        self._timer = QTimer(self)
        self._timer.setInterval(interval)
        self._timer.timeout.connect(self.refresh)
        self.refresh()
        if self._s.get("present"):
            self._timer.start()
        else:
            # auch ohne Akku selten nachsehen (Akku eingesetzt, Gerät erst später erkannt)
            self._timer.setInterval(120000)
            self._timer.start()

    @Slot()
    def refresh(self):
        s = read_state(self._root)
        if s.get("present") and self._timer.interval() > 15000:
            self._timer.setInterval(15000)
        self._warn(s)
        if s != self._s:
            self._s = s
            self.changed.emit()

    def _warn(self, s):
        if not s.get("present") or not s.get("discharging"):
            self._warned.clear()             # eingesteckt: Warnungen wieder scharf
            return
        p = s["percent"]
        for level, title, body in ((CRITICAL, "Akku fast leer", "Nur noch {p} %. Bitte jetzt das Netzteil anschließen."),
                                   (LOW, "Akku schwach", "Noch {p} %{t}. Am besten bald das Netzteil anschließen.")):
            if p <= level and level not in self._warned:
                self._warned.update(x for x in (LOW, CRITICAL) if x >= level)
                rest = f" (etwa {dauer(s['minutes'])})" if s.get("minutes") else ""
                self._notify(title, body.format(p=p, t=rest), level == CRITICAL)
                break

    def _notify(self, title, body, critical):
        self.notifications.append((title, body))
        if shutil.which("notify-send"):
            args = ["notify-send", "-a", "Akku", "-i", "battery-caution" if critical else "battery-low",
                    "-u", "critical" if critical else "normal", title, body]
            try:
                subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass

    present = Property(bool, lambda self: bool(self._s.get("present")), notify=changed)
    percent = Property(int, lambda self: int(self._s.get("percent", 0)), notify=changed)
    charging = Property(bool, lambda self: bool(self._s.get("charging")), notify=changed)
    plugged = Property(bool, lambda self: bool(self._s.get("plugged")), notify=changed)
    full = Property(bool, lambda self: bool(self._s.get("full")), notify=changed)
    low = Property(bool, lambda self: bool(self._s.get("discharging")) and self._s.get("percent", 100) <= LOW, notify=changed)
    timeText = Property(str, lambda self: dauer(self._s.get("minutes")), notify=changed)
    statusText = Property(str, lambda self: status_text(self._s), notify=changed)
