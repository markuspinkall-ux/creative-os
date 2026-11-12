"""Godot im Hintergrund: einmalig herunterladen, Spiel testen, fertiges Spiel exportieren."""

import os
import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton, QVBoxLayout,
)

from . import builder, godot, icons
from .style import C


def human(n):
    return f"{n / 1e9:.1f} GB" if n > 1e9 else f"{n / 1e6:.0f} MB"


class Download(QObject):
    """Lädt eine Datei in eine Zwischendatei (folgt GitHub-Weiterleitungen)."""
    progress = Signal(int, int)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.net = QNetworkAccessManager(self)
        self.url = url
        self.file = None
        self.reply = None
        self.path = None

    def start(self):
        fd, self.path = tempfile.mkstemp(prefix="creative-engine-", suffix=Path(self.url).suffix,
                                         dir=str(godot.data_dir().parent) if godot.data_dir().parent.exists() else None)
        os.close(fd)
        self.file = open(self.path, "wb")
        req = QNetworkRequest(QUrl(self.url))
        req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                         QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "Creative-Engine")
        self.reply = self.net.get(req)
        self.reply.readyRead.connect(lambda: self.file.write(bytes(self.reply.readAll())))
        self.reply.downloadProgress.connect(lambda a, b: self.progress.emit(int(a), int(b)))
        self.reply.finished.connect(self.finish)

    def cancel(self):
        if self.reply:
            self.reply.abort()

    def finish(self):
        self.file.write(bytes(self.reply.readAll()))
        self.file.close()
        if self.reply.error() != QNetworkReply.NetworkError.NoError:
            Path(self.path).unlink(missing_ok=True)
            self.failed.emit(self.reply.errorString())
        else:
            self.done.emit(self.path)
        self.reply.deleteLater()


class SetupDialog(QDialog):
    """Einmalige Einrichtung: Spiel-Motor (ca. 60 MB) und optional Export-Vorlagen (ca. 1,2 GB)."""

    def __init__(self, parent=None, templates=False):
        super().__init__(parent)
        self.setWindowTitle("Spiel-Motor einrichten")
        self.setMinimumWidth(520)
        self.want_templates = templates
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 22, 24, 20)
        v.setSpacing(12)
        title = QLabel("Fertige Spiele brauchen den Spiel-Motor" if templates else "Einmal den Spiel-Motor laden")
        title.setStyleSheet("font-size:19px;font-weight:700")
        v.addWidget(title)
        text = QLabel(
            "Die Creative Engine baut deine Spiele mit Godot, einer freien Spiel-Engine. Du merkst davon nichts – "
            "sie wird nur einmal heruntergeladen und liegt dann in deinem Benutzerordner.")
        text.setWordWrap(True)
        text.setObjectName("sub")
        v.addWidget(text)
        self.motor = QLabel()
        self.vorlagen = QCheckBox(f"Export-Vorlagen für Linux und Windows (ca. {godot.TEMPLATES_SIZE_MB / 1000:.1f} GB "
                                  "Download, entpackt ca. 300 MB)")
        self.vorlagen.setChecked(templates)
        v.addWidget(self.motor)
        v.addWidget(self.vorlagen)
        self.status = QLabel("")
        self.status.setObjectName("sub")
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.hide()
        v.addWidget(self.bar)
        v.addWidget(self.status)
        row = QHBoxLayout()
        row.addStretch(1)
        self.cancel = QPushButton("Abbrechen")
        self.cancel.clicked.connect(self.stop)
        self.go = QPushButton("Herunterladen")
        self.go.setObjectName("primary")
        self.go.setIcon(icons.icon("download", C["accentText"]))
        self.go.clicked.connect(self.begin)
        row.addWidget(self.cancel)
        row.addWidget(self.go)
        v.addLayout(row)
        self.queue = []
        self.current = None
        self.refresh()

    def refresh(self):
        have = godot.binary() is not None
        self.motor.setText(("✓ " if have else "• ") + f"Spiel-Motor Godot {godot.VERSION} (ca. 60 MB)"
                           + (" – vorhanden" if have else ""))
        if godot.templates_ready():
            self.vorlagen.setText("✓ Export-Vorlagen für Linux und Windows – vorhanden")
            self.vorlagen.setEnabled(False)
            self.vorlagen.setChecked(False)
        if have and (godot.templates_ready() or not self.want_templates):
            self.go.setText("Fertig")
            self.go.setIcon(icons.icon("check", C["accentText"]))
            try:
                self.go.clicked.disconnect()
            except RuntimeError:
                pass
            self.go.clicked.connect(self.accept)
            if not self.vorlagen.isChecked() or godot.templates_ready():
                pass

    def begin(self):
        self.queue = []
        if godot.binary() is None:
            self.queue.append(("Spiel-Motor", godot.EDITOR_URL, godot.install_editor))
        if self.vorlagen.isChecked() and not godot.templates_ready():
            self.queue.append(("Export-Vorlagen", godot.TEMPLATES_URL, godot.install_templates))
        if not self.queue:
            self.accept()
            return
        self.go.setEnabled(False)
        self.vorlagen.setEnabled(False)
        self.bar.show()
        self.inhibit = keep_awake("Creative Engine lädt den Spiel-Motor")
        self.next()

    def next(self):
        if not self.queue:
            self.status.setText("Alles bereit.")
            release(getattr(self, "inhibit", None))
            self.go.setEnabled(True)
            self.refresh()
            return
        name, url, install = self.queue.pop(0)
        self.current = Download(url, self)
        self.current.progress.connect(lambda a, b, n=name: self.show_progress(n, a, b))
        self.current.failed.connect(self.fail)
        self.current.done.connect(lambda path, n=name, f=install: self.install(n, path, f))
        self.current.start()

    def show_progress(self, name, a, b):
        if b > 0:
            self.bar.setMaximum(1000)
            self.bar.setValue(int(a * 1000 / b))
            self.status.setText(f"{name}: {human(a)} von {human(b)}")
        else:
            self.bar.setMaximum(0)
            self.status.setText(f"{name}: {human(a)}")

    def install(self, name, path, func):
        self.status.setText(f"{name} wird eingerichtet …")
        self.bar.setMaximum(0)
        QTimer.singleShot(30, lambda: self._install(name, path, func))

    def _install(self, name, path, func):
        try:
            func(path)
        except Exception as exc:  # noqa: BLE001
            self.fail(f"{name}: {exc}")
            return
        finally:
            Path(path).unlink(missing_ok=True)
        self.next()

    def fail(self, message):
        release(getattr(self, "inhibit", None))
        self.status.setText(f"Download fehlgeschlagen: {message}")
        self.status.setStyleSheet(f"color:{C['danger']}")
        self.go.setEnabled(True)
        self.go.setText("Erneut versuchen")

    def stop(self):
        if self.current:
            self.current.cancel()
        release(getattr(self, "inhibit", None))
        self.reject()


def keep_awake(why):
    """Bereitschaft verhindern, solange geladen/exportiert wird (wie beim Update-Center)."""
    if not shutil.which("systemd-inhibit") and not shutil.which("flatpak-spawn"):
        return None
    p = QProcess()
    cmd = ["systemd-inhibit", "--what=idle:sleep", "--who=Creative Engine", f"--why={why}", "sleep", "infinity"]
    if os.path.exists("/.flatpak-info"):
        cmd = ["flatpak-spawn", "--host"] + cmd
    p.start(cmd[0], cmd[1:])
    return p


def release(proc):
    if proc is not None and proc.state() != QProcess.ProcessState.NotRunning:
        proc.kill()
        proc.waitForFinished(1000)


def ensure_godot(parent, templates=False):
    if godot.binary() is not None and (not templates or godot.templates_ready()):
        return True
    dlg = SetupDialog(parent, templates)
    dlg.exec()
    return godot.binary() is not None and (not templates or godot.templates_ready())


class Player(QObject):
    """Startet das Spiel zum Testen in einem eigenen Fenster."""
    message = Signal(str)
    stopped = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.proc = None
        self.log = ""

    def running(self):
        return self.proc is not None and self.proc.state() != QProcess.ProcessState.NotRunning

    def play(self, folder, data, start=None):
        if self.running():
            self.proc.kill()
            self.proc.waitForFinished(2000)
        target = godot.data_dir() / "test" / builder.file_name(data["name"])
        builder.build(folder, data, target)
        self.log = ""
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyRead.connect(self.read)
        self.proc.finished.connect(self.done)
        self.proc.start(str(godot.binary()), godot.run_args(target, start))
        self.message.emit("Spiel läuft – Fenster schließen oder Esc → Menü beendet es.")

    def read(self):
        self.log += bytes(self.proc.readAll()).decode("utf-8", "replace")
        self.log = self.log[-20000:]

    def stop(self):
        if self.running():
            self.proc.terminate()

    def done(self):
        errors = [l for l in self.log.splitlines() if "SCRIPT ERROR" in l or l.startswith("ERROR")]
        if errors:
            self.message.emit("Spiel beendet – Hinweis: " + errors[0][:160])
        else:
            self.message.emit("Spiel beendet.")
        self.stopped.emit()


class ExportDialog(QDialog):
    """Fertiges Spiel bauen: Linux (eine Datei) und Windows (.exe) in einen Ordner."""

    def __init__(self, parent, folder, data):
        super().__init__(parent)
        self.folder, self.data = folder, data
        self.setWindowTitle("Spiel exportieren")
        self.setMinimumWidth(560)
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 22, 24, 20)
        v.setSpacing(12)
        title = QLabel(f"„{data['name']}“ als fertiges Spiel")
        title.setStyleSheet("font-size:19px;font-weight:700")
        v.addWidget(title)
        sub = QLabel("Das Ergebnis läuft ohne Creative Engine – zum Weitergeben, Hochladen (z. B. itch.io) oder Archivieren.")
        sub.setObjectName("sub")
        sub.setWordWrap(True)
        v.addWidget(sub)
        self.linux = QCheckBox("Linux – eine Programmdatei (x86_64)")
        self.linux.setChecked(True)
        self.windows = QCheckBox("Windows – .exe (64 Bit)")
        self.windows.setChecked(True)
        v.addWidget(self.linux)
        v.addWidget(self.windows)
        row = QHBoxLayout()
        default = Path.home() / "Spiele" / builder.file_name(data["name"])
        self.target = QLineEdit(str(default))
        pick = QPushButton("Ordner …")
        pick.clicked.connect(self.pick)
        row.addWidget(QLabel("Ziel"))
        row.addWidget(self.target, 1)
        row.addWidget(pick)
        v.addLayout(row)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.hide()
        self.status = QLabel("")
        self.status.setObjectName("sub")
        self.status.setWordWrap(True)
        v.addWidget(self.bar)
        v.addWidget(self.status)
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.close_btn = QPushButton("Schließen")
        self.close_btn.clicked.connect(self.reject)
        self.go = QPushButton("Exportieren")
        self.go.setObjectName("primary")
        self.go.setIcon(icons.icon("export", C["accentText"]))
        self.go.clicked.connect(self.begin)
        btns.addWidget(self.close_btn)
        btns.addWidget(self.go)
        v.addLayout(btns)
        self.jobs = []
        self.proc = None
        self.results = []

    def pick(self):
        d = QFileDialog.getExistingDirectory(self, "Zielordner wählen", str(Path(self.target.text()).parent))
        if d:
            self.target.setText(str(Path(d) / builder.file_name(self.data["name"])))

    def begin(self):
        if not ensure_godot(self, templates=True):
            self.status.setText("Ohne Export-Vorlagen kann kein fertiges Spiel gebaut werden.")
            return
        out = Path(self.target.text()).expanduser()
        out.mkdir(parents=True, exist_ok=True)
        name = builder.file_name(self.data["name"])
        self.build_dir = godot.data_dir() / "export" / name
        builder.build(self.folder, self.data, self.build_dir)
        self.jobs = [("Vorbereiten", godot.import_args(self.build_dir), None)]
        if self.linux.isChecked():
            self.jobs.append(("Linux", godot.export_args(self.build_dir, "Linux", out / f"{name}.x86_64"),
                              out / f"{name}.x86_64"))
        if self.windows.isChecked():
            self.jobs.append(("Windows", godot.export_args(self.build_dir, "Windows", out / f"{name}.exe"),
                              out / f"{name}.exe"))
        if len(self.jobs) == 1:
            self.status.setText("Bitte mindestens ein System wählen.")
            return
        self.out = out
        self.results = []
        self.go.setEnabled(False)
        self.bar.show()
        self.bar.setMaximum(len(self.jobs))
        self.bar.setValue(0)
        self.inhibit = keep_awake("Creative Engine exportiert ein Spiel")
        self.next()

    def next(self):
        if not self.jobs:
            release(self.inhibit)
            self.bar.setValue(self.bar.maximum())
            lines = [f"✓ {n}: {p.name} ({human(p.stat().st_size)})" for n, p in self.results]
            self.status.setText("Fertig!\n" + "\n".join(lines))
            self.status.setStyleSheet(f"color:{C['ok']}")
            self.go.setEnabled(True)
            self.go.setText("Ordner öffnen")
            self.go.setIcon(icons.icon("folder", C["accentText"]))
            self.go.clicked.disconnect()
            self.go.clicked.connect(lambda: QProcess.startDetached("xdg-open", [str(self.out)]))
            return
        name, args, result = self.jobs.pop(0)
        self.current = (name, result)
        self.status.setText(f"{name} …")
        self.log = ""
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyRead.connect(lambda: setattr(self, "log", self.log + bytes(self.proc.readAll()).decode("utf-8", "replace")))
        self.proc.finished.connect(self.finished)
        self.proc.start(str(godot.binary()), args)

    def finished(self, code, _status):
        name, result = self.current
        self.bar.setValue(self.bar.value() + 1)
        if result is not None:
            if not result.exists() or result.stat().st_size < 1_000_000:
                release(self.inhibit)
                tail = "\n".join(l for l in self.log.splitlines() if "ERROR" in l)[-600:]
                self.status.setText(f"{name}: Export fehlgeschlagen.\n{tail}")
                self.status.setStyleSheet(f"color:{C['danger']}")
                self.go.setEnabled(True)
                return
            if name == "Linux":
                result.chmod(0o755)
            self.results.append((name, result))
        self.next()

    def reject(self):
        if self.proc and self.proc.state() != QProcess.ProcessState.NotRunning:
            self.proc.kill()
        release(getattr(self, "inhibit", None))
        super().reject()
