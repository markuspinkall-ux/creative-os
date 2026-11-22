"""Startpunkt: `gibeon-studio` – Aufnehmen und Streamen (Twitch, YouTube, eigener Server)."""

import os
import signal
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Fester Pfad, damit auch das Stream Deck (Deck) Studio erreicht: eine Textzeile je Befehl
SERVER = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}", "gibeon-studio.sock")


def _raise_running():
    from PySide6.QtNetwork import QLocalSocket
    sock = QLocalSocket()
    sock.connectToServer(SERVER)
    if not sock.waitForConnected(400):
        return False
    sock.write(b"raise\n")
    sock.waitForBytesWritten(400)
    return True


def main():
    selftest = "--selftest" in sys.argv
    try:
        from PySide6.QtWebEngineQuick import QtWebEngineQuick
        QtWebEngineQuick.initialize()
    except Exception as exc:                       # ohne eingebauten Browser fehlt nur der Chat
        print(f"gibeon-studio: kein eingebauter Browser ({exc})")
    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
    from PySide6.QtQuickControls2 import QQuickStyle

    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Studio")
    app.setOrganizationName("Gibeon OS")
    app.setDesktopFileName("gibeon-studio")
    app.setWindowIcon(QIcon.fromTheme("gibeon-studio"))
    if not selftest and _raise_running():
        return 0

    from .backend import Preview, Studio
    qmlRegisterType(Preview, "Studio", 1, 0, "Preview")
    studio = Studio(selftest=selftest)
    if selftest:
        out = os.path.join(tempfile.mkdtemp(), "selbsttest.mp4")
        ok, info = studio.run_selftest(out)
        print(f"Studio: Aufnahme-Test {'bestanden' if ok else 'FEHLGESCHLAGEN'} ({info})")
        if not ok:
            return 1
    engine = QQmlApplicationEngine()
    for d in (HERE.parent.parent / "shell" / "creative_shell" / "qml", Path(os.environ.get("GIBEON_PREFIX") or "/usr") / "lib/creative-shell/creative_shell/qml"):
        if (d / "Creative" / "qmldir").exists():
            engine.addImportPath(str(d))
            break
    engine.rootContext().setContextProperty("studio", studio)
    # Updates nur in der AppImage-Fassung (andere Linux-Systeme); in Gibeon OS kommen sie mit dem System
    from .appupdate import AppUpdate
    app_update = AppUpdate(app)
    engine.rootContext().setContextProperty("appUpdate", app_update)
    if not selftest:
        QTimer.singleShot(4000, app_update.check)
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    if selftest:
        print("Studio: Selbsttest bestanden")
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

        def read():
            while c.canReadLine() or c.bytesAvailable():
                line = bytes(c.readLine()).decode("utf-8", "replace").strip()
                if not line:
                    break
                if line == "raise":
                    win.show(), win.raise_(), win.requestActivate()
                    answer = "ok"
                else:
                    answer = studio.command(line)
                c.write((answer + "\n").encode())
                c.flush()
        c.readyRead.connect(read)
        c.disconnected.connect(c.deleteLater)

    server.newConnection.connect(on_conn)
    app.aboutToQuit.connect(studio.shutdown)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    t = QTimer()
    t.start(300)
    t.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
