"""Laufwerke: Platten anzeigen (Bauart, Größe, Zustand), neue Platte
einrichten, Zusatzplatten beim Start verbinden.

Gelesen wird ohne Rechte (lsblk, UDisks); Änderungen macht
/usr/libexec/creative-drives-helper über pkexec (fragt nach dem Passwort).
"""

import json
import re
import subprocess
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from creative_shell.runner import Runner, spawn_detached

HELPER = "/usr/libexec/creative-drives-helper"
SYSTEM_MOUNTS = ("/", "/sysroot", "/var", "/home", "/var/home", "/boot", "/boot/efi", "/efi")


def fmt_size(b):
    if not b:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1000 or unit == "TB":
            return (f"{b:.0f}" if b >= 100 or unit in ("B", "KB") else f"{b:.1f}".replace(".", ",")) + " " + unit
        b /= 1000
    return "?"


def kind(tran, rota, path):
    if (tran or "").lower() == "nvme" or "nvme" in path:
        return "M2"
    if (tran or "").lower() == "usb":
        return "USB-Laufwerk"
    if rota in (False, 0, "0"):
        return "SSD"
    if rota in (True, 1, "1"):
        return "Festplatte"
    return "Laufwerk"


def fstab_uuids():
    try:
        text = Path("/etc/fstab").read_text(encoding="utf-8")
    except OSError:
        return set()
    return set(re.findall(r"^UUID=([0-9A-Fa-f-]+)\s", text, re.M))


def health(device):
    """(stufe, text): ok | warn | bad | unknown"""
    try:
        info = subprocess.run(["udisksctl", "info", "-b", device], capture_output=True, text=True, timeout=5).stdout
        m = re.search(r"^\s*Drive:\s+'(/org/freedesktop/UDisks2/drives/[^']+)'", info, re.M)
        if not m:
            return "unknown", "Keine Angabe"
        drv = subprocess.run(["udisksctl", "info", "-o", m.group(1)], capture_output=True, text=True,
                             timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return "unknown", "Keine Angabe"
    if "NVMe.Controller" in drv:
        crit = re.search(r"SmartCriticalWarning:\s*(.*)", drv)
        if crit and crit.group(1).strip() not in ("", "[]"):
            return "bad", "Warnung der SSD – Daten bald sichern!"
        return "ok", "Gesund"
    failing = re.search(r"SmartFailing:\s*(\w+)", drv)
    if not failing:
        return "unknown", "Keine Angabe"
    if failing.group(1) == "true":
        return "bad", "Fällt bald aus – Daten sofort sichern!"
    bad = re.search(r"SmartNumBadSectors:\s*(\d+)", drv)
    if bad and int(bad.group(1)) > 0:
        return "warn", f"{bad.group(1)} defekte Sektoren – im Auge behalten"
    return "ok", "Gesund"


def list_disks():
    try:
        out = subprocess.run(["lsblk", "-J", "-b", "-p", "-o",
                              "PATH,TYPE,SIZE,MODEL,TRAN,ROTA,RM,HOTPLUG,FSTYPE,LABEL,UUID,MOUNTPOINTS,FSUSED,FSSIZE"],
                             capture_output=True, text=True, timeout=5).stdout
        data = json.loads(out)
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    auto = fstab_uuids()
    disks = []

    def walk(nodes):
        for n in nodes or []:
            yield n
            yield from walk(n.get("children"))

    for d in data.get("blockdevices", []):
        if d.get("type") != "disk" or d["path"].startswith(("/dev/zram", "/dev/loop", "/dev/sr")):
            continue
        parts = []
        system = False
        for p in walk(d.get("children")):
            mps = [m for m in (p.get("mountpoints") or []) if m]
            if any(m in SYSTEM_MOUNTS or m.startswith("/sysroot") for m in mps):
                system = True
            if not p.get("fstype") or p.get("fstype") in ("swap",) or any(m.startswith("/boot") for m in mps):
                continue
            size = int(p.get("fssize") or 0) or None
            used = int(p.get("fsused") or 0)
            parts.append({
                "device": p["path"], "label": p.get("label") or "", "fstype": p.get("fstype") or "",
                "mount": next((m for m in mps if not m.startswith("/sysroot")), ""),
                "automount": (p.get("uuid") or "") in auto,
                "usage": f"{fmt_size(size - used)} frei von {fmt_size(size)}" if size else "",
                "fraction": used / size if size else 0,
            })
        removable = bool(d.get("rm")) or bool(d.get("hotplug"))
        lvl, text = health(d["path"]) if not removable else ("unknown", "")
        disks.append({
            "device": d["path"], "kind": "Creative OS" if system else kind(d.get("tran"), d.get("rota"), d["path"]),
            "model": (d.get("model") or "").strip(), "size": fmt_size(int(d.get("size") or 0)),
            "system": system, "removable": removable, "parts": [] if system else parts,
            "empty": not parts and not system, "health": lvl, "healthText": text,
        })
    disks.sort(key=lambda x: (not x["system"], x["removable"], x["device"]))
    return disks


class DrivesModel(QObject):
    changed = Signal()
    messageChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = Runner(self, force_c_locale=True)
        self._disks = []
        self._busy = False
        self._message = ""
        self.refresh()

    @Slot()
    def refresh(self):
        self._disks = list_disks()
        self.changed.emit()

    def _helper(self, args, ok_text):
        if self._busy:
            return
        self._busy = True
        self._set_message("Einen Moment …")
        self.changed.emit()

        def done(code, out, _err):
            self._busy = False
            try:
                res = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
            except ValueError:
                res = {}
            if code in (126, 127) and not res:
                self._set_message("Abgebrochen – es wurde nichts verändert.")
            elif res.get("ok"):
                self._set_message(ok_text)
            else:
                self._set_message(res.get("error") or "Das hat nicht geklappt.")
            QTimer.singleShot(500, self.refresh)

        self._run.run(["pkexec", HELPER] + args, done)

    @Slot(str, str, bool)
    def setup(self, device, name, windows):
        name = name.strip() or "Daten"
        self._helper(["setup", device, name, "exfat" if windows else "ext4"],
                     f"Fertig! „{name}“ ist eingerichtet und erscheint in „Dateien“.")

    @Slot(str, bool)
    def setAutomount(self, part, on):
        self._helper(["automount", part, "on" if on else "off"],
                     "Wird jetzt bei jedem Start verbunden." if on else "Wird beim Start nicht mehr verbunden.")

    @Slot()
    def openExpert(self):
        spawn_detached(["gnome-disks"])

    @Slot(str)
    def openFolder(self, path):
        if path:
            spawn_detached(["creative-files", path])

    def _set_message(self, t):
        self._message = t
        self.messageChanged.emit()

    disks = Property("QVariantList", lambda self: self._disks, notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    message = Property(str, lambda self: self._message, notify=messageChanged)
    expertAvailable = Property(bool, lambda self: Path("/usr/bin/gnome-disks").exists(), constant=True)
