"""Creative Iso – Bedienung. Die eigentliche Arbeit macht /usr/libexec/creative-iso-helper
(über pkexec, mit Administratorrechten). Die Ausgabe wird Zeile für Zeile gelesen:
„@@ <prozent> <text>“ = Fortschritt, „@@ok <datei>“ = fertig, „@@fehler <text>“ = Fehler.
"""

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
    log = Property(str, lambda self: "\n".join(self._log[-200:]), notify=logChanged)
