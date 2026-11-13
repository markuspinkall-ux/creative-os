"""D-Bus-Dienst org.creativeos.Shell.

Hierüber meldet das KWin-Skript die offenen Fenster, und die
Windows-Tastenkürzel (Win-Taste, Win+E …) erreichen die Shell.
"""

import json

from PySide6.QtCore import ClassInfo, QObject, SLOT, Slot

from .runner import spawn_detached

try:
    from PySide6.QtDBus import QDBusConnection
except ImportError:  # sehr unwahrscheinlich, aber die Shell soll trotzdem laufen
    QDBusConnection = None

SERVICE = "org.creativeos.Shell"
PATH = "/Shell"


@ClassInfo({"D-Bus Interface": "org.creativeos.Shell"})
class ShellBus(QObject):
    def __init__(self, shell, tasks, apps, session, widgets, parent=None):
        super().__init__(parent)
        self._shell = shell
        self._tasks = tasks
        self._apps = apps
        self._session = session
        self._widgets = widgets

    def register(self):
        if QDBusConnection is None:
            print("creative-shell: QtDBus fehlt – Tastenkürzel und Fensterliste sind aus")
            return False
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            print("creative-shell: keine D-Bus-Sitzung")
            return False
        if not bus.registerService(SERVICE):
            print("creative-shell: D-Bus-Name belegt (läuft die Shell schon?)")
        # KWin darf Layer-Shell-Flächen während der Sperre ausblenden.
        # Nach erfolgreichem Entsperren die Desktop-Flächen erneut einblenden.
        bus.connect("org.freedesktop.ScreenSaver", "/ScreenSaver",
                    "org.freedesktop.ScreenSaver", "ActiveChanged",
                    self, SLOT("screenSaverChanged(bool)"))
        ok = bus.registerObject(PATH, self, QDBusConnection.RegisterOption.ExportAllSlots)
        if ok:
            self._tasks.request_snapshot()  # Fensterliste von KWin holen
        return ok

    @Slot(bool)
    def screenSaverChanged(self, active):
        if active:
            self._shell.closePopups()
            self._shell.hideBubble()
        else:
            self._shell.restoreDesktop()

    # ---- vom KWin-Skript --------------------------------------------------------
    @Slot(str)
    def update(self, payload):
        self._tasks.update_from_json(payload)
        # Für den Taskmanager: welche Prozesse haben ein Fenster („Apps“)
        try:
            import os
            from pathlib import Path
            d = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}") / "creative-shell"
            d.mkdir(mode=0o700, exist_ok=True)
            tmp = d / "windows.json.tmp"
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(d / "windows.json")
        except OSError:
            pass

    @Slot(result=str)
    def widgetState(self):
        extras = self._widgets["extras"]
        return json.dumps({
            **{name: self._widgets[name].enabled for name in ("shelf", "stats", "rss", "weather")},
            "clock": extras.clockEnabled, "clockInstalled": extras.clockInstalled,
            "twitch": extras.twitchEnabled, "channels": extras.channel_names(),
            "ki": self._widgets["ki"].enabled,
            "screens": self._shell.screenNames, "targets": self._shell.widgetScreens,
        })

    @Slot(str, bool, result=str)
    def setWidgetEnabled(self, name, enabled):
        try:
            if name in ("shelf", "stats", "rss", "weather", "ki"):
                self._widgets[name].setEnabled(enabled)
            else:
                self._widgets["extras"].setEnabled(name, enabled)
        except ValueError as exc:
            return str(exc)
        return ""

    @Slot(str, str, result=str)
    def setWidgetMonitor(self, name, monitor):
        return self._shell.setWidgetScreen(name, monitor)

    @Slot(str, result=str)
    def installClockWidget(self, payload):
        if len(payload) > 4096:
            return "Widget-Paket ist zu groß."
        try:
            self._widgets["extras"].installClock(payload)
        except ValueError as exc:
            return str(exc)
        return ""

    @Slot(str, result=str)
    def setTwitchChannels(self, text):
        if len(text) > 2048:
            return "Die Kanalliste ist zu lang."
        try:
            self._widgets["extras"].saveChannels(text)
        except ValueError as exc:
            return str(exc)
        return ""

    # ---- Tastenkürzel -------------------------------------------------------------
    @Slot()
    def refreshScreens(self):
        """Systemsteuerung hat die Bildschirme geändert (z. B. Hauptbildschirm)."""
        self._shell.refreshPrimary()

    @Slot()
    def toggleStartMenu(self):
        self._shell.toggleStartMenuOnActiveScreen(self._tasks.active_output)

    @Slot(str)
    def launchRole(self, role):
        for pin in self._apps.pinned:
            if pin.get("icon") == role:
                self._apps.launch(pin["desktopId"])
                return

    @Slot()
    def openSettings(self):
        if not spawn_detached(["creative-settings"]):
            spawn_detached(["systemsettings"])

    @Slot()
    def lock(self):
        self._session.lock()

    @Slot()
    def screenshot(self):
        if not spawn_detached(["creative-shots", "--snip"]):
            spawn_detached(["spectacle", "--region", "--background", "--copy-image"])

    @Slot()
    def taskManager(self):
        if not spawn_detached(["creative-taskmanager"]) and not spawn_detached(["plasma-systemmonitor"]):
            spawn_detached(["gnome-system-monitor"])
