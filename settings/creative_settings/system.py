"""System-Infos, Gerätename, Updates, Drucker-Liste und Hintergrundbild."""

import json
import os
import platform
import pwd
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import Property, QCoreApplication, QFileSystemWatcher, QObject, QProcess, QProcessEnvironment, QTimer, QUrl, Signal, Slot

from creative_shell import config as shell_config
from creative_shell.runner import Runner, spawn_detached

from .updateprogress import UpdateProgress, read_rx_bytes, read_wx_bytes


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



UPDATE_HISTORY = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "creative-os" / "update-zeiten.json"


def _load_update_history():
    """Gemessene Zeiten vom letzten Update (Entpack-Geschwindigkeit, Dauer des Einrichtens)."""
    try:
        return json.loads(UPDATE_HISTORY.read_text())
    except (OSError, ValueError):
        return {}


def _save_update_history(data):
    try:
        UPDATE_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        UPDATE_HISTORY.write_text(json.dumps(data))
    except OSError:
        pass

class SystemModel(QObject):
    changed = Signal()
    updatesChanged = Signal()
    messageChanged = Signal()
    accountsChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = Runner(self, force_c_locale=True)
        self._info = {
            "os": os_name(), "cpu": cpu_name(), "ram": ram_text(), "gpu": gpu_names(),
            "disk": disk_text(), "kernel": platform.release(),
        }
        self._host = socket.gethostname()
        self._message = ""
        self._accountBusy = False
        self._atomic = shutil.which("rpm-ostree") is not None and Path("/run/ostree-booted").exists()
        self._sb = {"secureboot": False, "enrolled": False, "pending": False}
        self._sb_msg = ""
        self.refreshSecureBoot()
        self._upd = {"state": "unknown", "text": "", "version": "", "busy": False,
                     "channel": "", "rolledBack": "", "channelBusy": False,
                     "pendingChannel": "", "wantChannel": "", "progress": -1, "progressText": ""}
        self.checkStatus()

    def _localAccounts(self):
        accounts = []
        for line in _read("/etc/passwd").splitlines():
            fields = line.split(":")
            if len(fields) != 7 or not fields[2].isdigit():
                continue
            uid = int(fields[2])
            if 1000 <= uid < 65534:
                accounts.append({"uid": uid, "name": fields[0], "current": uid == os.getuid()})
        return sorted(accounts, key=lambda account: account["name"].casefold())

    accounts = Property("QVariantList", _localAccounts, notify=accountsChanged)
    accountBusy = Property(bool, lambda self: self._accountBusy, notify=accountsChanged)

    @Slot(int, str)
    def deleteAccount(self, uid, name):
        if self._accountBusy or uid == os.getuid():
            return
        if not any(account["uid"] == uid and account["name"] == name for account in self._localAccounts()):
            self._set_message("Dieses lokale Konto ist nicht mehr verfügbar.")
            self.accountsChanged.emit()
            return
        try:
            if pwd.getpwuid(uid).pw_name != name:
                return
        except KeyError:
            return
        self._accountBusy = True
        self.accountsChanged.emit()

        def done(code, _out, _err):
            self._accountBusy = False
            self.accountsChanged.emit()
            self._set_message("Das Konto wurde gelöscht. Der persönliche Ordner bleibt erhalten."
                              if code == 0 else "Das Konto konnte nicht gelöscht werden. Prüfe, ob es noch angemeldet ist und ob du Administratorrechte hast.")

        self._run.run(["busctl", "--allow-interactive-authorization=yes", "call",
                       "org.freedesktop.Accounts", "/org/freedesktop/Accounts",
                       "org.freedesktop.Accounts", "DeleteUser", "xb", str(uid), "false"],
                      done, timeout_ms=0)

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
        self._run.run(["hostnamectl", "set-hostname", name], done, timeout_ms=0)
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

        def chan(d):
            ref = (d or {}).get("container-image-reference", "") or ""
            return "" if not ref else ("test" if ref.endswith("-testing") else "stabil")
        self._upd["channel"] = chan(booted)
        # Bereits gewechselt, aber erst nach dem Neustart aktiv?
        pend = chan(staged) if staged else ""
        self._upd["pendingChannel"] = pend if pend and pend != self._upd["channel"] else ""
        try:
            self._upd["rolledBack"] = Path("/var/lib/creative-os/rolled-back").read_text().strip()
        except OSError:
            self._upd["rolledBack"] = ""
        if staged and self._upd["pendingChannel"]:
            name = "Test" if self._upd["pendingChannel"] == "test" else "Stabil"
            self._set_upd(state="reboot", text=f"Der Kanal „{name}“ ist vorbereitet – er wird beim nächsten Neustart aktiv.")
        elif staged:
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
        self._run.run(self._update_cmd("--check"), done, timeout_ms=0)

    # ---- Herunterladen mit Fortschritt ---------------------------------------------
    def _stream(self, args, done):
        """Startet ein Update-Programm und liest seine Ausgabe laufend mit (für den Balken).
        rpm-ostree meldet: „layers needed: 12 (1.2 GB)“, dann je Schicht „Fetching … done“."""
        p = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("LC_ALL", "C")
        env.insert("LANG", "C")
        p.setProcessEnvironment(env)
        p.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        st = {"buf": "", "out": [], "progress": UpdateProgress(_load_update_history()), "started": time.monotonic()}
        self._set_upd(progress=-1, progressText="Warte auf dein Passwort …")

        def show():
            state = st["progress"].state()
            if not st["out"]:
                return                                   # noch keine Ausgabe: Passwortabfrage läuft
            self._set_upd(progress=state["progress"], progressText=state["text"])

        def handle(line):
            st["out"].append(line)
            st["progress"].feed(line)
            show()

        def tick():
            st["progress"].sample(time.monotonic() - st["started"], read_rx_bytes(), read_wx_bytes())
            show()

        timer = QTimer(p)
        timer.setInterval(1000)
        timer.timeout.connect(tick)
        timer.start()
        tick()

        def read():
            st["buf"] += bytes(p.readAllStandardOutput()).decode("utf-8", "replace")
            parts = re.split(r"[\r\n]", st["buf"])
            st["buf"] = parts.pop()
            for line in parts:
                if line.strip():
                    handle(line.strip())

        def finished(code, status):
            timer.stop()
            read()
            if st["buf"].strip():
                handle(st["buf"].strip())
            if status != QProcess.ExitStatus.NormalExit:
                code = -1
            out = "\n".join(st["out"])
            if code == 0 and st["progress"].total:
                st["progress"].finish(time.monotonic() - st["started"])
                _save_update_history(st["progress"].history())
            self._set_upd(progress=100 if code == 0 else -1, progressText="")
            p.deleteLater()
            done(code, out, out)

        p.readyReadStandardOutput.connect(read)
        p.finished.connect(finished)
        p.start(args[0], list(args[1:]))

    @Slot()
    def downloadUpdate(self):
        self._set_upd(busy=True, text="Update wird heruntergeladen – du kannst normal weiterarbeiten …")

        def done(code, _out, err):
            self._upd["busy"] = False
            if code == 0:
                self.checkStatus()
            elif code in (126, 127):
                self._set_upd(state="available", text="Abgebrochen – das Update wurde nicht geladen.")
            else:
                detail = (err.strip().splitlines() or [""])[-1][:160]
                self._set_upd(state="error", text="Das Update konnte nicht geladen werden."
                              + (f" ({detail})" if detail else ""))
        self._stream(self._update_cmd(), done)

    @Slot(str)
    def setChannel(self, name):
        """Update-Kanal wechseln: „stabil“ (geprüft) oder „test“ (Vorabversionen)."""
        shown = self._upd.get("pendingChannel") or self._upd.get("channel")
        if name == shown or name not in ("stabil", "test") or self._upd.get("busy"):
            return
        self._set_upd(channelBusy=True, busy=True, wantChannel=name,
                      text="Wechsle zu „" + ("Test" if name == "test" else "Stabil") + "“ – die passende Version wird geladen …")

        def done(code, _out, err):
            self._upd["busy"] = False
            self._upd["channelBusy"] = False
            self._upd["wantChannel"] = ""
            if code == 0:
                self.checkStatus()
            elif code in (126, 127):
                self._set_upd(text="Abgebrochen – der Kanal bleibt, wie er ist.")
            else:
                detail = (err.strip().splitlines() or [""])[-1][:160]
                self._set_upd(state="error", text="Der Kanal konnte nicht gewechselt werden."
                              + (f" ({detail})" if detail else ""))
        self._stream(self._update_cmd("--channel", name), done)

    @staticmethod
    def _update_cmd(*extra):
        """creative-update weicht bei IPv6-Problemen auf IPv4 aus (braucht dafür root → pkexec)."""
        if Path("/usr/bin/creative-update").exists() and shutil.which("pkexec"):
            return ["pkexec", "/usr/bin/creative-update", *extra]
        return ["rpm-ostree", "upgrade", *extra]

    # ---- Secure Boot: Treiber freischalten ----------------------------------------------
    sbChanged = Signal()

    @Slot()
    def refreshSecureBoot(self):
        def done(code, out, _err):
            try:
                self._sb = json.loads(out.strip().splitlines()[-1])
            except (ValueError, IndexError):
                pass
            self.sbChanged.emit()
        if Path("/usr/libexec/creative-secureboot").exists():
            self._run.run(["/usr/libexec/creative-secureboot", "status"], done)

    @Slot()
    def enrollSecureBoot(self):
        self._sb_msg = "Warte auf dein Passwort …"
        self.sbChanged.emit()

        def done(code, out, err):
            if code == 0:
                self._sb_msg = ("Vorgemerkt. Beim nächsten Neustart erscheint ein blauer Bildschirm: "
                                "„Enroll MOK“ › „Continue“ › „Yes“ wählen, Passwort creative eingeben, dann „Reboot“.")
            elif code in (126, 127):
                self._sb_msg = "Abgebrochen."
            else:
                self._sb_msg = "Das hat nicht geklappt: " + ((err or out).strip().splitlines() or [""])[-1][:140]
            self.refreshSecureBoot()
        self._run.run(["pkexec", "/usr/libexec/creative-secureboot", "enroll"], done, timeout_ms=0)

    @Slot(str)
    def openUrl(self, url):
        if url.startswith("file://"):
            path = url[7:]
            if not spawn_detached(["creative-files", path]):
                spawn_detached(["xdg-open", path])
        else:
            spawn_detached(["xdg-open", url])

    @Slot()
    def reboot(self):
        spawn_detached(["systemctl", "reboot"])

    @Slot()
    def openSoftware(self):
        spawn_detached(["creative-software", "--updates"])

    def _set_message(self, text):
        self._message = text
        self.messageChanged.emit()

    info = Property("QVariantMap", lambda self: self._info, constant=True)
    hostName = Property(str, lambda self: self._host, notify=changed)
    updates = Property("QVariantMap", lambda self: dict(self._upd), notify=updatesChanged)
    secureBoot = Property("QVariantMap", lambda self: dict(self._sb), notify=sbChanged)
    secureBootMessage = Property(str, lambda self: self._sb_msg, notify=sbChanged)
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
        self._viz_opacity = float(cfg.get("visualizerOpacity", 0.1))
        self._stats_on = bool(cfg.get("desktopStats", True))
        self._np_on = bool(cfg.get("taskbarNowPlaying", True))
        self._login_sound = bool(cfg.get("loginSound", True))
        from creative_shell import look as _look
        self._design, self._accent = _look.read()
        self._images = []
        self.refresh()

    @Slot()
    def refresh(self):
        images = []
        from creative_shell import look as _look
        default = _look.default_wallpaper(self._builtin.parent.parent)
        if default.exists():
            images.append({"path": "", "url": QUrl.fromLocalFile(str(default)).toString(),
                           "label": "Planet (passt zum Design)"})
        home = Path.home()
        pics = home / "Bilder"
        if not pics.exists() and not pics.is_symlink():
            legacy = home / "Pictures"
            if legacy.is_dir() and not legacy.is_symlink():
                pics = legacy
            else:
                try:
                    pics.mkdir(exist_ok=True)
                except OSError:
                    pass
        if pics.is_dir() and not pics.is_symlink():
            # Nur Bilder direkt im Ordner „Bilder“ – keine Unterordner
            # (Bildschirmfotos, Fotoimporte usw. bleiben außen vor)
            files = []
            for f in pics.iterdir():
                if f.suffix.lower() not in IMAGE_EXT or f.is_symlink() or f.name.startswith("."):
                    continue
                try:
                    if f.is_file():
                        files.append((f.stat().st_mtime, f))
                except OSError:
                    continue
            files.sort(reverse=True)
            for _, f in files[:100]:
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

    @Slot(bool)
    def setLoginSound(self, on):
        self._login_sound = bool(on)
        shell_config.set_value("loginSound", self._login_sound)
        self.changed.emit()

    @Slot()
    def testLoginSound(self):
        from creative_shell.loginsound import player, sound_file
        path, program = sound_file(), player()
        if path and program:
            spawn_detached([program, "-f", path] if program == "canberra-gtk-play" else [program, path])

    @Slot(bool)
    def setNowPlaying(self, on):
        self._np_on = bool(on)
        shell_config.set_value("taskbarNowPlaying", self._np_on)
        self.changed.emit()

    @Slot(str)
    def setWallpaper(self, path):
        if path and not any(image["path"] == path for image in self._images):
            return
        if not shell_config.set_value("wallpaper", path):
            return
        self._current = path
        self.changed.emit()

    # ---- Design (Graphit/Porzellan) und Akzentfarbe ------------------------------
    @Slot(str)
    def setDesign(self, name):
        self._apply_look(design=name)

    @Slot(str)
    def setAccent(self, name):
        self._apply_look(accent=name)

    def _apply_look(self, design=None, accent=None):
        from creative_shell import look as _look
        new = _look.write(design, accent)
        if new == (self._design, self._accent):
            return
        self._design, self._accent = new
        self.changed.emit()
        _look.apply_system()           # GTK-, KDE- und Terminal-Farben
        # Taskleiste lädt sich selbst neu; dieses Fenster startet mit dem neuen Design neu
        spawn_detached(["creative-settings", "--page", "look"])
        QTimer.singleShot(600, QCoreApplication.quit)

    design = Property(str, lambda self: self._design, notify=changed)
    accent = Property(str, lambda self: self._accent, notify=changed)
    images = Property("QVariantList", lambda self: self._images, notify=changed)
    visualizer = Property(bool, lambda self: self._viz_on, notify=changed)
    visualizerOpacity = Property(float, lambda self: self._viz_opacity, notify=changed)
    desktopStats = Property(bool, lambda self: self._stats_on, notify=changed)
    nowPlaying = Property(bool, lambda self: self._np_on, notify=changed)
    loginSound = Property(bool, lambda self: self._login_sound, notify=changed)
    current = Property(str, lambda self: self._current, notify=changed)
