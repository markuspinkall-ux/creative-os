"""Startpunkt: `python3 -m creative_shell [--dev]`.

Pro Monitor entsteht eine eigene Taskleiste. Startmenü und Schnellzugriff
werden pro Monitor bei Bedarf erzeugt und öffnen sich auf dem Monitor, auf
dem geklickt wurde. Werden Monitore an- oder abgesteckt, passt sich alles an.
"""

import argparse
import os
import signal
import sys
import time
from pathlib import Path

from PySide6.QtCore import Property, QFileSystemWatcher, QMetaObject, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtQuickControls2 import QQuickStyle

from . import config
from .apps import AppModel
from .brightness import BrightnessModel
from .dbus_service import ShellBus
from .kwin import KWinBridge
from .desktop import DesktopModel
from .tasks import TaskModel
from .icons import IconProvider
from .network import NetworkModel
from .printers import PrinterModel
from .assistant_client import AssistantClient
from .session import SessionModel
from .sni import TrayItems
from .trash import TrashModel
from .desktopstats import DesktopStats
from .visualizer import Visualizer
from .nowplaying import NowPlaying
from .broadcasttray import BroadcastTray
from .shelf import ShelfModel

QML_DIR = Path(__file__).resolve().parent / "qml"
BAR_HEIGHT = 74       # 60 px Leiste + 14 px Abstand zum Bildschirmrand
POPUP_GAP = 10        # Abstand zwischen Leiste und Menü
START_WIDTH = 24 + 380
PANEL_WIDTH = 360 + 24
TRASH_WIDTH = 270 + 8
ASSIST_WIDTH = 320 + 8
BUBBLE_WIDTH = 380 + 8
POPUPS = ("start", "panel", "trash", "assistant", "appmenu", "chat")
SURFACES = POPUPS + ("bubble",)


# Kleine Helfer: Die in QML erzeugten Fenster werden über das Qt-Metasystem
# angesprochen. Das funktioniert auch dann, wenn PySide das Objekt nur als
# allgemeines QObject kennt.
def _win_show(win):
    QMetaObject.invokeMethod(win, "show")


def _win_hide(win):
    QMetaObject.invokeMethod(win, "hide")


def _win_visible(win):
    return bool(win.property("visible"))


def _win_activate(win):
    QMetaObject.invokeMethod(win, "requestActivate")


def _win_set_screen(win, screen):
    if hasattr(win, "setScreen"):
        win.setScreen(screen)
    else:
        win.setProperty("screen", screen)
    # Layer-Shell: Ziel-Monitor ausdrücklich festlegen. Sonst legt KWin bei
    # mehreren Monitoren alle Leisten auf denselben (aktiven) Bildschirm.
    for child in win.children():
        meta = child.metaObject()
        if meta.className() != "LayerShellQt::Window":
            continue
        if meta.indexOfProperty("wantsToBeOnActiveScreen") >= 0:
            child.setProperty("wantsToBeOnActiveScreen", False)
        if meta.indexOfProperty("screen") >= 0:          # ab Plasma 6.7
            child.setProperty("screen", screen)
        elif meta.indexOfProperty("screenConfiguration") >= 0:
            child.setProperty("screenConfiguration", 0)   # ScreenFromQWindow


def _win_move(win, x, y):
    win.setProperty("x", x)
    win.setProperty("y", y)


def layer_shell_available(engine):
    comp = QQmlComponent(engine)
    comp.setData(b"import QtQuick\nimport org.kde.layershell 1.0\nItem {}\n", QUrl())
    return comp.status() == QQmlComponent.Status.Ready


class ShellController(QObject):
    openChanged = Signal()

    def __init__(self, app, engine, use_layer_shell):
        super().__init__()
        self._app = app
        self._engine = engine
        self._layer = use_layer_shell
        self._surfaces = {}  # Monitorname -> {"screen", "bg", "bar", "start", "panel", "trash"}
        self._open = {key: "" for key in POPUPS}   # welches Menü ist auf welchem Monitor offen
        self._panel_focus = ""                      # "calendar": Schnellzugriff zeigt den Kalender
        self._tray_menu_key = ""
        self._last_screen = ""
        self._primary_name = ""      # Hauptbildschirm laut KWin
        self._primary_proc = None
        self._last_auto_close = ("", 0.0)
        host = "HostLayer.qml" if use_layer_shell else "HostPlain.qml"
        self._component = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_DIR / host)))
        if self._component.isError():
            raise RuntimeError("\n".join(e.toString() for e in self._component.errors()))

    # ---- Hauptbildschirm: kommt von KWin (Systemsteuerung › Bildschirme) ---------
    # Qt kennt unter Wayland den von KWin festgelegten Hauptbildschirm nicht
    # zuverlässig – darum direkt bei kscreen-doctor nachfragen.
    def _read_primary(self):
        if self._primary_proc is not None:
            return
        from PySide6.QtCore import QProcess
        p = QProcess(self)
        self._primary_proc = p

        def done(_code, _status):
            self._primary_proc = None
            raw = bytes(p.readAllStandardOutput()).decode("utf-8", "replace")
            p.deleteLater()
            try:
                import json
                data = json.loads(raw[raw.index("{"):])
                outs = [o for o in data.get("outputs", []) if o.get("enabled", True) and o.get("connected", True)]
                outs.sort(key=lambda o: int(o.get("priority", 99) or 99))
                name = outs[0].get("name", "") if outs else ""
            except (ValueError, IndexError, AttributeError):
                return
            if name and name != self._primary_name:
                self._primary_name = name
                self.openChanged.emit()

        p.finished.connect(done)
        p.start("kscreen-doctor", ["-j"])

    @Slot()
    def refreshPrimary(self):
        self._primary_timer.start()

    def _primary(self):
        if self._primary_name and self._primary_name in self._surfaces:
            return self._primary_name
        prim = self._app.primaryScreen()
        return prim.name() if prim else ""

    def start(self):
        self._primary_timer = QTimer(self)
        self._primary_timer.setSingleShot(True)
        self._primary_timer.setInterval(700)
        self._primary_timer.timeout.connect(self._read_primary)
        self._primary_poll = QTimer(self)
        self._primary_poll.setInterval(5000)
        self._primary_poll.timeout.connect(self._read_primary)
        self._primary_poll.start()
        self._read_primary()
        self._app.primaryScreenChanged.connect(lambda _s: self.refreshPrimary())
        self._app.screenAdded.connect(lambda _s: self.refreshPrimary())
        self._app.screenRemoved.connect(lambda _s: self.refreshPrimary())
        for screen in self._app.screens():
            self._add_screen(screen)
        self._app.screenAdded.connect(self._add_screen)
        self._app.screenRemoved.connect(self._remove_screen)

    # ---- Monitore -----------------------------------------------------------
    def _add_screen(self, screen):
        name = screen.name()
        if name in self._surfaces:
            return
        entry = {"screen": screen, "bg": None, "bar": None}
        entry.update({key: None for key in SURFACES})
        self._surfaces[name] = entry
        geo = screen.geometry()
        if self._layer:  # im Testmodus kein Hintergrund, sonst wäre der Desktop verdeckt
            entry["bg"] = self._create(screen, "background", "Wallpaper.qml", geo.width(), geo.height(), False)
            _win_show(entry["bg"])
        entry["bar"] = self._create(screen, "bar", "Taskbar.qml", geo.width(), BAR_HEIGHT, False)
        _win_show(entry["bar"])
        screen.geometryChanged.connect(lambda _g, n=name: self._relayout(n))
        screen.geometryChanged.connect(lambda _g: self.refreshPrimary())

    def _remove_screen(self, screen):
        entry = self._surfaces.pop(screen.name(), None)
        if not entry:
            return
        for key in ("bg", "bar") + SURFACES:
            win = entry.get(key)
            if win is not None:
                _win_hide(win)
                win.deleteLater()
        if screen.name() in self._open.values():
            self._open = {key: "" for key in POPUPS}
            self.openChanged.emit()

    def _relayout(self, name):
        entry = self._surfaces.get(name)
        if not entry:
            return
        for key in SURFACES:  # Menüs bei neuer Auflösung neu bauen
            win = entry.get(key)
            if win is not None:
                _win_hide(win)
                win.deleteLater()
                entry[key] = None
        geo = entry["screen"].geometry()
        bar = entry["bar"]
        bar.setProperty("surfaceWidth", geo.width())
        if entry.get("bg") is not None:
            entry["bg"].setProperty("surfaceWidth", geo.width())
            entry["bg"].setProperty("surfaceHeight", geo.height())
        if not self._layer:
            _win_move(bar, geo.x(), geo.y() + geo.height() - BAR_HEIGHT)

    def _popup_height(self, screen, wanted):
        return min(wanted, screen.geometry().height() - BAR_HEIGHT - 40) + POPUP_GAP

    def _create(self, screen, placement, content, width, height, keyboard, key=""):
        props = {
            "popupKey": key,
            "contentSource": QUrl.fromLocalFile(str(QML_DIR / "surfaces" / content)),
            "screenName": screen.name(),
            "placement": placement,
            "surfaceWidth": width,
            "surfaceHeight": height,
            "wantsKeyboard": keyboard,
        }
        win = self._component.createWithInitialProperties(props, self._engine.rootContext())
        if win is None:
            raise RuntimeError("\n".join(e.toString() for e in self._component.errors()))
        _win_set_screen(win, screen)
        if not self._layer:
            geo = screen.geometry()
            bottom = geo.y() + geo.height()
            if placement == "bar":
                _win_move(win, geo.x(), bottom - height)
            elif placement == "left":
                _win_move(win, geo.x(), bottom - BAR_HEIGHT - height)
            else:
                _win_move(win, geo.x() + geo.width() - width, bottom - BAR_HEIGHT - height)
        return win

    def _ensure(self, name, key):
        entry = self._surfaces.get(name)
        if entry is None:
            return None
        if entry[key] is None:
            screen = entry["screen"]
            if key == "start":
                entry[key] = self._create(screen, "left", "StartMenu.qml", START_WIDTH,
                                          self._popup_height(screen, 780), True, key)
            elif key == "panel":
                entry[key] = self._create(screen, "right", "QuickPanel.qml", PANEL_WIDTH,
                                          self._popup_height(screen, 940), True, key)
            elif key == "trash":
                entry[key] = self._create(screen, "right", "TrashMenu.qml", TRASH_WIDTH,
                                          200 + POPUP_GAP, True, key)
            elif key == "assistant":
                entry[key] = self._create(screen, "right", "AssistantMenu.qml", ASSIST_WIDTH,
                                          self._popup_height(screen, 620), True, key)
            elif key == "appmenu":
                entry[key] = self._create(screen, "right", "TrayAppMenu.qml", TRASH_WIDTH,
                                          self._popup_height(screen, 460), True, key)
            elif key == "chat":
                entry[key] = self._create(screen, "right", "AssistantChat.qml", BUBBLE_WIDTH,
                                          self._popup_height(screen, 560), True, key)
            elif key == "bubble":
                entry[key] = self._create(screen, "right", "AssistantBubble.qml", BUBBLE_WIDTH,
                                          170 + POPUP_GAP, False, key)
        return entry[key]

    # ---- Für QML --------------------------------------------------------------
    def _toggle(self, name, key):
        self._last_screen = name
        current = self._open[key]
        # Klick auf den Knopf eines Menüs, das sich gerade durch den Klick selbst
        # geschlossen hat (Fokusverlust), soll es nicht sofort wieder öffnen.
        last_key, last_time = self._last_auto_close
        if last_key == f"{key}:{name}" and time.monotonic() - last_time < 0.35:
            return
        if current == name:
            self.closePopups()
            return
        self.closePopups()
        win = self._ensure(name, key)
        if win is None:
            return
        self._open[key] = name
        _win_show(win)
        _win_activate(win)
        self.openChanged.emit()

    @Slot(str)
    def toggleStartMenu(self, name):
        self._toggle(name, "start")

    def toggleStartMenuOnActiveScreen(self, output_name):
        """Windows-Taste: Startmenü auf dem Monitor mit dem aktiven Fenster."""
        if self._open["start"]:
            self.closePopups()
            return
        name = output_name if output_name in self._surfaces else next(iter(self._surfaces), "")
        if name:
            self._toggle(name, "start")

    @Slot(str)
    def toggleQuickPanel(self, name):
        self._panel_focus = ""
        self._toggle(name, "panel")

    @Slot(str)
    def toggleCalendar(self, name):
        """Klick auf Uhr/Datum: Schnellzugriff öffnen und zum Kalender springen."""
        self._panel_focus = "calendar"
        self.openChanged.emit()
        self._toggle(name, "panel")

    @Slot(str)
    def toggleTrashMenu(self, name):
        self._toggle(name, "trash")

    @Slot(str)
    def toggleAssistantMenu(self, name):
        self._toggle(name, "assistant")

    @Slot(str)
    def toggleChat(self, name):
        self._toggle(name, "chat")

    @Slot(str, str)
    def toggleTrayAppMenu(self, name, item_key):
        self._tray_menu_key = item_key
        self._toggle(name, "appmenu")

    # Sprechblase des Assistenten (nimmt keinen Fokus, verschwindet von selbst)
    def _bubble_screen(self):
        if self._last_screen in self._surfaces:
            return self._last_screen
        prim = self._primary()
        return prim if prim in self._surfaces else next(iter(self._surfaces), "")

    @Slot()
    def showBubble(self):
        name = self._bubble_screen()
        if self._open["assistant"] or self._open["chat"]:
            return                        # Menü/Chat ist offen – das zeigt den Text schon
        win = self._ensure(name, "bubble")
        if win is not None and not _win_visible(win):
            _win_show(win)

    @Slot()
    def hideBubble(self):
        for entry in self._surfaces.values():
            if entry.get("bubble") is not None and _win_visible(entry["bubble"]):
                _win_hide(entry["bubble"])

    @Slot(str)
    def noteScreen(self, name):
        self._last_screen = name

    @Slot()
    def closePopups(self):
        for entry in self._surfaces.values():
            for key in POPUPS:
                if entry[key] is not None and _win_visible(entry[key]):
                    _win_hide(entry[key])
        if any(self._open.values()):
            self._open = {key: "" for key in POPUPS}
            self.openChanged.emit()

    @Slot(str, str)
    def popupLostFocus(self, name, key):
        if key not in POPUPS:
            key = "start" if key == "left" else "panel"
        if self._open[key] == name:
            self._last_auto_close = (f"{key}:{name}", time.monotonic())
            self.closePopups()

    startMenuOpenOn = Property(str, lambda self: self._open["start"], notify=openChanged)
    quickPanelOpenOn = Property(str, lambda self: self._open["panel"], notify=openChanged)
    trashMenuOpenOn = Property(str, lambda self: self._open["trash"], notify=openChanged)
    panelFocus = Property(str, lambda self: self._panel_focus, notify=openChanged)
    assistantMenuOpenOn = Property(str, lambda self: self._open["assistant"], notify=openChanged)
    trayMenuKey = Property(str, lambda self: self._tray_menu_key, notify=openChanged)
    chatOpenOn = Property(str, lambda self: self._open["chat"], notify=openChanged)
    # Schreibtisch-Symbole erscheinen nur auf dem Hauptbildschirm
    primaryScreen = Property(str, lambda self: self._primary(), notify=openChanged)


def main():
    parser = argparse.ArgumentParser(prog="creative-shell")
    parser.add_argument("--dev", action="store_true",
                        help="ohne Layer-Shell starten (zum Testen in jedem Desktop)")
    args = parser.parse_args()

    # Eigener Look nur für dieses Programm (nicht an gestartete Apps vererben)
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("creative-shell")
    app.setDesktopFileName("creative-shell")
    app.setQuitOnLastWindowClosed(False)

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))
    engine.addImageProvider("icon", IconProvider())

    cfg = config.load()
    apps = AppModel(cfg["pinned"])
    tasks = TaskModel(apps, KWinBridge())
    models = {
        "apps": apps,
        "tasks": tasks,
        "network": NetworkModel(),
        "brightness": BrightnessModel(),
        "printers": PrinterModel(),
        "session": SessionModel(),
        "trash": TrashModel(),
        "desktop": DesktopModel(),
        "assistant": AssistantClient(),
        "trayApps": TrayItems(),
        "desktopStats": DesktopStats(),
        "visualizer": Visualizer(),
        "nowplaying": NowPlaying(),
        "broadcast": BroadcastTray(),
        "shelf": ShelfModel(apps),
    }
    use_layer = not args.dev and app.platformName() == "wayland" and layer_shell_available(engine)
    if not use_layer and not args.dev:
        print("creative-shell: Layer-Shell nicht verfügbar – starte im einfachen Fenstermodus")

    shell = ShellController(app, engine, use_layer)
    ctx = engine.rootContext()
    def wallpaper_url():
        path = os.path.expanduser(config.load().get("wallpaper") or "")
        if not path or not os.path.exists(path):
            path = str(QML_DIR / "Creative" / "wallpapers" / "graphit.svg")
        return QUrl.fromLocalFile(path)

    ctx.setContextProperty("wallpaperUrl", wallpaper_url())
    # Neues Hintergrundbild aus der Systemsteuerung sofort übernehmen
    cfg_dir = config.config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    watcher = QFileSystemWatcher([str(cfg_dir)])
    watcher.directoryChanged.connect(lambda _p: ctx.setContextProperty("wallpaperUrl", wallpaper_url()))
    ctx.setContextProperty("shell", shell)
    for name, model in models.items():
        ctx.setContextProperty(name, model)
    shell.start()
    models["assistant"].spoke.connect(shell.showBubble)

    # Fensterliste von KWin und Windows-Tastenkürzel über D-Bus
    bus = ShellBus(shell, tasks, apps, models["session"])
    bus.register()

    # Strg+C / systemd-Stopp sauber beenden
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    ticker = QTimer()
    ticker.start(300)
    ticker.timeout.connect(lambda: None)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
