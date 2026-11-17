"""Messenger-Fenster (öffnet sich aus dem Tray). Schließen beendet nur das Fenster – der Dienst und
das Tray-Symbol laufen weiter. Ein zweiter Aufruf holt das offene Fenster nach vorn.

    orbit-messenger-window [orbit-id]
"""

import os
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .messenger import MessengerModel

QML_DIR = Path(__file__).resolve().parent / "qml"
INSTANCE = f"orbit-messenger-window-{os.getuid()}"


def hand_over(chat):
    """Läuft schon ein Fenster? Dann ihm den Chat geben und selbst gehen."""
    sock = QLocalSocket()
    sock.connectToServer(INSTANCE)
    if not sock.waitForConnected(300):
        return False
    sock.write((chat + "\n").encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(300)
    sock.disconnectFromServer()
    return True


def main():
    chat = sys.argv[1] if len(sys.argv) > 1 else ""
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Messenger")
    app.setDesktopFileName("orbit-messenger")
    app.setWindowIcon(QIcon.fromTheme("orbit-messenger"))
    if hand_over(chat):
        return 0
    QLocalServer.removeServer(INSTANCE)
    server = QLocalServer()
    server.listen(INSTANCE)

    model = MessengerModel()
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))
    engine.rootContext().setContextProperty("messenger", model)
    engine.rootContext().setContextProperty("startChat", chat)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "messenger" / "MessengerWindow.qml")))
    if not engine.rootObjects():
        return 1
    win = engine.rootObjects()[0]

    def incoming():
        conn = server.nextPendingConnection()
        if conn is None:
            return

        def read():
            wanted = bytes(conn.readAll()).decode("utf-8", "ignore").strip()
            if wanted:
                model.openChat(wanted)
            win.show()
            win.raise_()
            win.requestActivate()
        conn.readyRead.connect(read)
        conn.disconnected.connect(lambda: (read(), conn.deleteLater()))
    server.newConnection.connect(incoming)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
