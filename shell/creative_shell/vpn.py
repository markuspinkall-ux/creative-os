"""Proton VPN über NetworkManager (WireGuard, ohne Proton-App).

Proton bietet für jedes Konto – auch das kostenlose – WireGuard-Konfigurationen
zum Herunterladen an (account.protonvpn.com › Downloads). Gibeon OS liest so
eine .conf-Datei selbst und legt daraus eine NetworkManager-Verbindung an:

* nur für den angemeldeten Benutzer (connection.permissions = user:NAME),
  dafür braucht NetworkManager kein Administrator-Passwort und andere Konten
  sehen weder die Verbindung noch den Schlüssel;
* startet nie von selbst (autoconnect aus);
* der private Schlüssel geht über D-Bus direkt an NetworkManager und taucht nie
  in einer Befehlszeile auf.

Verbinden, Trennen und Entfernen laufen über nmcli (ohne Geheimnisse).
"""

import ipaddress
import json
import os
import pwd
import re
import socket
import struct
import uuid as uuidlib
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, QTimer, QUrl, Signal, Slot

from . import config
from .network import split_terse
from .runner import Runner, spawn_detached

PREFIX = "Proton VPN · "
INTERFACE = "proton0"
MAX_CONF = 16 * 1024
DOWNLOADS = "https://account.protonvpn.com/downloads"
KEY = re.compile(r"[A-Za-z0-9+/]{42}[AEIMQUYcgkosw480]=")

COUNTRIES = {
    "AE": "Vereinigte Arabische Emirate", "AR": "Argentinien", "AT": "Österreich", "AU": "Australien",
    "BE": "Belgien", "BG": "Bulgarien", "BR": "Brasilien", "CA": "Kanada", "CH": "Schweiz",
    "CL": "Chile", "CO": "Kolumbien", "CY": "Zypern", "CZ": "Tschechien", "DE": "Deutschland",
    "DK": "Dänemark", "EE": "Estland", "EG": "Ägypten", "ES": "Spanien", "FI": "Finnland",
    "FR": "Frankreich", "GR": "Griechenland", "HK": "Hongkong", "HR": "Kroatien", "HU": "Ungarn",
    "ID": "Indonesien", "IE": "Irland", "IL": "Israel", "IN": "Indien", "IS": "Island",
    "IT": "Italien", "JP": "Japan", "KR": "Südkorea", "LT": "Litauen", "LU": "Luxemburg",
    "LV": "Lettland", "MX": "Mexiko", "MY": "Malaysia", "NG": "Nigeria", "NL": "Niederlande",
    "NO": "Norwegen", "NZ": "Neuseeland", "PE": "Peru", "PH": "Philippinen", "PL": "Polen",
    "PT": "Portugal", "RO": "Rumänien", "RS": "Serbien", "SE": "Schweden", "SG": "Singapur",
    "SI": "Slowenien", "SK": "Slowakei", "TH": "Thailand", "TR": "Türkei", "TW": "Taiwan",
    "UA": "Ukraine", "UK": "Vereinigtes Königreich", "GB": "Vereinigtes Königreich",
    "US": "USA", "VN": "Vietnam", "ZA": "Südafrika",
}
# DE-FREE-12, NL#3, US-NY#45, CH-DE#1 (Secure Core), wg-JP-FREE-7 …
SERVER = re.compile(r"(?<![A-Za-z])([A-Z]{2})((?:-[A-Z]{2,4})*)[-#_ ]?#?(\d{1,4})(?!\d)")


# ---------------------------------------------------------------------------
# .conf lesen
# ---------------------------------------------------------------------------
def parse_conf(text):
    """wg-quick-Datei → {"private_key", "addresses", "dns", "mtu", "peers"}; ValueError auf Deutsch."""
    if len(text) > MAX_CONF:
        raise ValueError("Die Datei ist zu groß für eine WireGuard-Konfiguration.")
    section, iface, peers = None, {}, []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip() if not raw.lstrip().startswith("#") else ""
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            if section == "peer":
                peers.append({})
            elif section != "interface":
                raise ValueError(f"Unbekannter Abschnitt [{line[1:-1]}].")
            continue
        if "=" not in line or section is None:
            raise ValueError("Das ist keine WireGuard-Konfiguration.")
        key, value = (part.strip() for part in line.split("=", 1))
        key = key.lower()
        target = iface if section == "interface" else peers[-1]
        if key in ("address", "dns", "allowedips"):
            target.setdefault(key, []).extend(v.strip() for v in value.split(",") if v.strip())
        else:
            target[key] = value
    private = iface.get("privatekey", "")
    if not KEY.fullmatch(private):
        raise ValueError("In der Datei fehlt der private Schlüssel (PrivateKey).")
    for unsupported in ("preup", "postup", "predown", "postdown", "table", "saveconfig"):
        if unsupported in iface:
            raise ValueError("Die Datei enthält Befehle (PostUp …) – so etwas wird aus Sicherheitsgründen nicht übernommen.")
    addresses = []
    for value in iface.get("address", []):
        try:
            net = ipaddress.ip_interface(value if "/" in value else value + ("/128" if ":" in value else "/32"))
        except ValueError:
            raise ValueError(f"Ungültige Adresse: {value}") from None
        addresses.append((str(net.ip), net.network.prefixlen, net.version))
    if not any(a[2] == 4 for a in addresses):
        raise ValueError("In der Datei fehlt die IPv4-Adresse (Address).")
    dns = []
    for value in iface.get("dns", []):
        try:
            dns.append(ipaddress.ip_address(value))
        except ValueError:
            pass  # Suchdomänen braucht Proton nicht
    mtu = 0
    if "mtu" in iface:
        try:
            mtu = int(iface["mtu"])
        except ValueError:
            raise ValueError("Ungültige MTU.") from None
        if not 576 <= mtu <= 9000:
            raise ValueError("Ungültige MTU.")
    if not peers:
        raise ValueError("In der Datei fehlt der Server ([Peer]).")
    result_peers = []
    for peer in peers:
        public = peer.get("publickey", "")
        if not KEY.fullmatch(public):
            raise ValueError("Der öffentliche Schlüssel des Servers (PublicKey) fehlt oder ist ungültig.")
        endpoint = peer.get("endpoint", "")
        host, _, port = endpoint.rpartition(":")
        if not host or not port.isdigit() or not 0 < int(port) < 65536:
            raise ValueError("Die Server-Adresse (Endpoint) fehlt oder ist ungültig.")
        allowed = []
        for value in peer.get("allowedips", []):
            try:
                allowed.append(str(ipaddress.ip_network(value, strict=False)))
            except ValueError:
                raise ValueError(f"Ungültiger Eintrag bei AllowedIPs: {value}") from None
        if not allowed:
            raise ValueError("In der Datei fehlt AllowedIPs.")
        item = {"public_key": public, "endpoint": endpoint, "allowed_ips": allowed}
        if "presharedkey" in peer:
            if not KEY.fullmatch(peer["presharedkey"]):
                raise ValueError("Ungültiger PresharedKey.")
            item["preshared_key"] = peer["presharedkey"]
        if "persistentkeepalive" in peer:
            try:
                item["keepalive"] = max(0, min(65535, int(peer["persistentkeepalive"])))
            except ValueError:
                raise ValueError("Ungültiges PersistentKeepalive.") from None
        result_peers.append(item)
    return {"private_key": private, "addresses": addresses, "dns": dns, "mtu": mtu, "peers": result_peers}


def server_label(filename, text=""):
    """Land und Servername aus Dateiname oder Kommentar: ("NL", "Niederlande", "NL-FREE#12")."""
    candidates = [Path(filename).stem.upper()]
    candidates += [line.lstrip("# ").upper() for line in text.splitlines() if line.lstrip().startswith("#")]
    for candidate in candidates:
        candidate = candidate.replace("WG-", "")
        # jede Stelle prüfen (überlappend): in „CREATIVE-OS-NL-FREE-3“ ist „OS“ kein Land, „NL“ schon
        for match in (SERVER.match(candidate, i) for i in range(len(candidate))):
            code = match and match.group(1)
            if code in COUNTRIES:
                return code, COUNTRIES[code], f"{code}{match.group(2)}#{int(match.group(3))}"
    return "", "", Path(filename).stem[:40]


def connection_name(filename, text):
    code, country, server = server_label(filename, text)
    return PREFIX + (f"{country} ({server})" if country else server or "Server")


def split_name(name):
    """„Proton VPN · Niederlande (NL-FREE#12)“ → ("Niederlande", "NL-FREE#12")."""
    rest = name[len(PREFIX):] if name.startswith(PREFIX) else name
    match = re.fullmatch(r"(.*) \(([^()]*)\)", rest)
    return (match.group(1), match.group(2)) if match else (rest, "")


def nm_settings(parsed, name, user, uid=None):
    """Die Verbindung als einfache Python-Werte (für Tests); D-Bus-Typen macht to_dbus()."""
    v4 = [a for a in parsed["addresses"] if a[2] == 4]
    v6 = [a for a in parsed["addresses"] if a[2] == 6]
    dns4 = [str(d) for d in parsed["dns"] if d.version == 4]
    dns6 = [str(d) for d in parsed["dns"] if d.version == 6]
    wireguard = {"private-key": parsed["private_key"], "peers": []}
    if parsed["mtu"]:
        wireguard["mtu"] = parsed["mtu"]
    for peer in parsed["peers"]:
        item = {"public-key": peer["public_key"], "endpoint": peer["endpoint"], "allowed-ips": peer["allowed_ips"]}
        if "preshared_key" in peer:
            item["preshared-key"] = peer["preshared_key"]
            item["preshared-key-flags"] = 0
        if peer.get("keepalive"):
            item["persistent-keepalive"] = peer["keepalive"]
        wireguard["peers"].append(item)
    ipv4 = {"method": "manual", "address-data": [{"address": a, "prefix": p} for a, p, _ in v4]}
    ipv6 = {"method": "manual", "address-data": [{"address": a, "prefix": p} for a, p, _ in v6]} if v6 \
        else {"method": "disabled"}
    if dns4:
        # alle Anfragen über den Tunnel (kein DNS-Leck)
        ipv4.update({"dns": dns4, "dns-search": ["~."], "dns-priority": -50})
    if dns6 and v6:
        ipv6.update({"dns": dns6, "dns-search": ["~."], "dns-priority": -50})
    return {
        "connection": {
            "id": name, "uuid": uid or str(uuidlib.uuid4()), "type": "wireguard",
            "interface-name": INTERFACE, "autoconnect": False, "permissions": [f"user:{user}:"],
        },
        "wireguard": wireguard,
        "ipv4": ipv4,
        "ipv6": ipv6,
    }


def to_dbus(settings):
    import dbus

    def ip4(text):
        return dbus.UInt32(struct.unpack("=I", socket.inet_aton(text))[0])

    def ip6(text):
        return dbus.ByteArray(socket.inet_pton(socket.AF_INET6, text))

    def addresses(rows):
        return dbus.Array([dbus.Dictionary({"address": r["address"], "prefix": dbus.UInt32(r["prefix"])},
                                           signature="sv") for r in rows], signature="a{sv}")

    con = settings["connection"]
    wg = settings["wireguard"]
    peers = []
    for peer in wg["peers"]:
        item = {"public-key": peer["public-key"], "endpoint": peer["endpoint"],
                "allowed-ips": dbus.Array(peer["allowed-ips"], signature="s")}
        if "preshared-key" in peer:
            item["preshared-key"] = peer["preshared-key"]
            item["preshared-key-flags"] = dbus.UInt32(0)
        if "persistent-keepalive" in peer:
            item["persistent-keepalive"] = dbus.UInt32(peer["persistent-keepalive"])
        peers.append(dbus.Dictionary(item, signature="sv"))
    out = {
        "connection": {
            "id": con["id"], "uuid": con["uuid"], "type": con["type"], "interface-name": con["interface-name"],
            "autoconnect": dbus.Boolean(False), "permissions": dbus.Array(con["permissions"], signature="s"),
        },
        "wireguard": {"private-key": wg["private-key"], "peers": dbus.Array(peers, signature="a{sv}")},
    }
    if "mtu" in wg:
        out["wireguard"]["mtu"] = dbus.UInt32(wg["mtu"])
    for family, conv in (("ipv4", ip4), ("ipv6", ip6)):
        src = settings[family]
        item = {"method": src["method"]}
        if "address-data" in src:
            item["address-data"] = addresses(src["address-data"])
        if "dns" in src:
            item["dns"] = dbus.Array([conv(d) for d in src["dns"]], signature="u" if family == "ipv4" else "ay")
            item["dns-search"] = dbus.Array(src["dns-search"], signature="s")
            item["dns-priority"] = dbus.Int32(src["dns-priority"])
        out[family] = item
    return dbus.Dictionary({k: dbus.Dictionary(v, signature="sv") for k, v in out.items()}, signature="sa{sv}")


def add_connection(settings):
    """Über D-Bus anlegen (Schlüssel nie in einer Befehlszeile). Gibt die UUID zurück."""
    try:
        import dbus
    except ImportError:
        raise ValueError("python3-dbus fehlt – die VPN-Verbindung kann nicht angelegt werden.") from None
    try:
        bus = dbus.SystemBus()
        nm = bus.get_object("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager/Settings")
        dbus.Interface(nm, "org.freedesktop.NetworkManager.Settings").AddConnection(to_dbus(settings))
    except dbus.DBusException as exc:
        text = exc.get_dbus_message() or str(exc)
        if "ermission" in text or "uthoriz" in text:
            raise ValueError("NetworkManager erlaubt das Anlegen der VPN-Verbindung nicht.") from None
        raise ValueError("NetworkManager hat die Konfiguration abgelehnt: " + text[:160]) from None
    return settings["connection"]["uuid"]


def state_path():
    return config.config_dir() / "vpn.json"


def read_last():
    try:
        data = json.loads(state_path().read_text(encoding="utf-8"))
        return data.get("last", "") if isinstance(data, dict) else ""
    except (OSError, ValueError):
        return ""


def write_last(uid):
    path = state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"last": uid}, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def parse_list(out):
    """`nmcli -t -f NAME,UUID,TYPE,ACTIVE connection show` → Proton-Verbindungen."""
    rows = []
    for line in out.splitlines():
        parts = split_terse(line)
        if len(parts) >= 4 and parts[2] == "wireguard" and parts[0].startswith(PREFIX):
            country, server = split_name(parts[0])
            rows.append({"uuid": parts[1], "name": parts[0], "country": country, "server": server,
                         "active": parts[3] == "yes"})
    rows.sort(key=lambda r: (r["country"], r["server"]))
    return rows


class VpnModel(QObject):
    changed = Signal()

    def __init__(self, parent=None, watch=True):
        super().__init__(parent)
        self._run = Runner(self, force_c_locale=True)
        self._available = True
        self._servers = []
        self._busy = False
        self._message = ""
        self._last = read_last()
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(500)
        self._debounce.timeout.connect(self.refresh)
        if watch:
            self._monitor = QProcess(self)
            self._monitor.readyReadStandardOutput.connect(self._on_monitor)
            self._monitor.start("nmcli", ["monitor"])
            self._poll = QTimer(self)
            self._poll.setInterval(60000)
            self._poll.timeout.connect(self.refresh)
            self._poll.start()
        self.refresh()

    def _on_monitor(self):
        self._monitor.readAllStandardOutput()
        self._debounce.start()

    def _set(self, busy=None, message=None):
        if busy is not None:
            self._busy = busy
        if message is not None:
            self._message = message
        self.changed.emit()

    @Slot()
    def refresh(self):
        self._run.run(["nmcli", "-t", "-f", "NAME,UUID,TYPE,ACTIVE", "connection", "show"], self._on_list)

    def _on_list(self, code, out, _err):
        self._available = code != 127
        self._servers = parse_list(out) if code == 0 else []
        self.changed.emit()

    # ---- Aktionen -----------------------------------------------------------
    @Slot(str)
    def importFile(self, url):
        path = QUrl(url).toLocalFile() if url.startswith("file:") else url
        try:
            if os.path.getsize(path) > MAX_CONF:
                raise ValueError("Die Datei ist zu groß für eine WireGuard-Konfiguration.")
            text = Path(path).read_text(encoding="utf-8")
            parsed = parse_conf(text)
            name = connection_name(path, text)
            existing = {s["name"] for s in self._servers}
            base, n = name, 2
            while name in existing:
                name, n = f"{base} {n}", n + 1
            uid = add_connection(nm_settings(parsed, name, pwd.getpwuid(os.getuid()).pw_name))
        except UnicodeDecodeError:
            self._set(message="Das ist keine WireGuard-Konfiguration.")
            return
        except OSError:
            self._set(message="Die Datei konnte nicht gelesen werden.")
            return
        except ValueError as exc:
            self._set(message=str(exc))
            return
        if not self._last:
            self._remember(uid)
        self._set(message=f"„{split_name(name)[0]}“ wurde hinzugefügt. Du kannst die Datei jetzt löschen.")
        self.refresh()

    def _remember(self, uid):
        self._last = uid
        write_last(uid)

    @Slot(str)
    def connectTo(self, uid):
        server = next((s for s in self._servers if s["uuid"] == uid), None)
        if server is None:
            return
        self._remember(uid)
        self._set(busy=True, message=f"Verbinde mit {server['country']} …")

        def done(code, _out, err):
            if code == 0:
                self._set(busy=False, message="")
            elif "ecrets" in err:
                self._set(busy=False, message="Der Schlüssel fehlt – bitte die Konfiguration neu hinzufügen.")
            else:
                self._set(busy=False, message="Verbindung fehlgeschlagen. Ist das Internet verbunden?")
            self._debounce.start()

        def up(*_):
            self._run.run(["nmcli", "connection", "up", "uuid", uid], done, timeout_ms=45000)

        # erst eine andere Proton-Verbindung trennen (gleiche Schnittstelle), danach verbinden
        others = [o["uuid"] for o in self._servers if o["active"] and o["uuid"] != uid]
        if others:
            self._run.run(["nmcli", "connection", "down", "uuid", *others], up)
        else:
            up()

    @Slot()
    def disconnect(self):
        active = [s for s in self._servers if s["active"]]
        if not active:
            return
        self._set(busy=True, message="")
        for i, server in enumerate(active):
            last = i == len(active) - 1
            self._run.run(["nmcli", "connection", "down", "uuid", server["uuid"]],
                          (lambda *_: (self._set(busy=False), self._debounce.start())) if last else None)

    @Slot(bool)
    def setEnabled(self, on):
        if not on:
            self.disconnect()
            return
        uid = self._last if any(s["uuid"] == self._last for s in self._servers) else (
            self._servers[0]["uuid"] if self._servers else "")
        if uid:
            self.connectTo(uid)

    @Slot(str)
    def remove(self, uid):
        server = next((s for s in self._servers if s["uuid"] == uid), None)
        if server is None:
            return

        def done(code, _out, _err):
            self._set(message="" if code == 0 else "Die Verbindung konnte nicht entfernt werden.")
            if uid == self._last:
                self._remember("")
            self.refresh()

        self._run.run(["nmcli", "connection", "delete", "uuid", uid], done)

    @Slot()
    def openProton(self):
        if not spawn_detached(["creative-browser", DOWNLOADS]):
            spawn_detached(["xdg-open", DOWNLOADS])

    @Slot()
    def openSettings(self):
        spawn_detached(["creative-settings", "--page", "vpn"])

    @Slot()
    def clearMessage(self):
        self._set(message="")

    def _active(self):
        return next((s for s in self._servers if s["active"]), None)

    available = Property(bool, lambda self: self._available, notify=changed)
    servers = Property("QVariantList", lambda self: self._servers, notify=changed)
    connected = Property(bool, lambda self: self._active() is not None, notify=changed)
    activeCountry = Property(str, lambda self: (self._active() or {}).get("country", ""), notify=changed)
    lastUuid = Property(str, lambda self: self._last, notify=changed)
    lastCountry = Property(str, lambda self: next(
        (s["country"] for s in self._servers if s["uuid"] == self._last),
        self._servers[0]["country"] if self._servers else ""), notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    message = Property(str, lambda self: self._message, notify=changed)
