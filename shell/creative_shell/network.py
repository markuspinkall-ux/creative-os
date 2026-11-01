"""WLAN und Kabelverbindung über NetworkManager (nmcli).

Ändert sich am Netz etwas, meldet `nmcli monitor` das sofort; die Anzeige
ist also immer aktuell, ohne ständig abzufragen.
"""

from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot

from .runner import Runner


def split_terse(line):
    """Zerlegt eine `nmcli -t`-Zeile; Doppelpunkte im Namen sind mit \\ maskiert."""
    parts, cur, esc = [], [], False
    for ch in line:
        if esc:
            cur.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


class NetworkModel(QObject):
    changed = Signal()
    messageChanged = Signal()
    busyChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = Runner(self, force_c_locale=True)
        self._available = True
        self._wifi_enabled = False
        self._wired = False
        self._connected = False
        self._ssid = ""
        self._strength = 0
        self._networks = []
        self._known = set()
        self._message = ""
        self._busy = False

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(600)
        self._debounce.timeout.connect(self.refresh)

        self._monitor = QProcess(self)
        self._monitor.readyReadStandardOutput.connect(self._on_monitor)
        self._monitor.start("nmcli", ["monitor"])

        self._poll = QTimer(self)  # Sicherheitsnetz, falls monitor ausfällt
        self._poll.setInterval(60000)
        self._poll.timeout.connect(self.refresh)
        self._poll.start()
        self.refresh()

    def _on_monitor(self):
        self._monitor.readAllStandardOutput()
        self._debounce.start()

    # ---- Abfragen -----------------------------------------------------------
    @Slot()
    def refresh(self):
        self._run.run(["nmcli", "-t", "-f", "WIFI", "general"], self._on_radio)
        self._run.run(["nmcli", "-t", "-f", "TYPE,STATE", "device"], self._on_devices)
        self._run.run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"], self._on_known)
        self._run.run(
            ["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "no"],
            self._on_wifi_list,
        )

    @Slot()
    def rescan(self):
        self._run.run(["nmcli", "device", "wifi", "rescan"], lambda *_: self._debounce.start())
        self.refresh()

    def _on_radio(self, code, out, _err):
        if code == 127:
            self._available = False
        self._wifi_enabled = out.strip() == "enabled"
        self.changed.emit()

    def _on_devices(self, code, out, _err):
        wired = False
        for line in out.splitlines():
            parts = split_terse(line)
            if len(parts) >= 2 and parts[0] == "ethernet" and parts[1] == "connected":
                wired = True
        self._wired = wired
        self.changed.emit()

    def _on_known(self, code, out, _err):
        self._known = {
            p[0] for p in (split_terse(l) for l in out.splitlines()) if len(p) >= 2 and p[1] == "802-11-wireless"
        }

    def _on_wifi_list(self, code, out, _err):
        best = {}
        current = None
        for line in out.splitlines():
            parts = split_terse(line)
            if len(parts) < 4 or not parts[1]:
                continue
            in_use, ssid, signal, security = parts[0] == "*", parts[1], parts[2], parts[3]
            try:
                strength = int(signal)
            except ValueError:
                strength = 0
            item = {
                "ssid": ssid,
                "strength": strength,
                "secured": security not in ("", "--"),
                "inUse": in_use,
                "known": ssid in self._known,
            }
            if in_use:
                current = item
            if ssid not in best or best[ssid]["strength"] < strength or in_use:
                best[ssid] = item
        nets = sorted(best.values(), key=lambda n: (not n["inUse"], not n["known"], -n["strength"]))
        self._networks = nets[:8]
        self._connected = current is not None
        self._ssid = current["ssid"] if current else ""
        self._strength = current["strength"] if current else 0
        self.changed.emit()

    # ---- Aktionen -----------------------------------------------------------
    @Slot(bool)
    def setWifiEnabled(self, on):
        self._wifi_enabled = on
        self.changed.emit()
        self._run.run(["nmcli", "radio", "wifi", "on" if on else "off"], lambda *_: self._debounce.start())

    @Slot(str, str)
    def connectTo(self, ssid, password):
        self._set_busy(True)
        self._set_message(f"Verbinde mit {ssid} …")
        if ssid in self._known and not password:
            args = ["nmcli", "connection", "up", "id", ssid]
        else:
            args = ["nmcli", "device", "wifi", "connect", ssid]
            if password:
                args += ["password", password]

        def done(code, _out, err):
            self._set_busy(False)
            if code == 0:
                self._set_message("")
            elif "Secrets were required" in err or "802-11-wireless-security" in err:
                self._set_message("Das Passwort stimmt nicht.")
            else:
                self._set_message("Verbindung fehlgeschlagen.")
            self._debounce.start()

        self._run.run(args, done)

    def _set_message(self, text):
        if text != self._message:
            self._message = text
            self.messageChanged.emit()

    def _set_busy(self, value):
        if value != self._busy:
            self._busy = value
            self.busyChanged.emit()

    # ---- Eigenschaften ------------------------------------------------------
    available = Property(bool, lambda self: self._available, notify=changed)
    wifiEnabled = Property(bool, lambda self: self._wifi_enabled, notify=changed)
    wired = Property(bool, lambda self: self._wired, notify=changed)
    connected = Property(bool, lambda self: self._connected, notify=changed)
    ssid = Property(str, lambda self: self._ssid, notify=changed)
    strength = Property(int, lambda self: self._strength, notify=changed)
    networks = Property("QVariantList", lambda self: self._networks, notify=changed)
    message = Property(str, lambda self: self._message, notify=messageChanged)
    busy = Property(bool, lambda self: self._busy, notify=busyChanged)
