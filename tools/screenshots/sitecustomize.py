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

    def scroll_down():
        """CREATIVE_SCREENSHOT_SCROLL=1: lange QML-Seiten ganz nach unten rollen."""
        from PySide6.QtQuick import QQuickWindow
        for window in QtGui.QGuiApplication.topLevelWindows():
            if not isinstance(window, QQuickWindow):
                continue
            stack = [window.contentItem()]
            while stack:
                item = stack.pop()
                stack.extend(item.childItems())
                ch, h = item.property("contentHeight"), item.height()
                if item.property("contentY") is not None and isinstance(ch, (int, float)) and ch > h + 20:
                    item.setProperty("contentY", ch - h)

    def drag_test():
        """CREATIVE_TEST_DRAG="x1,y1,x2,y2": im größten QML-Fenster mit der Maus ziehen (Prüfung)."""
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtQuick import QQuickWindow
        from PySide6.QtTest import QTest
        wins = [w for w in QtGui.QGuiApplication.topLevelWindows() if isinstance(w, QQuickWindow) and w.isVisible()]
        if not wins:
            return
        win = max(wins, key=lambda w: w.width() * w.height())
        x1, y1, x2, y2 = (int(v) for v in os.environ["CREATIVE_TEST_DRAG"].split(","))
        QTest.mousePress(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(x1, y1))
        steps = 12
        for i in range(1, steps + 1):
            QTest.mouseMove(win, QPoint(x1 + (x2 - x1) * i // steps, y1 + (y2 - y1) * i // steps), 20)
        QTest.mouseRelease(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(x2, y2), 30)
        print(f"Ziehen getestet: ({x1},{y1}) → ({x2},{y2})", file=sys.stderr)

    def rename_test():
        """CREATIVE_TEST_RENAME="x,y,Name[,fertig]": Symbol anklicken, F2, Namen tippen (und Eingabe)."""
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtQuick import QQuickWindow
        from PySide6.QtTest import QTest
        wins = [w for w in QtGui.QGuiApplication.topLevelWindows() if isinstance(w, QQuickWindow) and w.isVisible()]
        win = max(wins, key=lambda w: w.width() * w.height())
        parts = os.environ["CREATIVE_TEST_RENAME"].split(",")
        x, y, name = int(parts[0]), int(parts[1]), parts[2]
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(x, y))
        QTest.qWait(300)
        QTest.keyClick(win, Qt.Key.Key_F2)
        QTest.qWait(300)
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        for ch in name:                      # QTest.keyClicks gibt es nur für Widgets
            key = Qt.Key.Key_Space if ch == " " else Qt.Key(ord(ch.upper()))
            for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                QtGui.QGuiApplication.sendEvent(win, QKeyEvent(kind, key, Qt.KeyboardModifier.NoModifier, ch))
        if len(parts) > 3:
            QTest.qWait(200)
            QTest.keyClick(win, Qt.Key.Key_Return)
        print(f"Umbenennen getestet: {name}", file=sys.stderr)

    def shoot():
        if os.environ.get("CREATIVE_TEST_RENAME") and not state.get("renamed"):
            state["renamed"] = True
            try:
                rename_test()
            except Exception as error:  # noqa: BLE001
                print(f"Umbenennen nicht möglich: {error}", file=sys.stderr)
            QTimer.singleShot(1200, shoot)
            return
        if os.environ.get("CREATIVE_TEST_DRAG") and not state.get("dragged"):
            state["dragged"] = True
            try:
                drag_test()
            except Exception as error:  # noqa: BLE001
                print(f"Ziehen nicht möglich: {error}", file=sys.stderr)
            QTimer.singleShot(1200, shoot)
            return
        if os.environ.get("CREATIVE_SCREENSHOT_SCROLL") and not state.get("scrolled"):
            state["scrolled"] = True
            try:
                scroll_down()
            except Exception as error:  # noqa: BLE001
                print(f"Rollen nicht möglich: {error}", file=sys.stderr)
            QTimer.singleShot(600, shoot)
            return
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
