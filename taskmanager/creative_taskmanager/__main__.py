"""Startpunkt: `creative-taskmanager [--leistung | --autostart | --details]`."""

import os
import signal
import sys
from pathlib import Path

# Gemeinsame Teile der Creative Shell (Messfühler, Symbole, Design)
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
    app.setApplicationName("Taskmanager")
    app.setOrganizationName("Creative OS")
    app.setDesktopFileName("creative-taskmanager")
    app.setWindowIcon(QIcon.fromTheme("creative-taskmanager"))

    from creative_shell.icons import IconFiles
    from .backend import TaskManager

    engine = QQmlApplicationEngine()
    for d in (HERE.parent.parent / "shell" / "creative_shell" / "qml", Path("/usr/lib/creative-shell/creative_shell/qml")):
        if (d / "Creative" / "qmldir").exists():
            engine.addImportPath(str(d))
            break
    icon_files = IconFiles()
    engine.rootContext().setContextProperty("iconFiles", icon_files)

    page = "processes"
    for flag, name in (("--leistung", "performance"), ("--autostart", "startup"), ("--details", "details")):
        if flag in sys.argv:
            page = name
    tm = TaskManager()
    ctx = engine.rootContext()
    ctx.setContextProperty("tm", tm)
    ctx.setContextProperty("startPage", page)
    selftest = "--selftest" in sys.argv
    if selftest:
        problems = []
        engine.warnings.connect(lambda ws: problems.extend(w.toString() for w in ws))
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    if selftest:
        # Ohne Bildschirm einmal alle Seiten durchschalten und Warnungen ausgeben
        win = engine.rootObjects()[0]
        pages = ["processes", "performance", "startup", "details"]

        def step():
            if pages:
                win.setProperty("page", pages.pop(0))
                QTimer.singleShot(1800, step)
            else:
                for p in problems:
                    print("TASKMANAGER-WARNUNG", p)
                print("Taskmanager: Selbsttest", "mit Warnungen" if problems else "bestanden")
                app.exit(0)
        QTimer.singleShot(2000, step)

    signal.signal(signal.SIGINT, lambda *_: app.quit())
    ticker = QTimer()
    ticker.start(300)
    ticker.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
