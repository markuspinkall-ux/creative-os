"""Startpunkt: `creative-media [Datei …]`.

Mit Dateien als Argument (z. B. Doppelklick im Dateimanager) werden diese
sofort abgespielt.
"""

import json
import os
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .iptv import IptvModel
from .library import LibraryModel
from .settings import Settings
from .ytmusic import YtMusicModel
from .nowplaying import NowPlayingWriter

HERE = Path(__file__).resolve().parent


def creative_qml_dirs():
    """Fundorte des gemeinsamen Creative-Designs (Theme, Knöpfe, Symbole)."""
    return [
        HERE.parent.parent / "shell" / "creative_shell" / "qml",   # Entwicklung
        Path("/usr/lib/creative-shell/creative_shell/qml"),         # installiert
    ]


SERVER = f"creative-player-{os.getuid()}"


def _send_to_running(msg):
    """Läuft der Player schon, bekommt er den Befehl (z. B. vom Sprachassistenten)."""
    from PySide6.QtNetwork import QLocalSocket
    sock = QLocalSocket()
    sock.connectToServer(SERVER)
    if not sock.waitForConnected(400):
        return False
    sock.write(json.dumps(msg).encode())
    sock.flush()
    sock.waitForBytesWritten(1000)
    sock.disconnectFromServer()
    return True


def _cli_message(argv):
    """creative-player --ytmusic "suche" | --ytmusic-cmd pause|play|toggle|next|prev|stop"""
    if "--ytmusic" in argv:
        i = argv.index("--ytmusic")
        return {"cmd": "ytplay", "q": argv[i + 1] if i + 1 < len(argv) else ""}
    if "--ytmusic-cmd" in argv:
        i = argv.index("--ytmusic-cmd")
        return {"cmd": argv[i + 1] if i + 1 < len(argv) else ""}
    return None


def main():
    # Eingebauter Browser-Baustein für YouTube Music (offizielle Webseite) –
    # muss vor dem Programm selbst vorbereitet werden
    web_ok = False
    try:
        from PySide6.QtWebEngineQuick import QtWebEngineQuick
        QtWebEngineQuick.initialize()
        web_ok = True
    except Exception as exc:
        print(f"creative-media: kein eingebauter Browser ({exc}) – YouTube Music öffnet sich extern")

    # Eigener Look nur für dieses Programm (nicht an gestartete Apps vererben)
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)

    msg = _cli_message(sys.argv)
    files_given = [a for a in sys.argv[1:] if not a.startswith("-") and Path(a).exists()]
    if "--selftest" not in sys.argv and (msg or not files_given):
        if _send_to_running(msg or {"cmd": "raise"}):
            return 0
    app.setApplicationName("Creative Player")
    app.setOrganizationName("Creative OS")
    app.setDesktopFileName("creative-player")
    app.setWindowIcon(QIcon.fromTheme("creative-player", QIcon.fromTheme("multimedia-player")))

    engine = QQmlApplicationEngine()
    for d in creative_qml_dirs():
        if (d / "Creative" / "qmldir").exists():
            engine.addImportPath(str(d))
            break
    else:
        print("creative-media: Creative-Design nicht gefunden (Creative Shell installiert?)")
        return 1

    settings = Settings()
    music = LibraryModel("music")
    videos = LibraryModel("video")
    iptv = IptvModel(settings)
    ytmusic = YtMusicModel()
    nowplaying = NowPlayingWriter()
    app.aboutToQuit.connect(nowplaying.clear)

    files = [QUrl.fromLocalFile(str(Path(a).resolve())).toString()
             for a in sys.argv[1:] if not a.startswith("-") and Path(a).exists()]

    ctx = engine.rootContext()
    ctx.setContextProperty("settings", settings)
    ctx.setContextProperty("music", music)
    ctx.setContextProperty("videos", videos)
    ctx.setContextProperty("iptv", iptv)
    ctx.setContextProperty("ytmusic", ytmusic)
    ctx.setContextProperty("nowplaying", nowplaying)
    ctx.setContextProperty("startFiles", files)
    ctx.setContextProperty("webEngineAvailable", web_ok)

    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    win = engine.rootObjects()[0]
    if "--selftest" in sys.argv:
        print("Creative Player: Selbsttest bestanden", "(mit eingebautem Browser)" if web_ok else "(ohne Browser)")
        return 0

    # Befehle von außen (Sprachassistent, zweiter Start)
    from PySide6.QtNetwork import QLocalServer
    server = QLocalServer()
    QLocalServer.removeServer(SERVER)
    server.listen(SERVER)

    def handle(m):
        cmd = m.get("cmd")
        if cmd == "ytplay":
            win.setProperty("section", "ytmusic")
            if m.get("q"):
                ytmusic.search_and_play(m["q"])
            win.raise_() if hasattr(win, "raise_") else None
            win.requestActivate()
        elif cmd in ("play", "pause", "toggle", "next", "prev", "stop"):
            ytmusic.send(cmd)
        elif cmd == "raise":
            win.show()
            win.raise_()
            win.requestActivate()

    def incoming():
        sock = server.nextPendingConnection()
        if sock is None:
            return

        def read():
            try:
                handle(json.loads(bytes(sock.readAll()).decode() or "{}"))
            except ValueError:
                pass
        sock.readyRead.connect(read)
        sock.disconnected.connect(sock.deleteLater)
    server.newConnection.connect(incoming)
    if msg:
        QTimer.singleShot(300, lambda: handle(msg))

    signal.signal(signal.SIGINT, lambda *_: app.quit())
    ticker = QTimer()
    ticker.start(300)
    ticker.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
