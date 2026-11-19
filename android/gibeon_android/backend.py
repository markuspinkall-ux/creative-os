"""Android-Apps – Bedienung für Waydroid.

Einrichten, Grafik, Google-Geräte-ID und Entfernen macht /usr/libexec/gibeon-android-helper
(über pkexec, mit Administratorrechten). Starten, Play Store, APKs installieren und Beenden
laufen als normaler Benutzer direkt über `waydroid`.

Ausgabe des Hilfsprogramms: „@@ <prozent> <text>“ = Fortschritt, „@@ok <text>“ = fertig,
„@@fehler <text>“ = Fehler. Alles andere ist Protokoll.
"""

import configparser
import re
import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication

HELPER = "/usr/libexec/gibeon-android-helper"
CFG = Path("/var/lib/waydroid/waydroid.cfg")
IMAGES = (Path("/var/lib/waydroid/images/system.img"), Path("/etc/waydroid-extra/images/system.img"),
          Path("/usr/share/waydroid-extra/images/system.img"))
REGISTER_URL = "https://www.google.com/android/uncertified"
STORE = "com.android.vending"
CONF_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "gibeon-android"
APPS_DIR = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "applications"
DL = re.compile(r"([\d.]+)\s*MB\s*/\s*([\d.]+)\s*MB")
GOOD_DRIVERS = {"i915": "Intel-Grafik", "xe": "Intel-Grafik", "amdgpu": "AMD-Grafik", "radeon": "AMD-Grafik",
                "virtio-pci": "VM-Grafik", "virtio_gpu": "VM-Grafik"}


def graphics_probe():
    """(art, text): art = hw (beschleunigt), sw (nur NVIDIA → Software) oder none."""
    found_nvidia = False
    for r in sorted(Path("/sys/class/drm").glob("renderD*")):
        try:
            drv = (r / "device" / "driver").resolve().name
        except OSError:
            continue
        if drv in GOOD_DRIVERS:
            return "hw", f"{GOOD_DRIVERS[drv]} – mit Beschleunigung"
        if drv.startswith("nvidia") or drv == "nouveau":
            found_nvidia = True
    if found_nvidia:
        return "sw", "Nur NVIDIA gefunden – Android läuft ohne Grafikbeschleunigung (für Apps okay, für Spiele zu langsam)"
    return "none", "Keine passende Grafik gefunden"


def read_cfg():
    cfg = configparser.ConfigParser(interpolation=None, strict=False)
    cfg.optionxform = str
    try:
        cfg.read(CFG)
    except (configparser.Error, OSError):
        pass
    return cfg


class Android(QObject):
    changed = Signal()
    logChanged = Signal()

    def __init__(self, selftest=False, parent=None):
        super().__init__(parent)
        try:
            self._variant = Path("/usr/share/creative-os/variant").read_text().strip() or "amd"
        except OSError:
            self._variant = "amd"
        self._gfx, self._gfx_text = graphics_probe()
        self._installed = shutil.which("waydroid") is not None
        self._setup = False
        self._google = False
        self._session = "STOPPED"     # STOPPED | STARTING | RUNNING
        self._starting_ticks = 0
        self._pending = []            # Aufgaben, sobald Android läuft: ("store",) ("full",) ("apk", pfad)
        self._busy = ""               # einrichten | gsf | entfernen | grafik
        self._percent = 0
        self._status = ""
        self._result = ""
        self._error = ""
        self._message = ""
        self._gsf = ""
        self._log = []
        self._proc = None
        self._buf = ""
        self._dl_phase = 0
        self._dl_last = 0.0
        self._choice = "google"
        self._apps = 0
        self._refresh_static()
        self._status_proc = None
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self._poll)
        if not selftest:
            self._timer.start()
            QTimer.singleShot(0, self._poll)

    # ---- Zustand ---------------------------------------------------------------------------
    def _refresh_static(self):
        self._setup = CFG.exists() and any(p.exists() for p in IMAGES)
        cfg = read_cfg()
        ota = cfg.get("waydroid", "system_ota", fallback="") + cfg.get("waydroid", "system_type", fallback="")
        self._google = "GAPPS" in ota.upper()
        try:
            self._apps = len(list(APPS_DIR.glob("waydroid.*.desktop")))
        except OSError:
            self._apps = 0

    def _poll(self):
        before = (self._setup, self._google, self._apps)
        self._refresh_static()
        if before != (self._setup, self._google, self._apps):
            self.changed.emit()
        if not (self._installed and self._setup) or self._status_proc is not None:
            return
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        p.finished.connect(lambda *_: self._status_done(p))
        self._status_proc = p
        p.start("waydroid", ["status"])

    def _status_done(self, p):
        out = bytes(p.readAll()).decode("utf-8", "replace")
        self._status_proc = None
        p.deleteLater()
        running = bool(re.search(r"Session:\s*RUNNING", out))
        old = self._session
        if running:
            self._session = "RUNNING"
            self._starting_ticks = 0
        elif self._session == "STARTING":
            self._starting_ticks += 1
            if self._starting_ticks > 40:           # etwa 2 Minuten
                self._session = "STOPPED"
                self._pending = []
                self._error = "Android ist nicht gestartet. Einmal abmelden und wieder anmelden, dann nochmal versuchen."
        else:
            self._session = "STOPPED"
        if self._session == "RUNNING" and old != "RUNNING":
            self._first_run()
            self._run_pending()
        if old != self._session:
            self.changed.emit()

    def _first_run(self):
        """Android-Apps als eigene Fenster statt in einem großen Android-Bildschirm."""
        flag = CONF_DIR / "fenster"
        if flag.exists():
            return
        try:
            CONF_DIR.mkdir(parents=True, exist_ok=True)
            subprocess.run(["waydroid", "prop", "set", "persist.waydroid.multi_windows", "true"],
                           capture_output=True, timeout=15)
            flag.write_text("1\n")
        except (OSError, subprocess.SubprocessError):
            pass

    def _run_pending(self):
        jobs, self._pending = self._pending, []
        for job in jobs:
            if job[0] == "store":
                self._detached(["app", "launch", STORE])
            elif job[0] == "full":
                self._detached(["show-full-ui"])
            elif job[0] == "apk":
                self._install_apk(job[1])

    @staticmethod
    def _detached(args):
        QProcess.startDetached("waydroid", args)

    def _when_running(self, job):
        if not self._setup:
            return
        self._error = ""
        if self._session == "RUNNING":
            self._pending = [job]
            self._run_pending()
        else:
            self._pending.append(job)
            self.startAndroid()
        self.changed.emit()

    # ---- Bedienung als Benutzer --------------------------------------------------------------
    @Slot()
    def startAndroid(self):
        if not self._setup or self._session != "STOPPED":
            return
        self._session = "STARTING"
        self._starting_ticks = 0
        self._error = ""
        self._detached(["session", "start"])
        self.changed.emit()

    @Slot()
    def stopAndroid(self):
        self._pending = []
        subprocess.Popen(["waydroid", "session", "stop"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._session = "STOPPED"
        self.changed.emit()

    @Slot()
    def openStore(self):
        if self._google:
            self._when_running(("store",))

    @Slot()
    def showFull(self):
        self._when_running(("full",))

    @Slot(str)
    def installApk(self, url):
        path = QUrl(url).toLocalFile() if url.startswith("file:") else url
        if path:
            self._when_running(("apk", path))

    def _install_apk(self, path):
        self._message = f"Installiere {Path(path).name} …"
        self.changed.emit()
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        def done(code, _st):
            out = bytes(p.readAll()).decode("utf-8", "replace").strip()
            if code == 0 and "fail" not in out.lower():
                self._message = f"{Path(path).name} ist installiert – die App steht gleich im Startmenü."
            else:
                self._message = ""
                self._error = f"{Path(path).name} ließ sich nicht installieren." + (f" ({out[-200:]})" if out else "")
            p.deleteLater()
            self.changed.emit()
        p.finished.connect(done)
        p.start("waydroid", ["app", "install", path])

    @Slot()
    def copyGsf(self):
        if self._gsf:
            QGuiApplication.clipboard().setText(self._gsf)
            self._message = "Geräte-ID kopiert."
            self.changed.emit()

    @Slot()
    def openRegister(self):
        subprocess.Popen(["xdg-open", REGISTER_URL], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @Slot(str)
    def setChoice(self, c):
        if c in ("google", "frei"):
            self._choice = c
            self.changed.emit()

    @Slot()
    def clearMessage(self):
        self._message = ""
        self._error = ""
        self.changed.emit()

    # ---- Hilfsprogramm (Administratorrechte) ---------------------------------------------------
    def _start(self, kind, args):
        if self._busy:
            return
        self._busy, self._percent, self._result, self._error, self._message = kind, 0, "", "", ""
        self._status = "Warte auf dein Passwort …"
        self._log, self._buf = [], ""
        self._dl_phase, self._dl_last = 0, 0.0
        self.changed.emit()
        self.logChanged.emit()
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        p.readyReadStandardOutput.connect(self._read)
        p.finished.connect(self._finished)
        self._proc = p
        p.start("pkexec", [HELPER] + args)

    @Slot()
    def setUp(self):
        self._start("einrichten", ["einrichten", self._choice])

    @Slot()
    def fetchGsf(self):
        if self._session != "RUNNING":
            self._error = "Starte zuerst Android und öffne einmal den Play Store."
            self.changed.emit()
            return
        self._start("gsf", ["gsf"])

    @Slot()
    def fixGraphics(self):
        self._start("grafik", ["grafik"])

    @Slot()
    def remove(self):
        if self._session != "STOPPED":
            self.stopAndroid()
        self._start("entfernen", ["entfernen", str(os.getuid())])

    @Slot()
    def cancel(self):
        if self._busy:
            self._status = "Wird abgebrochen …"
            self.changed.emit()
            QProcess.startDetached("pkexec", [HELPER, "cancel"])

    def _read(self):
        self._buf += bytes(self._proc.readAllStandardOutput()).decode("utf-8", "replace")
        *lines, self._buf = re.split(r"[\r\n]", self._buf)
        for raw in lines:
            line = raw.rstrip()
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
                m = DL.search(line)
                if m and self._busy == "einrichten":
                    done, total = float(m.group(1)), float(m.group(2))
                    frac = done / total if total else 0
                    if frac + 0.2 < self._dl_last:    # nächste Datei (erst System, dann Hersteller-Teil)
                        self._dl_phase += 1
                    self._dl_last = frac
                    lo, hi = (5, 80) if self._dl_phase == 0 else (80, 90)
                    self._percent = max(self._percent, int(lo + (hi - lo) * frac))
                    self._status = f"Lade Android herunter … {done:.0f} von {total:.0f} MB"
                    continue
                self._log.append(line[:400])
                if len(self._log) > 400:
                    self._log = self._log[-300:]
        self.changed.emit()
        self.logChanged.emit()

    def _finished(self, code, _status):
        self._read()
        kind, self._busy = self._busy, ""
        if not self._result and not self._error:
            self._error = ("Abgebrochen – es wurde nichts verändert." if code in (126, 127)
                           else "Das hat nicht geklappt – Details im Protokoll.")
        if self._result:
            if kind == "gsf":
                self._gsf = self._result
                self._message = "Geräte-ID gefunden. Kopieren, auf der Google-Seite eintragen und etwa 15 Minuten warten."
            elif kind == "einrichten":
                self._message = "Android ist eingerichtet. Beim ersten Start dauert es etwas länger."
            elif kind == "entfernen":
                self._gsf = ""
                self._session = "STOPPED"
                self._message = "Android und alle Android-Apps sind entfernt."
            elif kind == "grafik":
                self._message = "Grafik neu eingestellt. Android einmal beenden und neu starten."
        self._status = ""
        self._gfx, self._gfx_text = graphics_probe()
        self._refresh_static()
        self.changed.emit()

    # ---- Eigenschaften ------------------------------------------------------------------------
    variant = Property(str, lambda self: self._variant, notify=changed)
    installed = Property(bool, lambda self: self._installed, notify=changed)
    isSetUp = Property(bool, lambda self: self._setup, notify=changed)
    google = Property(bool, lambda self: self._google, notify=changed)
    choice = Property(str, lambda self: self._choice, notify=changed)
    graphics = Property(str, lambda self: self._gfx, notify=changed)
    graphicsText = Property(str, lambda self: self._gfx_text, notify=changed)
    session = Property(str, lambda self: self._session, notify=changed)
    busy = Property(str, lambda self: self._busy, notify=changed)
    percent = Property(int, lambda self: self._percent, notify=changed)
    status = Property(str, lambda self: self._status, notify=changed)
    error = Property(str, lambda self: self._error, notify=changed)
    message = Property(str, lambda self: self._message, notify=changed)
    gsfId = Property(str, lambda self: self._gsf, notify=changed)
    appCount = Property(int, lambda self: self._apps, notify=changed)
    log = Property(str, lambda self: "\n".join(self._log[-200:]), notify=logChanged)
