"""Startpunkt: `creative-settings [--page netzwerk|bildschirme|ton|drucker|darstellung|updates|system]`."""

import argparse
import signal
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHELL_DIRS = [HERE.parent.parent / "shell", Path("/usr/lib/creative-shell")]
for d in SHELL_DIRS:
    if (d / "creative_shell").is_dir():
        sys.path.insert(0, str(d))
        break

from PySide6.QtCore import QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QFont, QGuiApplication, QIcon  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

from creative_shell.network import NetworkModel  # noqa: E402
from creative_shell.session import SessionModel  # noqa: E402

from .displays import DisplayModel  # noqa: E402
from .server import ServerModel  # noqa: E402
from .sound import SoundModel  # noqa: E402
from .system import LookModel, PrinterListModel, SystemModel  # noqa: E402

PAGES = {
    "network": "network", "netzwerk": "network", "wlan": "network",
    "displays": "displays", "bildschirme": "displays", "display": "displays",
    "sound": "sound", "ton": "sound",
    "printers": "printers", "drucker": "printers",
    "look": "look", "darstellung": "look", "hintergrund": "look", "wallpaper": "look",
    "updates": "updates", "system": "system",
    "server": "server", "meinserver": "server", "mein-server": "server",
}


def main():
    parser = argparse.ArgumentParser(prog="creative-settings")
    parser.add_argument("--page", default="network")
    args, _rest = parser.parse_known_args()

    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Systemsteuerung")
    app.setOrganizationName("Creative OS")
    app.setDesktopFileName("creative-settings")
    app.setWindowIcon(QIcon.fromTheme("creative-settings", QIcon.fromTheme("preferences-system")))
    app.setFont(QFont("Arial", 10))

    engine = QQmlApplicationEngine()
    qml_root = next((d / "creative_shell" / "qml" for d in SHELL_DIRS if (d / "creative_shell" / "qml").is_dir()), None)
    if qml_root is None:
        print("creative-settings: Creative-Design nicht gefunden (Creative Shell installiert?)")
        return 1
    engine.addImportPath(str(qml_root))

    models = {
        "network": NetworkModel(),
        "session": SessionModel(),
        "displays": DisplayModel(),
        "sound": SoundModel(),
        "system": SystemModel(),
        "printerList": PrinterListModel(),
        "server": ServerModel(),
        "look": LookModel(qml_root / "Creative" / "wallpapers"),
    }
    ctx = engine.rootContext()
    for name, model in models.items():
        ctx.setContextProperty(name, model)
    ctx.setContextProperty("startPage", PAGES.get(args.page.lower(), "network"))

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
