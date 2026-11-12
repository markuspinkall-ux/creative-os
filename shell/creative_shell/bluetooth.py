"""Bluetooth tray controls. Commands run off the UI thread through BlueZ."""
import os
import re
import shutil
import subprocess
import threading

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

MAC = re.compile(r"^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}$")


def run_ctl(*args):
    result = subprocess.run(["bluetoothctl", *args], capture_output=True, text=True,
                            timeout=20, env={**os.environ, "LC_ALL": "C"})
    out = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", result.stdout + result.stderr)
    if result.returncode or re.search(r"(?im)^.*(?:Failed to|org\.bluez\.Error|not available|No default controller)", out):
        raise RuntimeError(out.strip()[-400:] or "Bluetooth-Befehl fehlgeschlagen.")
    return out


def set_power(enabled):
    """Einschalten braucht beim ersten Mal oft einen Moment (Adapter wacht auf,
    BlueZ meldet dann „off-enabling“ / org.bluez.Error.Failed). Darum: Funksperre
    lösen, bis zu dreimal versuchen und am Ende nur den tatsächlichen Zustand zählen."""
    want = "yes" if enabled else "no"
    if enabled and shutil.which("rfkill"):
        subprocess.run(["rfkill", "unblock", "bluetooth"], capture_output=True, timeout=5)
    last = None
    for attempt in range(3):
        try:
            run_ctl("power", "on" if enabled else "off")
            return
        except RuntimeError as exc:
            last = exc
        # vielleicht hat es trotz Meldung geklappt (oder klappt gleich)
        for _ in range(4):
            threading.Event().wait(0.5)
            try:
                if f"Powered: {want}" in run_ctl("show"):
                    return
            except RuntimeError:
                pass
    raise RuntimeError(("Bluetooth ließ sich nicht einschalten." if enabled else
                        "Bluetooth ließ sich nicht ausschalten.") + " Bitte gleich noch einmal versuchen.") from last


def friendly(error):
    """Keine rohen bluetoothctl-Ausgaben anzeigen."""
    if not error:
        return ""
    if re.search(r"No default controller|not available", error):
        return "Kein Bluetooth-Adapter gefunden."
    if re.search(r"\[CHG\]|\[NEW\]|\[DEL\]|org\.bluez|Failed to|Controller [0-9A-F:]{17}", error):
        return "Bluetooth hat gerade nicht reagiert. Bitte noch einmal versuchen."
    return error


def read_state():
    info = run_ctl("show")
    available = bool(re.search(r"(?m)^Controller ", info))
    powered = "Powered: yes" in info
    devices = []
    if powered:
        for address, name in re.findall(r"(?m)^Device ([0-9A-Fa-f:]{17}) (.+)$", run_ctl("devices")):
            if not MAC.fullmatch(address):
                continue
            try:
                details = run_ctl("info", address)
            except RuntimeError:
                continue  # device disappeared during refresh
            devices.append({"address": address, "name": name,
                            "paired": "Paired: yes" in details,
                            "connected": "Connected: yes" in details})
    devices.sort(key=lambda d: (not d["connected"], not d["paired"], d["name"].lower()))
    return available, powered, devices


class BluetoothModel(QObject):
    changed = Signal()
    _result = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._available = self._powered = self._busy = False
        self._devices = []
        self._error = ""
        self._result.connect(self._done)
        self._timer = QTimer(self)
        self._timer.setInterval(15000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def _start(self, action=None):
        if self._busy:
            return
        self._busy, self._error = True, ""
        self.changed.emit()

        def worker():
            try:
                if action:
                    action()
                self._result.emit({"state": read_state()})
            except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
                self._result.emit({"error": str(exc)})
        threading.Thread(target=worker, daemon=True).start()

    @Slot(object)
    def _done(self, result):
        self._busy = False
        self._error = result.get("error", "")
        if "state" in result:
            self._available, self._powered, self._devices = result["state"]
        elif "No default controller" in self._error or "not available" in self._error:
            self._available = self._powered = False
            self._devices = []
        self.changed.emit()

    @Slot()
    def refresh(self):
        self._start()

    @Slot(bool)
    def setPowered(self, enabled):
        self._start(lambda: set_power(enabled))

    @Slot()
    def scan(self):
        if self._powered:
            self._start(lambda: run_ctl("--timeout", "8", "scan", "on"))

    @Slot(str, bool)
    def setConnected(self, address, connected):
        if MAC.fullmatch(address) and any(d["address"] == address and d["paired"] for d in self._devices):
            self._start(lambda: run_ctl("connect" if connected else "disconnect", address))

    @Slot()
    def pair(self):
        # KDE handles PIN/passkey confirmation and agent registration securely.
        program = shutil.which("bluedevil-wizard")
        if not program:
            self._error = "Die Bluetooth-Kopplung ist nicht installiert."
            self.changed.emit()
            return
        try:
            subprocess.Popen([program], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            self._error = str(exc)
            self.changed.emit()

    available = Property(bool, lambda s: s._available, notify=changed)
    powered = Property(bool, lambda s: s._powered, notify=changed)
    busy = Property(bool, lambda s: s._busy, notify=changed)
    devices = Property("QVariantList", lambda s: s._devices, notify=changed)
    error = Property(str, lambda s: friendly(s._error), notify=changed)
