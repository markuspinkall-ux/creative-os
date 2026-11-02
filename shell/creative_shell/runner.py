"""Startet Hilfsprogramme (nmcli, lpstat, ddcutil …) asynchron.

Die Oberfläche blockiert dadurch nie, auch wenn ein Programm hängt.
"""

import shutil
import subprocess

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer

TIMEOUT_MS = 15000


class Runner(QObject):
    def __init__(self, parent=None, force_c_locale=False):
        super().__init__(parent)
        self._env = None
        if force_c_locale:
            # Damit die Ausgabe englisch und damit sicher auswertbar ist.
            self._env = QProcessEnvironment.systemEnvironment()
            self._env.insert("LC_ALL", "C")
            self._env.insert("LANG", "C")

    def run(self, args, callback=None, stdin=None, timeout_ms=TIMEOUT_MS):
        """Führt args aus und ruft danach callback(code, stdout, stderr) auf.
        timeout_ms=0: ohne Zeitlimit (z. B. Updates, Passwort-Abfrage)."""
        if not args or shutil.which(args[0]) is None:
            if callback:
                callback(127, "", f"{args[0] if args else '?'} nicht gefunden")
            return
        proc = QProcess(self)
        if self._env is not None:
            proc.setProcessEnvironment(self._env)
        timer = QTimer(proc)
        timer.setSingleShot(True)
        timer.timeout.connect(proc.kill)

        def finished(code, status):
            try:
                timer.stop()
                out = proc.readAllStandardOutput().data().decode("utf-8", "replace")
                err = proc.readAllStandardError().data().decode("utf-8", "replace")
            except RuntimeError:  # Shell wird gerade beendet
                return
            proc.deleteLater()
            if status != QProcess.ExitStatus.NormalExit:
                code = -1
            if callback:
                callback(code, out, err)

        proc.finished.connect(finished)
        proc.start(args[0], list(args[1:]))
        if stdin is not None:
            proc.write(stdin.encode("utf-8"))
            proc.closeWriteChannel()
        if timeout_ms:
            timer.start(timeout_ms)


def spawn_detached(args):
    """Startet ein Programm unabhängig von der Shell (überlebt einen Shell-Neustart)."""
    if not args or shutil.which(args[0]) is None:
        return False
    try:
        subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except OSError:
        return False
