"""Startpunkt: `creative-shots` (Fenster) oder `creative-shots --snip` (sofort Auswahl)."""

import signal
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .backend import Shots

HERE = Path(__file__).resolve().parent


def main():
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Creative Shots")
    app.setOrganizationName("Creative OS")
    app.setDesktopFileName("creative-shots")
    app.setWindowIcon(QIcon.fromTheme("creative-shots"))

    engine = QQmlApplicationEngine()
    for d in (HERE.parent.parent / "shell" / "creative_shell" / "qml", Path("/usr/lib/creative-shell/creative_shell/qml")):
        if (d / "Creative" / "qmldir").exists():
            engine.addImportPath(str(d))
            break
    shots = Shots()
    snip = "--snip" in sys.argv
    shots.set_close_after(snip)
    for m in ("rect", "window", "screen", "free"):
        if f"--{m}" in sys.argv:
            shots.mode = m
    engine.rootContext().setContextProperty("shots", shots)
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    win = engine.rootObjects()[0]
    if "--selftest" in sys.argv:
        from PySide6.QtGui import QImage
        from .backend import paint_strokes
        img = QImage(200, 100, QImage.Format.Format_RGB32)
        img.fill(0xFF202020)
        strokes = [{"tool": t, "color": "#ff5a5a", "width": 4, "pts": [10, 10, 60, 50, 90, 20]}
                   for t in ("pen", "marker", "arrow", "rect")]
        out = paint_strokes(img, strokes)
        assert out.pixelColor(10, 10).red() > 100, "Stift fehlt"
        shots._image = img
        shots.crop(strokes, 5, 5, 50, 40)
        assert shots._image.width() == 50 and shots._image.height() == 40
        print("Creative Shots: Selbsttest bestanden")
        return 0
    if snip:
        QTimer.singleShot(150, shots.startSnip)
    else:
        win.show()

    signal.signal(signal.SIGINT, lambda *_: app.quit())
    ticker = QTimer()
    ticker.start(300)
    ticker.timeout.connect(lambda: None)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
