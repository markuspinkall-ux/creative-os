"""Startpunkt: `creative-media [Datei …]`.

Mit Dateien als Argument (z. B. Doppelklick im Dateimanager) werden diese
sofort abgespielt.
"""

import os
import signal
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .iptv import IptvModel
from .library import LibraryModel
from .settings import Settings
from .ytmusic import YtMusicModel

HERE = Path(__file__).resolve().parent


def creative_qml_dirs():
    """Fundorte des gemeinsamen Creative-Designs (Theme, Knöpfe, Symbole)."""
    return [
        HERE.parent.parent / "shell" / "creative_shell" / "qml",   # Entwicklung
        Path("/usr/lib/creative-shell/creative_shell/qml"),         # installiert
    ]


def main():
    # Eigener Look nur für dieses Programm (nicht an gestartete Apps vererben)
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Creative Player")
    app.setOrganizationName("Creative OS")
    app.setDesktopFileName("creative-player")
    app.setWindowIcon(QIcon.fromTheme("creative-player", QIcon.fromTheme("multimedia-player")))

    engine = QQmlApplicationEngine()
    for d in creative_qml_dirs():
        if (d / "Creative" / "qmldir").exists():
            engine.addImportPath(str(d))
            break
    else:
        print("creative-media: Creative-Design nicht gefunden (Creative Shell installiert?)")
        return 1

    settings = Settings()
    music = LibraryModel("music")
    videos = LibraryModel("video")
    iptv = IptvModel(settings)
    ytmusic = YtMusicModel()

    files = [QUrl.fromLocalFile(str(Path(a).resolve())).toString()
             for a in sys.argv[1:] if not a.startswith("-") and Path(a).exists()]

    ctx = engine.rootContext()
    ctx.setContextProperty("settings", settings)
    ctx.setContextProperty("music", music)
    ctx.setContextProperty("videos", videos)
    ctx.setContextProperty("iptv", iptv)
    ctx.setContextProperty("ytmusic", ytmusic)
    ctx.setContextProperty("startFiles", files)

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
