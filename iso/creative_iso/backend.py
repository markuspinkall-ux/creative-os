"""Creative Iso – Bedienung. Die eigentliche Arbeit macht /usr/libexec/creative-iso-helper
(über pkexec, mit Administratorrechten). Die Ausgabe wird Zeile für Zeile gelesen:
„@@ <prozent> <text>“ = Fortschritt, „@@ok <datei>“ = fertig, „@@fehler <text>“ = Fehler.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, QUrl, Signal, Slot

HELPER = "/usr/libexec/creative-iso-helper"


def default_outdir():
    try:
        out = subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True, timeout=3).stdout.strip()
        if out and Path(out) != Path.home():
            return str(Path(out) / "ISOs")
    except (OSError, subprocess.SubprocessError):
        pass
    return str(Path.home() / "ISOs")


def free_gb(path):
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    try:
        return shutil.disk_usage(p).free / 1e9
    except OSError:
        return 0.0


SYSTEM_MOUNTS = ("/", "/boot", "/boot/efi", "/efi", "/sysroot", "/var", "/home", "/var/home", "/usr", "/etc")


def usb_sticks():
    """USB-Sticks und Speicherkarten (nie das System-Laufwerk)."""
    try:
        out = subprocess.run(["lsblk", "-J", "-b", "-p", "-o", "PATH,TYPE,SIZE,MODEL,VENDOR,TRAN,RM,HOTPLUG,MOUNTPOINTS"],
                             capture_output=True, text=True, timeout=5).stdout
        data = json.loads(out).get("blockdevices", [])
    except (OSError, ValueError, subprocess.SubprocessError):
        return []

    def walk(n):
        yield n
        for c in n.get("children") or []:
            yield from walk(c)

    sticks = []
    for d in data:
        if d.get("type") != "disk" or not d.get("size"):
            continue
        if not ((d.get("tran") or "") == "usb" or d.get("rm") in (True, 1, "1") or d.get("hotplug") in (True, 1, "1")):
            continue
        mounts = [m for x in walk(d) for m in (x.get("mountpoints") or []) if m]
        if any(m in SYSTEM_MOUNTS or m.startswith("/sysroot") or m.startswith("/boot") for m in mounts):
            continue
        size = int(d["size"])
        name = " ".join(x for x in ((d.get("vendor") or "").strip(), (d.get("model") or "").strip()) if x) or "USB-Stick"
        gb = size / 1e9
        sticks.append({"device": d["path"], "name": name, "size": size,
                       "label": f"{name} · {gb:.0f} GB".replace(".", ",") if gb >= 10 else f"{name} · {gb:.1f} GB".replace(".", ",")})
    return sticks


class IsoMaker(QObject):
    changed = Signal()
    logChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        try:
            self._variant = Path("/usr/share/creative-os/variant").read_text().strip() or "amd"
        except OSError:
            self._variant = "amd"
        self._outdir = default_outdir()
        self._source = ""            # leer = Fedora-Netzinstallation herunterladen
        self._channel = "stabil"
        self._running = False
        self._percent = 0
        self._status = ""
        self._result = ""
        self._error = ""
        self._log = []
        self._proc = None
        self._buf = ""
        self._usb_iso = ""
        self._usb_dev = ""
        self._sticks = []
        self._last_iso = ""

    # ---- Einstellungen ----------------------------------------------------------------
    @Slot(str)
    def setVariant(self, v):
        if v in ("amd", "nvidia"):
            self._variant = v
            self.changed.emit()

    @Slot(str)
    def setChannel(self, c):
        if c in ("stabil", "test"):
            self._channel = c
            self.changed.emit()

    @Slot(str)
    def setSource(self, url):
        self._source = QUrl(url).toLocalFile() if url.startswith("file:") else url
        self.changed.emit()

    @Slot(str)
    def setOutdir(self, url):
        if url:
            self._outdir = QUrl(url).toLocalFile() if url.startswith("file:") else url
            self.changed.emit()

    # ---- USB-Stick -----------------------------------------------------------------------
    @Slot()
    def refreshUsb(self):
        sticks = usb_sticks()
        if sticks != self._sticks:
            self._sticks = sticks
            if self._usb_dev not in [s["device"] for s in sticks]:
                self._usb_dev = sticks[0]["device"] if len(sticks) == 1 else ""
            self.changed.emit()

    @Slot(str)
    def setUsbDevice(self, dev):
        self._usb_dev = dev
        self.changed.emit()

    @Slot(str)
    def setUsbIso(self, url):
        self._usb_iso = QUrl(url).toLocalFile() if url.startswith("file:") else url
        self.changed.emit()

    @Slot()
    def useResultForUsb(self):
        if self._result.endswith(".iso"):
            self._usb_iso = self._result
            self.changed.emit()

    @Slot()
    def makeUsb(self):
        if self._usb_iso and self._usb_dev:
            self._start(["usb", self._usb_iso, self._usb_dev])

    def _usb_fits(self):
        st = next((s for s in self._sticks if s["device"] == self._usb_dev), None)
        try:
            return bool(st) and os.path.getsize(self._usb_iso) <= st["size"]
        except OSError:
            return False

    # ---- Ablauf --------------------------------------------------------------------------
    def _start(self, args):
        if self._running:
            return
        self._running, self._percent, self._result, self._error = True, 0, "", ""
        self._status = "Warte auf dein Passwort …"
        self._log = []
        self._buf = ""
        self.changed.emit()
        self.logChanged.emit()
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        p.readyReadStandardOutput.connect(self._read)
        p.finished.connect(self._finished)
        self._proc = p
        p.start("pkexec", [HELPER] + args)

    @Slot()
    def makeFull(self):
        self._start(["full", self._outdir, str(os.getuid())])

    @Slot()
    def makeNet(self):
        self._start(["net", self._variant, self._channel, self._source or "download", self._outdir, str(os.getuid())])

    @Slot()
    def cancel(self):
        if self._running:
            self._status = "Wird abgebrochen …"
            self.changed.emit()
            QProcess.startDetached("pkexec", [HELPER, "cancel"])

    def _read(self):
        self._buf += bytes(self._proc.readAllStandardOutput()).decode("utf-8", "replace")
        *lines, self._buf = self._buf.split("\n")
        for raw in lines:
            line = raw.replace("\r", "").rstrip()
            if not line:
                continue
            if line.startswith("@@ok "):
                self._result = line[5:].strip()
            elif line.startswith("@@fehler "):
                self._error = line[9:].strip()
            elif line.startswith("@@ "):
                parts = line[3:].split(" ", 1)
                try:
                    self._percent = max(self._percent, int(parts[0]))
                except ValueError:
                    pass
                if len(parts) > 1:
                    self._status = parts[1]
            else:
                self._log.append(line[:400])
                if len(self._log) > 400:
                    self._log = self._log[-300:]
        self.changed.emit()
        self.logChanged.emit()

    def _finished(self, code, _status):
        self._read()
        self._running = False
        if not self._result and not self._error:
            self._error = ("Abgebrochen – es wurde nichts verändert." if code in (126, 127)
                           else "Die ISO konnte nicht erstellt werden – Details im Protokoll.")
        self._status = "Fertig!" if self._result else ""
        self.changed.emit()

    @Slot()
    def openFolder(self):
        target = str(Path(self._result).parent) if self._result else self._outdir
        Path(target).mkdir(parents=True, exist_ok=True)
        prog = ["creative-files", target] if shutil.which("creative-files") else ["xdg-open", target]
        subprocess.Popen(prog, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ---- Eigenschaften ----------------------------------------------------------------------
    variant = Property(str, lambda self: self._variant, notify=changed)
    channel = Property(str, lambda self: self._channel, notify=changed)
    source = Property(str, lambda self: self._source, notify=changed)
    sourceName = Property(str, lambda self: Path(self._source).name if self._source else "", notify=changed)
    outdir = Property(str, lambda self: self._outdir, notify=changed)
    outdirUrl = Property(str, lambda self: QUrl.fromLocalFile(self._outdir).toString(), notify=changed)
    freeSpace = Property(float, lambda self: round(free_gb(self._outdir), 1), notify=changed)
    systemFree = Property(float, lambda self: round(free_gb("/var/lib/containers"), 1), notify=changed)
    running = Property(bool, lambda self: self._running, notify=changed)
    percent = Property(int, lambda self: self._percent, notify=changed)
    status = Property(str, lambda self: self._status, notify=changed)
    result = Property(str, lambda self: self._result, notify=changed)
    error = Property(str, lambda self: self._error, notify=changed)
    sticks = Property("QVariantList", lambda self: self._sticks, notify=changed)
    usbDevice = Property(str, lambda self: self._usb_dev, notify=changed)
    usbIso = Property(str, lambda self: self._usb_iso, notify=changed)
    usbIsoName = Property(str, lambda self: Path(self._usb_iso).name if self._usb_iso else "", notify=changed)
    usbIsoSize = Property(str, lambda self: (f"{os.path.getsize(self._usb_iso) / 1e9:.1f} GB".replace(".", ",")
                                             if self._usb_iso and os.path.exists(self._usb_iso) else ""), notify=changed)
    usbFits = Property(bool, _usb_fits, notify=changed)
    log = Property(str, lambda self: "\n".join(self._log[-200:]), notify=logChanged)
