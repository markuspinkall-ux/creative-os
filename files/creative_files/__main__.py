"""Startpunkt: `creative-files [Ordner]`.

`creative-files --open-with Datei …` zeigt nur das Fenster „Öffnen mit“
(für den Rechtsklick auf dem Schreibtisch).
"""

import os
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .backend import FileManager
from .chooser import OpenWithChooser

HERE = Path(__file__).resolve().parent


def creative_qml_dirs():
    return [
        HERE.parent.parent / "shell" / "creative_shell" / "qml",   # Entwicklung
        Path("/usr/lib/creative-shell/creative_shell/qml"),         # installiert
    ]


def icon_files():
    """Runde App-Symbole wie im Startmenü (aus der Shell) – fehlt sie, gibt es Ersatzsymbole."""
    for d in (HERE.parent.parent / "shell", Path("/usr/lib/creative-shell")):
        if (d / "creative_shell").is_dir() and str(d) not in sys.path:
            sys.path.append(str(d))
    try:
        from creative_shell.icons import IconFiles
        return IconFiles()
    except Exception:  # noqa: BLE001
        return None


def open_with_paths(args):
    paths = []
    for a in args:
        if a.startswith("-"):
            continue
        if a.startswith("file://"):
            a = QUrl(a).toLocalFile()
        p = Path(a).expanduser()
        if p.is_file():
            paths.append(str(p.resolve()))
    return paths


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
    if sys.argv[1:] == ["--empty-trash"]:
        from .fsops import empty_trash

        try:
            empty_trash()
        except OSError as exc:
            print(exc, file=sys.stderr)
            return 1
        return 0

    # Eigener Look nur für dieses Programm (nicht an gestartete Apps vererben)
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    open_with_mode = "--open-with" in sys.argv
    app.setApplicationName("Öffnen mit" if open_with_mode else "Dateien")
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
        print("creative-files: Gibeon-Design nicht gefunden (Shell installiert?)")
        return 1

    chooser = OpenWithChooser()
    icons = icon_files()
    ctx = engine.rootContext()
    ctx.setContextProperty("openWith", chooser)
    ctx.setContextProperty("iconFiles", icons)
    if open_with_mode:
        ctx.setContextProperty("openWithPaths", open_with_paths(sys.argv[1:]))
        engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "OpenWithWindow.qml")))
        if not engine.rootObjects():
            return 1
        signal.signal(signal.SIGINT, lambda *_: app.quit())
        return app.exec()

    start = start_folder(sys.argv[1:])
    fm = FileManager(None if start == "trash:" else start)
    if start == "trash:":
        fm.openPage("trash")
    chooser.message.connect(fm._show_toast)
    ctx.setContextProperty("fm", fm)
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
