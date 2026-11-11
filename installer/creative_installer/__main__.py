"""Startpunkt: `creative-installer` – die Creative-Installation in der Live-Umgebung.

Die Oberfläche (QML) sammelt Festplatte und Benutzerkonto; installiert wird über
`pkexec creative-installer-helper install` (Anaconda im Hintergrund).
Mit `--demo` wird nur vorgespielt (keine Festplatte wird angefasst).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
for name, pkg in (("shell", "creative_shell"),):
    for base in (HERE.parent.parent / name, Path(f"/usr/lib/creative-{name}")):
        if (base / pkg).is_dir():
            sys.path.insert(0, str(base))
            break

from PySide6.QtCore import Property, QObject, QProcess, QProcessEnvironment, QTimer, QUrl, Signal, Slot  # noqa: E402
from PySide6.QtGui import QFont, QGuiApplication, QIcon  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

from creative_installer import plan  # noqa: E402

HELPER_PATHS = ["/usr/libexec/creative-installer-helper", str(HERE.parent / "creative-installer-helper")]
DEMO_DISKS = {"blockdevices": [
    {"name": "nvme0n1", "path": "/dev/nvme0n1", "size": 1000204886016, "model": "Samsung SSD 980 PRO 1TB",
     "tran": "nvme", "type": "disk", "rm": False, "ro": False,
     "children": [{"fstype": "vfat", "label": "SYSTEM"}, {"fstype": "ntfs", "label": "Windows"}]},
    {"name": "sda", "path": "/dev/sda", "size": 2000398934016, "model": "WDC WD20EZBX", "tran": "sata",
     "type": "disk", "rm": False, "ro": False, "children": [{"fstype": "ext4", "label": "Spiele"}]},
    {"name": "sdb", "path": "/dev/sdb", "size": 15376000000, "model": "SanDisk Ultra", "tran": "usb",
     "type": "disk", "rm": True, "ro": False, "children": [{"fstype": "iso9660", "label": "Creative-OS"}]},
]}


def _variant():
    try:
        return Path("/usr/share/creative-os/variant").read_text().strip() or "amd"
    except OSError:
        return "amd"


class Installer(QObject):
    changed = Signal()
    disksChanged = Signal()

    def __init__(self, demo=False):
        super().__init__()
        self._demo = demo
        self._disks = []
        self._busy = False
        self._percent = 0
        self._stage = ""
        self._log = []
        self._error = ""
        self._done = False
        self._proc = None
        self._buf = ""
        self.refreshDisks()

    # ---- Festplatten ------------------------------------------------------------------
    @Slot()
    def refreshDisks(self):
        if self._demo:
            self._disks = plan.parse_disks(DEMO_DISKS, {"/dev/sdb"})
        else:
            try:
                raw = subprocess.run(["lsblk", "--json", "--bytes", "--paths", "-o",
                                      "NAME,PATH,SIZE,MODEL,TRAN,TYPE,RM,RO,FSTYPE,LABEL"],
                                     capture_output=True, text=True, timeout=10).stdout
                self._disks = plan.parse_disks(raw or '{"blockdevices": []}', self._live_disks())
            except (OSError, subprocess.SubprocessError, ValueError):
                self._disks = []
        self.disksChanged.emit()

    @staticmethod
    def _live_disks():
        found = set()
        try:
            src = subprocess.run(["findmnt", "-n", "-o", "SOURCE", "/run/initramfs/live"],
                                 capture_output=True, text=True, timeout=5).stdout.strip()
            if src.startswith("/dev/"):
                parent = subprocess.run(["lsblk", "-n", "-p", "-o", "PKNAME", src],
                                        capture_output=True, text=True, timeout=5).stdout.split()
                found.add(parent[0] if parent else src)
        except (OSError, subprocess.SubprocessError):
            pass
        return found

    @Property("QVariantList", notify=disksChanged)
    def disks(self):
        return self._disks

    # ---- Hilfen für die Eingabe -------------------------------------------------------
    @Slot(str, result=str)
    def suggestUser(self, full_name):
        return plan.suggest_username(full_name)

    @Slot(str, result=int)
    def strength(self, pw):
        return plan.password_strength(pw)

    @Slot("QVariantMap", result=str)
    def check(self, cfg):
        return plan.validate(dict(cfg), self._disks)

    @Property("QStringList", constant=True)
    def keyboards(self):
        return list(plan.KEYBOARDS)

    @Property(str, constant=True)
    def variant(self):
        return _variant()

    @Property(bool, constant=True)
    def demo(self):
        return self._demo

    # ---- Installation -----------------------------------------------------------------
    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(int, notify=changed)
    def percent(self):
        return self._percent

    @Property(str, notify=changed)
    def stage(self):
        return self._stage

    @Property(str, notify=changed)
    def log(self):
        return "\n".join(self._log[-200:])

    @Property(str, notify=changed)
    def error(self):
        return self._error

    @Property(bool, notify=changed)
    def done(self):
        return self._done

    @Slot("QVariantMap")
    def start(self, cfg):
        cfg = dict(cfg)
        cfg["variant"] = _variant()
        err = plan.validate(cfg, self._disks)
        if err:
            self._error = err
            self.changed.emit()
            return
        self._busy, self._done, self._error, self._percent, self._log = True, False, "", 0, []
        self._stage = "Installation wird vorbereitet"
        self.changed.emit()
        helper = next((p for p in HELPER_PATHS if os.path.exists(p)), HELPER_PATHS[0])
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read)
        self._proc.finished.connect(self._finished)
        if self._demo:
            # Vorführmodus: der Helfer spielt die Installation nur vor (ohne root, ohne Festplatte)
            env = QProcessEnvironment.systemEnvironment()
            env.insert("CREATIVE_INSTALLER_DRYRUN", "1")
            self._proc.setProcessEnvironment(env)
            self._proc.start(sys.executable, [helper, "install"])
        else:
            self._proc.start("pkexec", [helper, "install"])
        self._proc.write((json.dumps(cfg) + "\n").encode())
        self._proc.closeWriteChannel()

    def _read(self):
        self._buf += bytes(self._proc.readAllStandardOutput()).decode(errors="replace")
        *lines, self._buf = self._buf.split("\n")
        for line in lines:
            if line.startswith("P "):
                parts = line.split(" ", 2)
                try:
                    self._percent = max(self._percent, int(parts[1]))
                except ValueError:
                    pass
                if len(parts) > 2:
                    self._stage = parts[2]
            elif line.startswith("L "):
                self._log.append(line[2:])
            elif line == "OK":
                self._done = True
                self._percent = 100
            elif line.startswith("ERR "):
                self._error = line[4:]
            elif line.strip():
                self._log.append(line)
        self.changed.emit()

    def _finished(self, code, _status):
        self._busy = False
        if not self._done and not self._error:
            self._error = ("Die Installation wurde abgebrochen." if code in (126, 127)
                           else f"Die Installation ist fehlgeschlagen (Code {code}).")
        self.changed.emit()

    @Slot()
    def reboot(self):
        if self._demo:
            QGuiApplication.quit()
            return
        subprocess.Popen(["systemctl", "reboot"])

    @Slot()
    def openExpert(self):
        """Fedora-Installer (Anaconda) für Sonderfälle wie Dual-Boot."""
        subprocess.Popen(["liveinst"], start_new_session=True)

    @Slot()
    def quit(self):
        QGuiApplication.quit()


def main():
    demo = "--demo" in sys.argv or "--selftest" in sys.argv
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Creative OS installieren")
    app.setDesktopFileName("creative-installer")
    app.setWindowIcon(QIcon.fromTheme("creative-installer"))
    app.setFont(QFont("Arial", 10))

    engine = QQmlApplicationEngine()
    qml_root = next((Path(p) / "creative_shell" / "qml" for p in sys.path
                     if (Path(p) / "creative_shell" / "qml" / "Creative").is_dir()), None)
    if qml_root is None:
        print("creative-installer: Creative-Design nicht gefunden")
        return 1
    engine.addImportPath(str(qml_root))
    installer = Installer(demo=demo)
    ctx = engine.rootContext()
    ctx.setContextProperty("installer", installer)
    ctx.setContextProperty("wallpaperUrl", QUrl.fromLocalFile(str(qml_root / "Creative" / "wallpapers" / "graphit.svg")))
    start_step = 0
    for arg in sys.argv:
        if arg.startswith("--step="):
            start_step = int(arg.split("=", 1)[1])
    ctx.setContextProperty("startStep", start_step)
    ctx.setContextProperty("autoMode", "--auto" in sys.argv)
    if "--selftest" in sys.argv:
        # nur übersetzen (ohne Fenster) – Fenster im Bau-Container können hängen
        from PySide6.QtQml import QQmlComponent
        comp = QQmlComponent(engine, QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
        if comp.isError():
            for err in comp.errors():
                print("QML-FEHLER", err.toString(), flush=True)
            os._exit(1)
        print("Creative-Installation: Selbsttest bestanden", flush=True)
        os._exit(0)
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    ticker = QTimer()
    ticker.start(300)
    ticker.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
