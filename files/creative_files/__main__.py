"""Startpunkt: `creative-files [Ordner]`."""

import os
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .backend import FileManager

HERE = Path(__file__).resolve().parent


def creative_qml_dirs():
    return [
        HERE.parent.parent / "shell" / "creative_shell" / "qml",   # Entwicklung
        Path("/usr/lib/creative-shell/creative_shell/qml"),         # installiert
    ]


def start_folder(args):
    for a in args:
        if a.startswith("-"):
            continue
        if a.startswith("file://"):
            a = QUrl(a).toLocalFile()
        p = Path(a).expanduser()
        if p.is_file():
            p = p.parent
        if p.is_dir():
            return str(p.resolve())
        if a in ("trash:", "trash:/", "trash:///"):
            return "trash:"
    return None


def main():
    # Eigener Look nur für dieses Programm (nicht an gestartete Apps vererben)
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Dateien")
    app.setOrganizationName("Creative OS")
    app.setDesktopFileName("creative-files")
    app.setWindowIcon(QIcon.fromTheme("creative-files", QIcon.fromTheme("system-file-manager")))
    app.setFont(QFont("Arial", 10))

    engine = QQmlApplicationEngine()
    for d in creative_qml_dirs():
        if (d / "Creative" / "qmldir").exists():
            engine.addImportPath(str(d))
            break
    else:
        print("creative-files: Creative-Design nicht gefunden (Creative Shell installiert?)")
        return 1

    start = start_folder(sys.argv[1:])
    fm = FileManager(None if start == "trash:" else start)
    if start == "trash:":
        fm.openPage("trash")
    engine.rootContext().setContextProperty("fm", fm)
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
