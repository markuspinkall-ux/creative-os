"""User-scoped Google OAuth and Drive mount management."""

import configparser
import os
import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, Property, QProcess, QTimer, Signal, Slot


CONFIG = Path.home() / ".config" / "creative-drive" / "rclone.conf"
UNIT = "creative-drive.service"


class GoogleDriveModel(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = None
        self._message = ""
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self.changed.emit)
        self._timer.start()

    def _connected(self):
        return self._has_token(CONFIG)

    @staticmethod
    def _has_token(path):
        config = configparser.ConfigParser(interpolation=None)
        try:
            config.read(path, encoding="utf-8")
            return bool(config.get("creative-drive", "token", fallback=""))
        except (OSError, configparser.Error):
            return False

    def _mounted(self):
        runtime = os.environ.get("XDG_RUNTIME_DIR")
        if not runtime:
            return False
        mount = Path(runtime) / "creative-drive" / "drive"
        try:
            return mount.is_mount()
        except OSError:
            return False

    def _run(self, command, args, callback):
        process = QProcess(self)
        self._process = process
        # rclone config may print credentials on successful authorization.
        process.setStandardOutputFile(QProcess.nullDevice())
        process.setStandardErrorFile(QProcess.nullDevice())

        def done(ok):
            if self._process is not process:
                return
            self._process = None
            process.deleteLater()
            callback(ok)
            self.changed.emit()

        process.finished.connect(lambda code, status: done(
            code == 0 and status == QProcess.ExitStatus.NormalExit))
        process.errorOccurred.connect(lambda error: done(False)
                                      if error == QProcess.ProcessError.FailedToStart else None)
        process.start(command, args)
        self.changed.emit()

    @Slot()
    def connectDrive(self):
        if self._process or self._mounted():
            return
        if not shutil.which("rclone"):
            self._message = "Google Drive ist in diesem Systemabbild nicht installiert."
            self.changed.emit()
            return
        if self._connected():
            self._mount()
            return
        try:
            CONFIG.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            temp = tempfile.TemporaryDirectory(prefix="authorize-", dir=CONFIG.parent)
        except OSError:
            self._message = "Der private Einstellungsordner konnte nicht angelegt werden."
            self.changed.emit()
            return
        pending = Path(temp.name) / "rclone.conf"
        self._message = "Melde dich im Browser bei Google an."

        def authorized(ok):
            try:
                if not ok or not self._has_token(pending):
                    self._message = "Die Google-Anmeldung wurde abgebrochen oder ist fehlgeschlagen."
                    return
                pending.chmod(0o600)
                # Keep any account connected by another settings window.
                os.link(pending, CONFIG)
            except OSError:
                self._message = "Das Google-Konto konnte nicht gespeichert werden."
                return
            finally:
                temp.cleanup()
            self._mount()

        self._run("rclone", ["--config", str(pending), "--auto-confirm", "config",
                             "create", "creative-drive", "drive", "scope=drive",
                             "config_is_local=true"], authorized)

    def _mount(self):
        self._message = "Google Drive wird eingebunden …"

        def mounted(ok):
            self._message = ("Google Drive steht in Dateien unter Geräte und Laufwerke bereit."
                             if ok else "Einbinden fehlgeschlagen. Prüfe die Internetverbindung.")

        self._run("systemctl", ["--user", "start", UNIT], mounted)

    @Slot()
    def cancel(self):
        if self._process and not self._connected():
            self._process.kill()

    @Slot()
    def unmountDrive(self):
        if self._process or not self._mounted():
            return
        self._message = "Google Drive wird ausgehängt …"

        def unmounted(ok):
            self._message = ("Google Drive ist ausgehängt. Das Konto bleibt verbunden."
                             if ok else "Google Drive konnte nicht ausgehängt werden.")

        self._run("systemctl", ["--user", "stop", UNIT], unmounted)

    connected = Property(bool, _connected, notify=changed)
    mounted = Property(bool, _mounted, notify=changed)
    busy = Property(bool, lambda self: self._process is not None, notify=changed)
    message = Property(str, lambda self: self._message, notify=changed)
