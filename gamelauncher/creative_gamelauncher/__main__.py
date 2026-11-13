"""Game Launcher – Steam-Spiele im Vollbild mit dem Controller starten (wie Big Picture).

  creative-gamelauncher              Vollbild auf dem Hauptbildschirm
  creative-gamelauncher --fenster    im Fenster (zum Ausprobieren)
  creative-gamelauncher --foto BILD  nach dem Laden ein Foto speichern (Prüfung)
  creative-gamelauncher --selftest   ohne Bildschirm laden und Warnungen melden
"""

import signal
import sys
from pathlib import Path

for _p in (Path(__file__).resolve().parent.parent.parent / "shell", Path("/usr/lib/creative-shell")):
    if (_p / "creative_shell").is_dir() and str(_p) not in sys.path:
        sys.path.append(str(_p))
        break

from PySide6.QtCore import QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication, QIcon  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

HERE = Path(__file__).resolve().parent


def main():
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Game Launcher")
    app.setOrganizationName("Creative OS")
    app.setDesktopFileName("creative-gamelauncher")
    app.setWindowIcon(QIcon.fromTheme("input-gaming"))

    from creative_shell.mainthread import install
    from .backend import Launcher
    _timer = install()  # noqa: F841

    engine = QQmlApplicationEngine()
    for d in (HERE.parent.parent / "shell" / "creative_shell" / "qml", Path("/usr/lib/creative-shell/creative_shell/qml")):
        if (d / "Creative" / "qmldir").exists():
            engine.addImportPath(str(d))
            break
    launcher = Launcher()
    engine.rootContext().setContextProperty("launcher", launcher)
    engine.quit.connect(app.quit)
    problems = []
    engine.warnings.connect(lambda ws: problems.extend(w.toString() for w in ws))
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        print("\n".join(problems))
        return 1
    win = engine.rootObjects()[0]
    signal.signal(signal.SIGINT, lambda *_: app.quit())

    if "--selftest" in sys.argv:
        def done():
            for p in problems:
                print("QML:", p)
            app.exit(1 if problems else 0)
        QTimer.singleShot(1500, done)
        return app.exec()

    # Nur auf dem Hauptbildschirm, im Vollbild
    screen = app.primaryScreen()
    if screen is not None:
        win.setScreen(screen)
        win.setGeometry(screen.geometry())
    if "--fenster" in sys.argv or "--foto" in sys.argv:
        win.resize(1920, 1080)
        win.show()
    else:
        win.showFullScreen()

    if "--foto" in sys.argv:
        target = sys.argv[sys.argv.index("--foto") + 1]
        wait = 4000
        if "--warten" in sys.argv:
            wait = int(sys.argv[sys.argv.index("--warten") + 1])

        def shot():
            win.grabWindow().save(target)
            for p in problems:
                print("QML:", p)
            print("Foto:", target)
            app.quit()
        QTimer.singleShot(wait, shot)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
