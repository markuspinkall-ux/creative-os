"""D-Bus-Dienst org.creativeos.Shell.

Hierüber meldet das KWin-Skript die offenen Fenster, und die
Windows-Tastenkürzel (Win-Taste, Win+E …) erreichen die Shell.
"""

from PySide6.QtCore import ClassInfo, QObject, Slot

from .runner import spawn_detached

try:
    from PySide6.QtDBus import QDBusConnection
except ImportError:  # sehr unwahrscheinlich, aber die Shell soll trotzdem laufen
    QDBusConnection = None

SERVICE = "org.creativeos.Shell"
PATH = "/Shell"


@ClassInfo({"D-Bus Interface": "org.creativeos.Shell"})
class ShellBus(QObject):
    def __init__(self, shell, tasks, apps, session, parent=None):
        super().__init__(parent)
        self._shell = shell
        self._tasks = tasks
        self._apps = apps
        self._session = session

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
        ok = bus.registerObject(PATH, self, QDBusConnection.RegisterOption.ExportAllSlots)
        if ok:
            self._tasks.request_snapshot()  # Fensterliste von KWin holen
        return ok

    # ---- vom KWin-Skript --------------------------------------------------------
    @Slot(str)
    def update(self, payload):
        self._tasks.update_from_json(payload)

    # ---- Tastenkürzel -------------------------------------------------------------
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
        spawn_detached(["spectacle", "--region", "--background", "--copy-image"])

    @Slot()
    def taskManager(self):
        if not spawn_detached(["plasma-systemmonitor"]):
            spawn_detached(["gnome-system-monitor"])
