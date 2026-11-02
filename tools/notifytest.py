"""Benachrichtigungsdienst testen: über D-Bus eine Meldung schicken und das Fenster fotografieren."""
import subprocess, sys
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
sys.argv = ["creative_notify"]
import creative_notify.__main__ as m
_orig = QGuiApplication.exec
def _exec():
    def send():
        subprocess.Popen(["gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications",
                            "--object-path", "/org/freedesktop/Notifications", "--method",
                            "org.freedesktop.Notifications.Notify", "Steam", "0", "steam",
                            "Freund ist online", "Markus spielt jetzt <b>Cyberpunk 2077</b>.",
                            "['default','Öffnen','chat','Nachricht schreiben']", "{}", "8000"],
                           )
        subprocess.Popen(["gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications",
                        "--object-path", "/org/freedesktop/Notifications", "--method",
                        "org.freedesktop.Notifications.Notify", "Downloads", "0", "folder-download",
                        "Download abgeschlossen", "creative-os-amd-netinstall.iso (812 MB)", "[]", "{}", "8000"],
                       )
    def grab():
        for w in QGuiApplication.topLevelWindows():
            if w.isVisible() and hasattr(w, "grabWindow"):
                img = w.grabWindow(); img.save("/tmp/notify.png"); print("Foto", img.width(), img.height())
        QGuiApplication.quit()
    QTimer.singleShot(1500, send)
    QTimer.singleShot(3500, grab)
    return _orig()
QGuiApplication.exec = staticmethod(_exec)
sys.exit(m.main())
