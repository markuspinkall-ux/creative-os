"""Capture – Bild und Ton einer Capture-Karte (HDMI-Grabber, Cam Link …) anzeigen.

Startpunkt: `creative-capture`. Die Anzeige läuft über Qt Multimedia (V4L2 + PipeWire).
"""

import json
import shutil
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .audio_routing import matching_audio

from PySide6.QtCore import Property, QObject, QProcess, QTimer, QUrl, Signal, Slot
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


from .audio_routing import MONITOR_TAG  # noqa: E402


class Capture(QObject):
    changed = Signal()
    toast = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cfg = {"video": "", "audio": "", "format": "", "volume": 1.0, "muted": False, "audioByVideo": {}, "monitorChannels": {}}
        self._monitor = QProcess(self)
        self._monitor.setStandardErrorFile(QProcess.nullDevice())
        self._monitor.setStandardOutputFile(QProcess.nullDevice())
        self._monitor_active = False
        self._monitor.errorOccurred.connect(self._monitor_error)
        self._monitor.finished.connect(self._monitor_finished)
        QGuiApplication.instance().aboutToQuit.connect(self.stopMonitor)
        self._kill_stale_monitors()
        try:
            data = json.loads(CFG.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._cfg.update({k: v for k, v in data.items() if k in self._cfg})
        except (OSError, ValueError):
            pass

    def _kill_stale_monitors(self):
        """Nach einem Absturz kann eine alte Ton-Wiedergabe weiterlaufen – dann hört man alles doppelt."""
        from .audio_routing import stale_monitors
        try:
            out = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True, timeout=3).stdout
        except (OSError, subprocess.SubprocessError):
            return
        for pid in stale_monitors(out):
            try:
                os.kill(pid, 15)
            except OSError:
                pass

    @Slot(str, str)
    def checkEcho(self, source, video_id):
        """Warnen, wenn der Ton der Capture-Karte schon woanders läuft oder ein Mikrofon gewählt ist."""
        from .audio_routing import is_capture_audio, other_players
        try:
            out = subprocess.run(["pactl", "-f", "json", "list", "sink-inputs"], capture_output=True, text=True,
                                 timeout=3).stdout
            others = other_players(json.loads(out or "[]"), source)
        except (OSError, ValueError, subprocess.SubprocessError):
            others = []
        if others:
            self.toast.emit(f"{others[0]} spielt den Ton der Capture-Karte schon ab – darum hörst du ihn doppelt "
                            "(Echo). Dort das Mithören ausschalten.")
        elif source and video_id and not is_capture_audio(source, video_id):
            self.toast.emit("Als Tonquelle ist ein Mikrofon gewählt – das kann pfeifen (Rückkopplung). "
                            "Unter „Tonquelle“ den HDMI-Ton der Capture-Karte wählen.")

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

    @Slot("QVariant", result=str)
    def deviceKey(self, value):
        if isinstance(value, str):
            return value
        try:
            return bytes(value).decode("utf-8")
        except (TypeError, ValueError, UnicodeDecodeError):
            return ""

    @Slot("QVariant", result=bool)
    def isCaptureCard(self, value):
        """Nur Capture-Karten (Elgato, AVerMedia Live Gamer Mini usw.) – Webcams nicht."""
        from .audio_routing import capture_card
        return bool(capture_card(self.deviceKey(value)))

    @Slot(str, result=int)
    def channelCount(self, source):
        try:
            result = subprocess.run(["pactl", "-f", "json", "list", "sources"],
                                    capture_output=True, text=True, timeout=2, check=True)
            for device in json.loads(result.stdout):
                if device.get("name") == source and not source.endswith(".monitor"):
                    channel_map = device.get("channel_map") or ""
                    return min(32, len(channel_map.split(","))) if channel_map else 0
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        return 0

    @Slot(str, result=int)
    def savedChannel(self, source):
        mapping = self._cfg["monitorChannels"]
        channel = mapping.get(source, 0) if isinstance(mapping, dict) else 0
        return channel if type(channel) is int and channel > 0 else 0

    @Slot(str, int)
    def saveChannel(self, source, channel):
        mapping = self._cfg["monitorChannels"]
        if not isinstance(mapping, dict):
            mapping = {}
        self.set("monitorChannels", {**mapping, source: channel})

    @Slot()
    def stopMonitor(self):
        self._monitor_active = False
        if self._monitor.state() != QProcess.ProcessState.NotRunning:
            self._monitor.kill()
            self._monitor.waitForFinished(500)

    def _monitor_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self._monitor_finished()

    def _monitor_finished(self, *_args):
        if self._monitor_active:
            self._monitor_active = False
            self.toast.emit("Der gewählte Tonkanal konnte nicht wiedergegeben werden.")

    @Slot(str, int, int, float)
    def playChannel(self, source, channels, channel, volume):
        self.stopMonitor()
        if not source or source.endswith(".monitor") or not 1 <= channel <= channels <= 32:
            return
        selected = channel - 1
        gain = max(0.0, min(1.0, volume))
        self._monitor_active = True
        # setpriv --pdeathsig: endet Capture (auch durch Absturz), endet die Wiedergabe mit –
        # sonst läuft sie weiter und beim nächsten Start hört man den Ton doppelt
        args = ["-nostdin", "-loglevel", "error", "-f", "pulse", "-channels", str(channels),
                "-fragment_size", "4096", "-name", MONITOR_TAG, "-i", source,
                "-af", f"pan=stereo|c0=c{selected}|c1=c{selected},volume={gain}",
                "-f", "pulse", "-name", MONITOR_TAG, "-buffer_duration", "50", "Capture"]
        if shutil.which("setpriv"):
            self._monitor.start("setpriv", ["--pdeathsig", "KILL", "ffmpeg", *args])
        else:
            self._monitor.start("ffmpeg", args)

    @Slot(str, result=str)
    def savedAudio(self, video_id):
        mapping = self._cfg.get("audioByVideo")
        return mapping.get(video_id, "") if isinstance(mapping, dict) else ""

    @Slot(str, str)
    def saveAudio(self, video_id, audio_id):
        if not video_id:
            return
        mapping = self._cfg.get("audioByVideo")
        if not isinstance(mapping, dict):
            mapping = {}
        self._cfg["audioByVideo"] = {**mapping, video_id: audio_id}
        self._save()
        self.changed.emit()

    @Slot(str, "QVariantList", result=str)
    def matchedAudio(self, video_id, candidates):
        match = matching_audio(video_id, candidates)
        return match if match in self.captureAudio(video_id) else ""

    @Slot(str, result="QStringList")
    def captureAudio(self, video_id):
        """Nur Tonquellen von Capture-Karten – nie das Mikrofon einer Webcam oder ein Headset."""
        from .audio_routing import capture_audio_ids
        return capture_audio_ids(video_id)


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
        print("Capture: Selbsttest bestanden")
        return 0
    win = engine.rootObjects()[0]
    from .wach import WachHalten
    wach = WachHalten().start()                 # solange Capture offen ist: kein Standby
    app.aboutToQuit.connect(wach.stop)
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
