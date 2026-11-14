"""Schnellzugriff › „Nicht sperren“: hält und löst die Sperre bei org.freedesktop.ScreenSaver.
   dbus-run-session -- python3 tools/nicht-sperren-test.py
Ein Ersatz-Dienst (eigener Prozess) zählt die aktiven Sperren wie kscreenlocker:
Inhibit erhöht, Trennen der Verbindung des Aufrufers gibt frei."""
import subprocess
import sys
import time
from pathlib import Path

FAKE = r'''
import sys
from PySide6.QtCore import QCoreApplication, QObject, Slot, ClassInfo
from PySide6.QtDBus import QDBusConnection, QDBusServiceWatcher, QDBusMessage

app = QCoreApplication(sys.argv)
bus = QDBusConnection.sessionBus()
holders = {}
watcher = QDBusServiceWatcher()
watcher.setConnection(bus)
watcher.setWatchMode(QDBusServiceWatcher.WatchModeFlag.WatchForUnregistration)
watcher.serviceUnregistered.connect(lambda n: holders.pop(n, None))

@ClassInfo({"D-Bus Interface": "org.freedesktop.ScreenSaver"})
class Saver(QObject):
    @Slot(str, str, QDBusMessage, result=int)
    def Inhibit(self, app_name, reason, msg):
        who = msg.service()
        print("Inhibit von", who, flush=True, file=sys.stderr)
        holders[who] = reason
        watcher.addWatchedService(who)
        return 1
    @Slot(result=int)
    def Count(self):
        return len(holders)

s = Saver()
assert bus.registerService("org.freedesktop.ScreenSaver")
assert bus.registerObject("/ScreenSaver", s, QDBusConnection.RegisterOption.ExportAllSlots)
print("bereit", flush=True)
app.exec()
'''

fake = subprocess.Popen([sys.executable, "-c", FAKE], stdout=subprocess.PIPE, text=True)
assert fake.stdout.readline().strip() == "bereit", "Ersatz-Dienst startet nicht"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shell"))
from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtDBus import QDBusConnection, QDBusInterface  # noqa: E402

app = QCoreApplication(sys.argv)
from creative_shell.session import SessionModel  # noqa: E402

probe = QDBusInterface("org.freedesktop.ScreenSaver", "/ScreenSaver", "org.freedesktop.ScreenSaver",
                       QDBusConnection.sessionBus())


def count():
    for _ in range(20):
        app.processEvents()
        time.sleep(0.05)
    return probe.call("Count").arguments()[0]


m = SessionModel()
try:
    assert m.keepAwakeAvailable and not m.keepAwake
    assert count() == 0
    m.setKeepAwake(True)
    assert m.keepAwake, "Einschalten fehlgeschlagen"
    assert count() == 1, "Sperre wird nicht gehalten"
    m.setKeepAwake(True)                        # doppelt einschalten: bleibt eine Sperre
    assert count() == 1
    m.setKeepAwake(False)
    assert not m.keepAwake
    assert count() == 0, "Sperre wird beim Ausschalten nicht freigegeben"
    m.setKeepAwake(True)                        # wieder einschalten geht
    assert count() == 1
    m.setKeepAwake(False)
    assert count() == 0
    print("Nicht sperren: alles in Ordnung")
finally:
    fake.terminate()
