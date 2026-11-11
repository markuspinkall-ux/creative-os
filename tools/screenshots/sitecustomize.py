"""Bildschirmfoto-Haken für die Oberflächentests im Build.

Wird nur geladen, wenn dieser Ordner im PYTHONPATH liegt und
CREATIVE_SCREENSHOT=/pfad/bild.png gesetzt ist. Dann fotografiert jede
PySide6-App ihr größtes sichtbares Fenster kurz nach dem Start (Widgets und
QML) und beendet sich wieder. Die Apps selbst bleiben unverändert.
"""

import os
import sys

TARGET = os.environ.get("CREATIVE_SCREENSHOT")
DELAY = int(os.environ.get("CREATIVE_SCREENSHOT_DELAY", "3000"))


def _install():
    from PySide6 import QtGui
    from PySide6.QtCore import QCoreApplication, QTimer
    try:
        from PySide6 import QtWidgets
    except ImportError:
        QtWidgets = None
    state = {"armed": False}

    def shoot():
        app = QCoreApplication.instance()
        images = []
        if QtWidgets is not None and isinstance(app, QtWidgets.QApplication):
            for widget in app.topLevelWidgets():
                if widget.isVisible() and widget.width() >= 120 and widget.height() >= 80:
                    images.append(widget.grab().toImage())
        try:
            from PySide6.QtQuick import QQuickWindow
            for window in QtGui.QGuiApplication.topLevelWindows():
                if isinstance(window, QQuickWindow) and window.isVisible():
                    images.append(window.grabWindow())
        except ImportError:
            pass
        images = [image for image in images if not image.isNull()]
        if images:
            biggest = max(images, key=lambda image: image.width() * image.height())
            if biggest.save(TARGET):
                print(f"Bildschirmfoto gespeichert: {TARGET} ({biggest.width()}×{biggest.height()})", file=sys.stderr)
        else:
            print(f"Kein sichtbares Fenster für {TARGET}", file=sys.stderr)
        sys.stderr.flush()
        os._exit(0)

    def arm():
        if not state["armed"]:
            state["armed"] = True
            QTimer.singleShot(DELAY, shoot)

    classes = [QtGui.QGuiApplication, QCoreApplication]
    if QtWidgets is not None:
        classes.insert(0, QtWidgets.QApplication)
    for cls in classes:
        for name in ("exec", "exec_"):
            original = getattr(cls, name, None)
            if original is None:
                continue

            def patched(*args, _original=original):
                # exec() ist in PySide statisch: Aufruf als app.exec() oder QApplication.exec()
                arm()
                return _original()

            setattr(cls, name, patched)


if TARGET:
    try:
        _install()
    except Exception as error:  # noqa: BLE001 – Test-Haken darf die App nie verhindern
        print(f"Bildschirmfoto-Haken nicht aktiv: {error}", file=sys.stderr)
