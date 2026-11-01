"""Startpunkt: `creative-welcome` – zeigt sich einmal nach der ersten Anmeldung.

Mit `--force` erscheint er erneut (z. B. zum Ausprobieren).
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOTS = [HERE.parent.parent, Path("/usr/lib")]
for name, pkg in (("shell", "creative_shell"), ("settings", "creative_settings")):
    for base in (HERE.parent.parent / name, Path(f"/usr/lib/creative-{name}")):
        if (base / pkg).is_dir():
            sys.path.insert(0, str(base))
            break

from PySide6.QtCore import QObject, QTimer, QUrl, Slot  # noqa: E402
from PySide6.QtGui import QFont, QGuiApplication, QIcon  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

from creative_shell import config as shell_config  # noqa: E402
from creative_shell.network import NetworkModel  # noqa: E402
from creative_shell.runner import spawn_detached  # noqa: E402
from creative_shell.session import SessionModel  # noqa: E402
from creative_settings.system import LookModel  # noqa: E402

MARKER = shell_config.config_dir() / "welcome-done"


class Welcome(QObject):
    @Slot()
    def finish(self):
        MARKER.parent.mkdir(parents=True, exist_ok=True)
        MARKER.write_text("1\n")
        QGuiApplication.quit()

    @Slot(str)
    def openSettings(self, page):
        spawn_detached(["creative-settings", "--page", page])


def main():
    if MARKER.exists() and "--force" not in sys.argv:
        return 0
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Willkommen")
    app.setDesktopFileName("creative-welcome")
    app.setWindowIcon(QIcon.fromTheme("creative-settings"))
    app.setFont(QFont("Arial", 10))

    engine = QQmlApplicationEngine()
    qml_root = next((Path(p) / "creative_shell" / "qml" for p in sys.path
                     if (Path(p) / "creative_shell" / "qml" / "Creative").is_dir()), None)
    if qml_root is None:
        print("creative-welcome: Creative-Design nicht gefunden")
        return 1
    engine.addImportPath(str(qml_root))

    welcome = Welcome()
    ctx = engine.rootContext()
    ctx.setContextProperty("welcome", welcome)
    ctx.setContextProperty("network", NetworkModel())
    ctx.setContextProperty("session", SessionModel())
    ctx.setContextProperty("look", LookModel(qml_root / "Creative" / "wallpapers"))
    ctx.setContextProperty("wallpaperUrl", QUrl.fromLocalFile(str(qml_root / "Creative" / "wallpapers" / "graphit.svg")))
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    ticker = QTimer()
    ticker.start(300)
    ticker.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
