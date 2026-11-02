"""Creative Capture – Bild und Ton einer Capture-Karte (HDMI-Grabber, Cam Link …) anzeigen.

Startpunkt: `creative-capture`. Die Anzeige läuft über Qt Multimedia (V4L2 + PipeWire).
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

HERE = Path(__file__).resolve().parent
SERVER = f"creative-capture-{os.getuid()}"
CFG = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "creative-os" / "capture.json"


def user_dir(kind, fallback):
    try:
        out = subprocess.run(["xdg-user-dir", kind], capture_output=True, text=True, timeout=3).stdout.strip()
        if out and Path(out) != Path.home():
            return Path(out)
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.home() / fallback


class Capture(QObject):
    changed = Signal()
    toast = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cfg = {"video": "", "audio": "", "format": "", "volume": 1.0, "muted": False}
        try:
            data = json.loads(CFG.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._cfg.update({k: v for k, v in data.items() if k in self._cfg})
        except (OSError, ValueError):
            pass

    def _save(self):
        try:
            CFG.parent.mkdir(parents=True, exist_ok=True)
            CFG.write_text(json.dumps(self._cfg, indent=1), encoding="utf-8")
        except OSError:
            pass

    @Slot(str, "QVariant")
    def set(self, key, value):
        if key in self._cfg and self._cfg[key] != value:
            self._cfg[key] = value
            self._save()
            self.changed.emit()

    @Slot(str, result="QVariant")
    def get(self, key):
        return self._cfg.get(key)

    @Slot(str, result=str)
    def newFile(self, kind):
        """Pfad für ein Bildschirmfoto (png) oder eine Aufnahme (mp4)."""
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        if kind == "photo":
            d = user_dir("PICTURES", "Bilder") / "Capture"
            name = f"Capture_{stamp}.png"
        else:
            d = user_dir("VIDEOS", "Videos") / "Capture"
            name = f"Capture_{stamp}.mp4"
        d.mkdir(parents=True, exist_ok=True)
        return str(d / name)

    @Slot(str, result=str)
    def fileUrl(self, path):
        return QUrl.fromLocalFile(path).toString()

    @Slot(str)
    def showInFiles(self, path):
        folder = str(Path(path).parent) if path else str(user_dir("VIDEOS", "Videos") / "Capture")
        prog = ["creative-files", folder] if subprocess.call(["sh", "-c", "command -v creative-files >/dev/null"]) == 0 \
            else ["xdg-open", folder]
        subprocess.Popen(prog, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @Slot(str, str, result=int)
    def matchScore(self, video_name, audio_name):
        """Wie gut passt ein Audiogerät zur Capture-Karte? (gleiche Wörter im Namen)"""
        stop = {"usb", "audio", "video", "device", "capture", "stereo", "analog", "digital", "input", "mono", "-"}
        a = {w for w in video_name.lower().replace(":", " ").replace("_", " ").split() if w not in stop and len(w) > 1}
        b = {w for w in audio_name.lower().replace(":", " ").replace("_", " ").split() if w not in stop and len(w) > 1}
        return len(a & b)


def _raise_running():
    from PySide6.QtNetwork import QLocalSocket
    sock = QLocalSocket()
    sock.connectToServer(SERVER)
    if not sock.waitForConnected(400):
        return False
    sock.write(b"raise")
    sock.waitForBytesWritten(400)
    return True


def main():
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Creative Capture")
    app.setOrganizationName("Creative OS")
    app.setDesktopFileName("creative-capture")
    app.setWindowIcon(QIcon.fromTheme("creative-capture"))
    if "--selftest" not in sys.argv and _raise_running():
        return 0
    engine = QQmlApplicationEngine()
    for d in (HERE.parent.parent / "shell" / "creative_shell" / "qml", Path("/usr/lib/creative-shell/creative_shell/qml")):
        if (d / "Creative" / "qmldir").exists():
            engine.addImportPath(str(d))
            break
    cap = Capture()
    engine.rootContext().setContextProperty("capture", cap)
    engine.rootContext().setContextProperty("selftest", "--selftest" in sys.argv)
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    if "--selftest" in sys.argv:
        print("Creative Capture: Selbsttest bestanden")
        return 0
    win = engine.rootObjects()[0]
    from PySide6.QtNetwork import QLocalServer
    server = QLocalServer()
    QLocalServer.removeServer(SERVER)
    server.listen(SERVER)

    def on_conn():
        c = server.nextPendingConnection()
        if c is not None:
            c.readyRead.connect(lambda: (c.readAll(), win.show(), win.raise_(), win.requestActivate()))

    server.newConnection.connect(on_conn)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    t = QTimer()
    t.start(300)
    t.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
