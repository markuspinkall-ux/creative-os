"""Startpunkt: `gibeon-android` (mit `--store` direkt den Play Store öffnen)."""

import os
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

HERE = Path(__file__).resolve().parent
SERVER = f"gibeon-android-{os.getuid()}"


def _raise_running(msg):
    from PySide6.QtNetwork import QLocalSocket
    sock = QLocalSocket()
    sock.connectToServer(SERVER)
    if not sock.waitForConnected(400):
        return False
    sock.write(msg)
    sock.waitForBytesWritten(400)
    return True


def main():
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Android-Apps")
    app.setOrganizationName("Gibeon OS")
    app.setDesktopFileName("gibeon-android")
    app.setWindowIcon(QIcon.fromTheme("gibeon-android"))
    store = "--store" in sys.argv
    if "--selftest" not in sys.argv and _raise_running(b"store" if store else b"raise"):
        return 0
    from .backend import Android
    engine = QQmlApplicationEngine()
    for d in (HERE.parent.parent / "shell" / "creative_shell" / "qml", Path("/usr/lib/creative-shell/creative_shell/qml")):
        if (d / "Creative" / "qmldir").exists():
            engine.addImportPath(str(d))
            break
    android = Android(selftest="--selftest" in sys.argv)
    engine.rootContext().setContextProperty("android", android)
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    if "--selftest" in sys.argv:
        print("Android-Apps: Selbsttest bestanden")
        return 0
    win = engine.rootObjects()[0]
    if store:
        android.openStore()
    from PySide6.QtNetwork import QLocalServer
    server = QLocalServer()
    QLocalServer.removeServer(SERVER)
    server.listen(SERVER)

    def on_conn():
        c = server.nextPendingConnection()
        if c is None:
            return

        def got():
            if bytes(c.readAll()) == b"store":
                android.openStore()
            win.show()
            win.raise_()
            win.requestActivate()
        c.readyRead.connect(got)

    server.newConnection.connect(on_conn)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    t = QTimer()
    t.start(300)
    t.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
