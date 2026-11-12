"""Creative OS – Benachrichtigungen (org.freedesktop.Notifications).

Zeigt Meldungen von Programmen (Steam, Discord, Downloads, Updates …) unten rechts
über der Taskleiste im Creative-Look. Startpunkt: `creative-notifyd`.
"""

import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
for base in (HERE.parent.parent / "shell", Path("/usr/lib/creative-shell")):
    if (base / "creative_shell").is_dir():
        sys.path.insert(0, str(base))
        break

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

MAX_SHOWN = 4


class Center(QObject):
    """Hält die sichtbaren Meldungen und spricht mit D-Bus."""
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []          # [{id, app, icon, summary, body, actions:[{key,label}], timeout}]
        self._next = 1
        self._bus = None          # D-Bus-Objekt (für Signale)

    def notify(self, app, replaces, icon, summary, body, actions, hints, timeout):
        nid = int(replaces) if replaces else self._next
        if not replaces:
            self._next += 1
        acts = []
        for i in range(0, len(actions) - 1, 2):
            acts.append({"key": str(actions[i]), "label": str(actions[i + 1])})
        img = str(icon or "")
        if not img:
            for k in ("image-path", "image_path"):
                if k in hints:
                    img = str(hints[k])
        if img.startswith("file://"):
            img = QUrl(img).toLocalFile()
        urgency = int(hints.get("urgency", 1)) if hasattr(hints, "get") else 1
        if timeout is None or int(timeout) < 0:
            timeout = 6500 if urgency < 2 else 0          # kritisch: bleibt stehen
        item = {"id": nid, "app": str(app or ""), "icon": img, "summary": str(summary or ""),
                "body": str(body or ""), "actions": [a for a in acts if a["key"] != "default"],
                "hasDefault": any(a["key"] == "default" for a in acts), "timeout": int(timeout),
                "critical": urgency >= 2, "stamp": time.time()}
        self._items = [x for x in self._items if x["id"] != nid] + [item]
        self._items = self._items[-MAX_SHOWN:]
        self.changed.emit()
        return nid

    @Slot(int)
    def close(self, nid):
        self._remove(nid, 2)                 # vom Benutzer geschlossen

    @Slot(int)
    def expire(self, nid):
        self._remove(nid, 1)                 # abgelaufen

    def close_by_app(self, nid):
        self._remove(nid, 3)

    @Slot(int, str)
    def invoke(self, nid, key):
        if self._bus is not None:
            try:
                self._bus.ActionInvoked(nid, key)
            except Exception:
                pass
        self._remove(nid, 2)

    def _remove(self, nid, reason):
        before = len(self._items)
        self._items = [x for x in self._items if x["id"] != nid]
        if len(self._items) != before:
            self.changed.emit()
            if self._bus is not None:
                try:
                    self._bus.NotificationClosed(nid, reason)
                except Exception:
                    pass

    @Slot(str, result=bool)
    def iconOk(self, name):
        from PySide6.QtGui import QIcon
        if not name:
            return False
        if name.startswith("/"):
            return os.path.exists(name)
        return QIcon.hasThemeIcon(name)

    items = Property("QVariantList", lambda self: self._items, notify=changed)


def start_dbus(center):
    """org.freedesktop.Notifications über dbus-python (läuft in Qts GLib-Schleife mit)."""
    try:
        import dbus
        import dbus.service
        from dbus.mainloop.glib import DBusGMainLoop
    except ImportError:
        print("creative-notifyd: python3-dbus fehlt")
        return None
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    try:
        name = dbus.service.BusName("org.freedesktop.Notifications", bus, do_not_queue=True, replace_existing=True,
                                    allow_replacement=True)
    except dbus.exceptions.NameExistsException:
        print("creative-notifyd: ein anderer Benachrichtigungsdienst läuft schon")
        return None

    class Server(dbus.service.Object):
        @dbus.service.method("org.freedesktop.Notifications", in_signature="", out_signature="as")
        def GetCapabilities(self):
            return ["body", "actions", "icon-static", "persistence"]

        @dbus.service.method("org.freedesktop.Notifications", in_signature="susssasa{sv}i", out_signature="u")
        def Notify(self, app, replaces, icon, summary, body, actions, hints, timeout):
            return center.notify(app, int(replaces), icon, summary, body, list(actions),
                                 {str(k): v for k, v in hints.items()}, int(timeout))

        @dbus.service.method("org.freedesktop.Notifications", in_signature="u", out_signature="")
        def CloseNotification(self, nid):
            center.close_by_app(int(nid))

        @dbus.service.method("org.freedesktop.Notifications", in_signature="", out_signature="ssss")
        def GetServerInformation(self):
            return ("Creative OS", "Creative OS", "1.0", "1.2")

        @dbus.service.signal("org.freedesktop.Notifications", signature="uu")
        def NotificationClosed(self, nid, reason):
            pass

        @dbus.service.signal("org.freedesktop.Notifications", signature="us")
        def ActionInvoked(self, nid, key):
            pass

    server = Server(bus, "/org/freedesktop/Notifications")
    server._name = name
    center._bus = server
    return server


def main():
    QQuickStyle.setStyle("Basic")
    os.environ.setdefault("QT_QPA_PLATFORM", "wayland")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Creative Benachrichtigungen")
    app.setDesktopFileName("creative-notifyd")
    app.setQuitOnLastWindowClosed(False)
    center = Center()
    engine = QQmlApplicationEngine()
    from creative_shell.icons import IconFiles
    icon_files = IconFiles()
    engine.rootContext().setContextProperty("iconFiles", icon_files)
    for d in (HERE.parent.parent / "shell" / "creative_shell" / "qml", Path("/usr/lib/creative-shell/creative_shell/qml")):
        if (d / "Creative" / "qmldir").exists():
            engine.addImportPath(str(d))
            break
    engine.rootContext().setContextProperty("center", center)
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    if "--selftest" in sys.argv:
        center.notify("Test", 0, "dialog-information", "Selbsttest", "Benachrichtigungen funktionieren.", [], {}, 1000)
        print("Benachrichtigungen: Selbsttest bestanden")
        return 0
    keep = start_dbus(center)
    if keep is None:
        return 0
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
