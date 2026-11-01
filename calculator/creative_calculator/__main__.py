"""Startpunkt: `creative-calculator`."""

import signal
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .calc import Calculator

HERE = Path(__file__).resolve().parent


def main():
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Creative Calculator")
    app.setOrganizationName("Creative OS")
    app.setDesktopFileName("creative-calculator")
    app.setWindowIcon(QIcon.fromTheme("creative-calculator", QIcon.fromTheme("accessories-calculator")))

    engine = QQmlApplicationEngine()
    for d in (HERE.parent.parent / "shell" / "creative_shell" / "qml",
              Path("/usr/lib/creative-shell/creative_shell/qml")):
        if (d / "Creative" / "qmldir").exists():
            engine.addImportPath(str(d))
            break
    else:
        print("creative-calculator: Creative-Design nicht gefunden (Creative Shell installiert?)")
        return 1

    calc = Calculator()
    engine.rootContext().setContextProperty("calc", calc)
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1

    signal.signal(signal.SIGINT, lambda *_: app.quit())
    ticker = QTimer()
    ticker.start(300)
    ticker.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
