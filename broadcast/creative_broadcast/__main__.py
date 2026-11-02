"""Startpunkt der Bedienung: `creative-broadcast`."""

import os
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

HERE = Path(__file__).resolve().parent
SERVER = f"creative-broadcast-{os.getuid()}"


def _raise_running():
    """Läuft das Fenster schon, wird es nur nach vorn geholt (kein zweites Fenster)."""
    from PySide6.QtNetwork import QLocalSocket
    sock = QLocalSocket()
    sock.connectToServer(SERVER)
    if not sock.waitForConnected(400):
        return False
    sock.write(b"raise")
    sock.waitForBytesWritten(400)
    sock.disconnectFromServer()
    return True


def main():
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Creative Broadcast")
    app.setOrganizationName("Creative OS")
    app.setDesktopFileName("creative-broadcast")
    app.setWindowIcon(QIcon.fromTheme("creative-broadcast"))
    if "--selftest" not in sys.argv and _raise_running():
        return 0
    from .ui import Broadcast
    engine = QQmlApplicationEngine()
    for d in (HERE.parent.parent / "shell" / "creative_shell" / "qml", Path("/usr/lib/creative-shell/creative_shell/qml")):
        if (d / "Creative" / "qmldir").exists():
            engine.addImportPath(str(d))
            break
    bc = Broadcast()
    engine.rootContext().setContextProperty("bc", bc)
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    if "--selftest" in sys.argv:
        print("Creative Broadcast: Oberfläche ok")
        return 0
    win = engine.rootObjects()[0]
    from PySide6.QtNetwork import QLocalServer
    server = QLocalServer()
    QLocalServer.removeServer(SERVER)
    server.listen(SERVER)

    def on_conn():
        c = server.nextPendingConnection()
        if c is None:
            return
        c.readyRead.connect(lambda: (c.readAll(), win.show(), win.raise_(), win.requestActivate()))

    server.newConnection.connect(on_conn)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    t = QTimer()
    t.start(300)
    t.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
