"""Solange Capture offen ist: kein Standby, kein Abdunkeln, keine Bildschirmsperre.

Zwei Wege, damit es in jeder Sitzung greift:
- org.freedesktop.ScreenSaver.Inhibit (Bildschirm bleibt an, Plasma/PowerDevil schläft nicht);
  die Sperre hängt an unserer D-Bus-Verbindung und fällt beim Beenden von selbst weg.
- systemd-inhibit --what=idle:sleep, gekoppelt an unsere Prozessnummer: stürzt Capture ab,
  endet auch die Sperre (tail --pid).
"""

import os
import shutil
import subprocess

WHO = "Capture"
WHY = "Capture-Karte wird angezeigt"


def inhibit_cmd(pid=None):
    """Befehl für die systemd-Sperre – endet, sobald Capture (pid) endet."""
    pid = pid or os.getpid()
    cmd = ["systemd-inhibit", "--what=idle:sleep", f"--who={WHO}", f"--why={WHY}", "--mode=block",
           "tail", f"--pid={pid}", "-f", "/dev/null"]
    if os.path.exists("/.flatpak-info"):
        cmd = ["flatpak-spawn", "--host"] + cmd
    return cmd


class WachHalten:
    def __init__(self):
        self.proc = None
        self.cookie = None

    def start(self):
        if shutil.which("systemd-inhibit") or shutil.which("flatpak-spawn"):
            try:
                self.proc = subprocess.Popen(inhibit_cmd(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL, start_new_session=True)
            except OSError:
                self.proc = None
        try:
            from PySide6.QtDBus import QDBusConnection, QDBusInterface
            bus = QDBusConnection.sessionBus()
            if bus.isConnected():
                iface = QDBusInterface("org.freedesktop.ScreenSaver", "/ScreenSaver",
                                       "org.freedesktop.ScreenSaver", bus)
                if iface.isValid():
                    reply = iface.call("Inhibit", WHO, WHY)
                    args = reply.arguments()
                    if args:
                        self.cookie = int(args[0])
        except Exception:  # noqa: BLE001 – ohne D-Bus bleibt die systemd-Sperre
            self.cookie = None
        return self

    def stop(self):
        if self.cookie is not None:
            try:
                from PySide6.QtDBus import QDBusConnection, QDBusInterface
                iface = QDBusInterface("org.freedesktop.ScreenSaver", "/ScreenSaver",
                                       "org.freedesktop.ScreenSaver", QDBusConnection.sessionBus())
                iface.call("UnInhibit", self.cookie)
            except Exception:  # noqa: BLE001
                pass
            self.cookie = None
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(1)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
