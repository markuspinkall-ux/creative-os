"""Creative Deck – Elgato Stream Deck einrichten und nutzen.

  creative-deck                  Editor öffnen (Tasten einrichten)
  creative-deck --hintergrund    Dienst für die Geräte (startet mit der Sitzung)
  creative-deck --foto BILD      Editor laden und ein Foto speichern (Prüfung)
  creative-deck --selftest       ohne Bildschirm laden und Fehler melden
"""

import os
import signal
import sys
from pathlib import Path

for _p in (Path(__file__).resolve().parent.parent.parent / "shell", Path("/usr/lib/creative-shell")):
    if (_p / "creative_shell").is_dir() and str(_p) not in sys.path:
        sys.path.append(str(_p))
        break

HERE = Path(__file__).resolve().parent


def run_daemon():
    # Der Dienst zeichnet nur Tastenbilder – ohne Fenster. Nur für diesen Prozess, NICHT über die
    # Umgebung: sonst erbten gestartete Programme (Player, Terminal …) „offscreen“ und blieben unsichtbar.
    os.environ.pop("QT_QPA_PLATFORM", None)
    from PySide6.QtGui import QGuiApplication, QIcon
    app = QGuiApplication(sys.argv[:1] + ["-platform", "offscreen"] + sys.argv[1:])
    app.setApplicationName("creative-deck-dienst")
    try:
        from creative_shell import icons
        QIcon.setThemeName("CreativePorzellan" if icons._light() else "Creative")
    except Exception:  # noqa: BLE001
        pass
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    from . import daemon
    from PySide6.QtCore import QTimer
    keepalive = QTimer()             # damit Python Signale (SIGTERM) bearbeiten kann
    keepalive.start(500)
    keepalive.timeout.connect(lambda: None)
    return daemon.run(app)


def run_editor(args):
    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle

    from .editor import DeckEditor
    from .render import creative_qml_dir

    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Creative Deck")
    app.setOrganizationName("Creative OS")
    app.setDesktopFileName("creative-deck")
    app.setWindowIcon(QIcon.fromTheme("creative-deck"))

    icon_files = None
    try:
        from creative_shell.icons import IconFiles
        icon_files = IconFiles()
    except Exception:  # noqa: BLE001
        pass
    editor = DeckEditor(icon_files)
    engine = QQmlApplicationEngine()
    qml = creative_qml_dir()
    if qml:
        engine.addImportPath(str(qml))
    warnings = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    engine.rootContext().setContextProperty("deck", editor)
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        print("\n".join(warnings) or "Main.qml lädt nicht", file=sys.stderr)
        return 1
    win = engine.rootObjects()[0]
    app.aboutToQuit.connect(editor.saveNow)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    ticker = QTimer()
    ticker.start(300)
    ticker.timeout.connect(lambda: None)

    if "--foto" in args:
        target = args[args.index("--foto") + 1]
        select = int(os.environ.get("CREATIVE_DECK_TASTE", "0"))
        editor.select(select)

        def shoot():
            win.grabWindow().save(target)
            print("Foto:", target)
            app.quit()
        QTimer.singleShot(int(os.environ.get("CREATIVE_DECK_DELAY", "2500")), shoot)
    if "--selftest" in args:
        def done():
            bad = [w for w in warnings if "Main.qml" in w or "qml" in w.lower()]
            print("\n".join(bad) if bad else "Creative Deck: Editor ok")
            app.exit(1 if bad else 0)
        QTimer.singleShot(1500, done)
    return app.exec()


def main():
    args = sys.argv[1:]
    if "--hintergrund" in args:
        return run_daemon()
    return run_editor(args)


if __name__ == "__main__":
    sys.exit(main())
