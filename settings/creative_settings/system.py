"""System-Infos, Gerätename, Updates, Drucker-Liste und Hintergrundbild."""

import json
import os
import platform
import re
import shutil
import socket
import subprocess
from pathlib import Path

from PySide6.QtCore import Property, QFileSystemWatcher, QObject, QTimer, QUrl, Signal, Slot

from creative_shell import config as shell_config
from creative_shell.runner import Runner, spawn_detached


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def os_name():
    data = dict(re.findall(r'^(\w+)="?([^"\n]*)"?$', _read("/etc/os-release"), re.M))
    return data.get("PRETTY_NAME") or data.get("NAME") or "Linux"


def cpu_name():
    m = re.search(r"^model name\s*:\s*(.+)$", _read("/proc/cpuinfo"), re.M)
    name = m.group(1) if m else platform.processor() or "Unbekannt"
    name = re.sub(r"\((R|TM)\)|CPU|@.*$", "", name).strip()
    cores = os.cpu_count() or 0
    return f"{re.sub(' +', ' ', name)} ({cores} Kerne)" if cores else name


def ram_text():
    m = re.search(r"^MemTotal:\s+(\d+)", _read("/proc/meminfo"), re.M)
    if not m:
        return "Unbekannt"
    gb = int(m.group(1)) / 1024 / 1024
    return f"{round(gb)} GB" if gb >= 3 else f"{gb:.1f} GB".replace(".", ",")


def gpu_names():
    if not shutil.which("lspci"):
        return "Unbekannt"
    try:
        out = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return "Unbekannt"
    gpus = []
    for line in out.splitlines():
        if re.search(r"VGA compatible|3D controller|Display controller", line):
            name = line.split(": ", 1)[-1]
            name = re.sub(r"\s*\(rev [0-9a-f]+\)$", "", name)
            name = name.replace("Corporation ", "").replace("[", "").replace("]", "")
            gpus.append(name.strip())
    return " · ".join(gpus) or "Unbekannt"


def disk_text():
    for p in ("/sysroot", "/"):
        try:
            u = shutil.disk_usage(p)
            free = u.free / 1024 ** 3
            total = u.total / 1024 ** 3
            return f"{free:.0f} GB frei von {total:.0f} GB"
        except OSError:
            continue
    return "Unbekannt"


class SystemModel(QObject):
    changed = Signal()
    updatesChanged = Signal()
    messageChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = Runner(self, force_c_locale=True)
        self._info = {
            "os": os_name(), "cpu": cpu_name(), "ram": ram_text(), "gpu": gpu_names(),
            "disk": disk_text(), "kernel": platform.release(),
        }
        self._host = socket.gethostname()
        self._message = ""
        self._atomic = shutil.which("rpm-ostree") is not None and Path("/run/ostree-booted").exists()
        self._upd = {"state": "unknown", "text": "", "version": "", "busy": False}
        self.checkStatus()

    # ---- Gerätename -------------------------------------------------------------
    @Slot(str, result=str)
    def rename(self, name):
        name = name.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,62}", name):
            return "Bitte nur Buchstaben (ohne Umlaute), Ziffern und Bindestriche verwenden."

        def done(code, _out, err):
            if code == 0:
                self._host = name
                self.changed.emit()
                self._set_message("Der Gerätename wurde geändert.")
            else:
                self._set_message("Der Name konnte nicht geändert werden.")
        self._run.run(["hostnamectl", "set-hostname", name], done)
        return ""

    # ---- Updates ----------------------------------------------------------------
    def _set_upd(self, **kw):
        self._upd.update(kw)
        self.updatesChanged.emit()

    @Slot()
    def checkStatus(self):
        if not self._atomic:
            self._set_upd(state="classic", text="Updates kommen über die App „Software“.")
            return
        self._run.run(["rpm-ostree", "status", "--json"], self._on_status)

    def _on_status(self, code, out, _err):
        try:
            deps = json.loads(out).get("deployments", [])
        except ValueError:
            self._set_upd(state="unknown", text="Der Update-Status konnte nicht gelesen werden.")
            return
        booted = next((d for d in deps if d.get("booted")), {})
        staged = next((d for d in deps if d.get("staged")), None)
        self._upd["version"] = booted.get("version", "")
        if staged:
            self._set_upd(state="reboot", text="Ein Update ist bereit. Es wird beim nächsten Neustart aktiv.")
        else:
            self._set_upd(state="current", text="Creative OS ist auf dem neuesten Stand.")

    @Slot()
    def checkUpdates(self):
        if not self._atomic:
            self.openSoftware()
            return
        self._set_upd(busy=True, text="Suche nach Updates …")

        def done(code, out, err):
            self._upd["busy"] = False
            if code == 77 or "No updates available" in out:
                self._set_upd(state="current", text="Creative OS ist auf dem neuesten Stand.")
            elif code == 0:
                self._set_upd(state="available", text="Ein Update ist verfügbar.")
            else:
                detail = (err.strip().splitlines() or [""])[-1][:160]
                if "authoriz" in detail.lower() or "polkit" in detail.lower() or "not allowed" in detail.lower():
                    text = "Für die Update-Suche fehlt noch die Berechtigung – sie kommt mit dem nächsten Update."
                else:
                    text = "Die Update-Suche hat nicht geklappt." + (f" ({detail})" if detail else
                                                                    " Besteht eine Internetverbindung?")
                self._set_upd(state="error", text=text)
        self._run.run(self._update_cmd("--check"), done)

    @Slot()
    def downloadUpdate(self):
        self._set_upd(busy=True, text="Update wird heruntergeladen – du kannst normal weiterarbeiten …")

        def done(code, _out, err):
            self._upd["busy"] = False
            if code == 0:
                self.checkStatus()
            else:
                detail = (err.strip().splitlines() or [""])[-1][:160]
                self._set_upd(state="error", text="Das Update konnte nicht geladen werden."
                              + (f" ({detail})" if detail else ""))
        self._run.run(self._update_cmd(), done)

    @staticmethod
    def _update_cmd(*extra):
        """creative-update weicht bei IPv6-Problemen auf IPv4 aus (braucht dafür root → pkexec)."""
        if Path("/usr/bin/creative-update").exists() and shutil.which("pkexec"):
            return ["pkexec", "/usr/bin/creative-update", *extra]
        return ["rpm-ostree", "upgrade", *extra]

    @Slot()
    def reboot(self):
        spawn_detached(["systemctl", "reboot"])

    @Slot()
    def openSoftware(self):
        if not spawn_detached(["gnome-software", "--mode=updates"]):
            spawn_detached(["plasma-discover", "--mode", "update"])

    def _set_message(self, text):
        self._message = text
        self.messageChanged.emit()

    info = Property("QVariantMap", lambda self: self._info, constant=True)
    hostName = Property(str, lambda self: self._host, notify=changed)
    updates = Property("QVariantMap", lambda self: dict(self._upd), notify=updatesChanged)
    message = Property(str, lambda self: self._message, notify=messageChanged)


class PrinterListModel(QObject):
    """Alle Drucker (lpstat), Standarddrucker, Testseite."""
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = Runner(self, force_c_locale=True)
        self._printers = []
        self._default = ""
        self._available = shutil.which("lpstat") is not None
        self.refresh()

    @Slot()
    def refresh(self):
        self._run.run(["lpstat", "-d"], self._on_default)

    def _on_default(self, _code, out, _err):
        m = re.search(r"system default destination:\s*(\S+)", out)
        self._default = m.group(1) if m else ""
        self._run.run(["lpstat", "-p"], self._on_list)

    def _on_list(self, _code, out, _err):
        printers = []
        for line in out.splitlines():
            if not line.startswith("printer "):
                continue
            name = line.split()[1]
            state = "Ausgeschaltet oder gestört" if "disabled" in line else \
                    ("Druckt gerade" if "now printing" in line else "Bereit")
            printers.append({"name": name, "label": name.replace("_", " "), "state": state,
                             "isDefault": name == self._default, "problem": "disabled" in line})
        printers.sort(key=lambda p: (not p["isDefault"], p["label"].casefold()))
        self._printers = printers
        self.changed.emit()

    @Slot(str)
    def setDefault(self, name):
        self._run.run(["lpoptions", "-d", name], lambda *_: self.refresh())

    @Slot(str)
    def testPage(self, name):
        for f in ("/usr/share/cups/data/testprint", "/usr/share/cups/data/default-testpage.pdf"):
            if Path(f).exists():
                self._run.run(["lp", "-d", name, f])
                return

    @Slot()
    def addPrinter(self):
        if not spawn_detached(["system-config-printer"]):
            spawn_detached(["xdg-open", "http://localhost:631/admin"])

    available = Property(bool, lambda self: self._available, constant=True)
    printers = Property("QVariantList", lambda self: self._printers, notify=changed)


IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".svg"}


class LookModel(QObject):
    """Hintergrundbild wählen (gilt sofort, die Taskleiste lädt es neu)."""
    changed = Signal()

    def __init__(self, builtin_dir, parent=None):
        super().__init__(parent)
        self._builtin = Path(builtin_dir)
        cfg = shell_config.load()
        self._current = cfg.get("wallpaper") or ""
        self._viz_on = bool(cfg.get("taskbarVisualizer", True))
        self._viz_opacity = float(cfg.get("visualizerOpacity", 0.7))
        self._stats_on = bool(cfg.get("desktopStats", True))
        self._images = []
        self.refresh()

    @Slot()
    def refresh(self):
        images = []
        for f in sorted(self._builtin.glob("*")):
            if f.suffix.lower() in IMAGE_EXT:
                images.append({"path": "", "url": QUrl.fromLocalFile(str(f)).toString(),
                               "label": "Graphit" if f.stem == "graphit" else f.stem.capitalize()})
                break
        pics = None
        for name in ("Bilder", "Pictures"):
            if (Path.home() / name).is_dir():
                pics = Path.home() / name
                break
        if pics:
            files = [f for f in pics.rglob("*") if f.is_file() and f.suffix.lower() in IMAGE_EXT]
            files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            for f in files[:40]:
                images.append({"path": str(f), "url": QUrl.fromLocalFile(str(f)).toString(), "label": f.stem})
        self._images = images
        self.changed.emit()

    # ---- Musik-Visualizer und Leistungsanzeige (Taskleiste übernimmt sofort) ----
    @Slot(bool)
    def setVisualizer(self, on):
        self._viz_on = bool(on)
        shell_config.set_value("taskbarVisualizer", self._viz_on)
        self.changed.emit()

    @Slot(float)
    def setVisualizerOpacity(self, value):
        self._viz_opacity = max(0.1, min(1.0, round(float(value), 2)))
        shell_config.set_value("visualizerOpacity", self._viz_opacity)
        self.changed.emit()

    @Slot(bool)
    def setDesktopStats(self, on):
        self._stats_on = bool(on)
        shell_config.set_value("desktopStats", self._stats_on)
        self.changed.emit()

    @Slot(str)
    def setWallpaper(self, path):
        cfg_path = shell_config.config_dir() / "shell.json"
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except (OSError, ValueError):
            data = {}
        data["wallpaper"] = path
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cfg_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(cfg_path)
        self._current = path
        self.changed.emit()

    images = Property("QVariantList", lambda self: self._images, notify=changed)
    visualizer = Property(bool, lambda self: self._viz_on, notify=changed)
    visualizerOpacity = Property(float, lambda self: self._viz_opacity, notify=changed)
    desktopStats = Property(bool, lambda self: self._stats_on, notify=changed)
    current = Property(str, lambda self: self._current, notify=changed)
