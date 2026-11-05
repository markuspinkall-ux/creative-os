"""Mein Server: Webseite auf einer eigenen Festplatte – ein Schalter, fertig.

Die Systemänderungen macht /usr/libexec/creative-server-helper (über pkexec,
dabei wird das Passwort abgefragt). Hier wird nur angezeigt und angestoßen.
"""

import json
import shutil
import socket
import subprocess
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from creative_shell.runner import Runner, spawn_detached

HELPER = "/usr/libexec/creative-server-helper"
STATE = Path("/var/lib/creative-server/state.json")
HIDDEN = {"/boot", "/boot/efi", "/efi"}
SKIP_FS = {"swap", "LVM2_member", "crypto_LUKS", "linux_raid_member", "squashfs", ""}


def fmt_size(b):
    if not b:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024 or unit == "TB":
            text = f"{b:.0f}" if unit in ("B", "KB", "MB") or b >= 100 else f"{b:.1f}".replace(".", ",")
            return f"{text} {unit}"
        b /= 1024
    return "?"


def list_disks(selected):
    try:
        out = subprocess.run(["lsblk", "-J", "--tree=PATH", "-b", "-p", "-o", "PATH,LABEL,SIZE,FSTYPE,MOUNTPOINTS,RM,HOTPLUG,TYPE,FSUSED,MODEL,ROTA,TRAN"],
                             capture_output=True, text=True, timeout=5).stdout
        data = json.loads(out)
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    disks = []

    def kind(tran, rota, path):
        if (tran or "").lower() == "nvme" or "nvme" in path:
            return "M2"
        if rota in (False, 0, "0"):
            return "SSD"
        if rota in (True, 1, "1"):
            return "Festplatte"
        return "Laufwerk"

    def walk(nodes, model="", removable=False, tran="", rota=None):
        for n in nodes or []:
            model_here = n.get("model") or model
            if n.get("type") == "disk":
                tran, rota = n.get("tran") or "", n.get("rota")
            rem = removable or bool(n.get("rm")) or bool(n.get("hotplug"))
            mps = [m for m in (n.get("mountpoints") or []) if m]
            fs = n.get("fstype") or ""
            if n.get("type") in ("part", "crypt", "lvm") and fs not in SKIP_FS and not any(m in HIDDEN for m in mps):
                system = any(m in ("/", "/sysroot", "/var", "/home", "/var/home") for m in mps)
                size = int(n.get("size") or 0)
                used = int(n.get("fsused") or 0)
                name = "Creative OS" if system else kind(tran, n.get("rota", rota), n["path"])
                disks.append({
                    "device": n["path"], "name": f"{name} · {fmt_size(size)}", "system": system,
                    "removable": rem, "used": used / size if size and used else 0,
                    "info": ("Hier läuft Creative OS – der Server bekommt einen eigenen, geschützten Ordner" if system else
                             (f"Enthält {fmt_size(used)} Daten – sie bleiben unangetastet" if used else "Leer oder noch nicht eingebunden")),
                    "selected": n["path"] == selected or (system and selected == "system"),
                })
            walk(n.get("children"), model_here, rem, tran, rota)

    walk(data.get("blockdevices"))
    disks = [d for d in disks if not d["removable"]]     # USB-Sticks eignen sich nicht als Server
    disks.sort(key=lambda d: (not d["system"], d["name"].casefold()))
    return disks


def addresses():
    host = socket.gethostname()
    urls = [f"http://{host}.local"]
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=3).stdout.split()
        urls += [f"http://{ip}" for ip in out if ":" not in ip][:2]
    except (OSError, subprocess.SubprocessError):
        pass
    return urls


class ServerModel(QObject):
    changed = Signal()
    messageChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = Runner(self, force_c_locale=True)
        self._state = {}
        self._active = False
        self._busy = False
        self._message = ""
        self._choice = ""
        self._disks = []
        self._installed = Path(HELPER).exists() and shutil.which("caddy") is not None
        self._timer = QTimer(self)
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    @Slot()
    def refresh(self):
        try:
            self._state = json.loads(STATE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._state = {}
        target = self._state.get("target", "")
        if not self._choice:
            self._choice = target
        self._disks = list_disks(self._choice)
        self._run.run(["systemctl", "is-active", "creative-server.service"], self._on_active)

    def _on_active(self, _code, out, _err):
        self._active = out.strip() == "active"
        self.changed.emit()

    @Slot(str)
    def choose(self, device):
        if self._active:
            self._set_message("Zum Wechseln der Festplatte den Server zuerst ausschalten.")
            return
        self._choice = device
        self._disks = list_disks(device)
        self.changed.emit()

    @Slot(bool)
    def setEnabled(self, on):
        if self._busy:
            return
        if not self._installed:
            self._set_message("„Mein Server“ ist auf diesem System nicht installiert.")
            return
        if on:
            target = self._choice
            if not target:
                self._set_message("Bitte zuerst unten eine Festplatte für den Server auswählen.")
                return
            disk = next((d for d in self._disks if d["device"] == target), None)
            arg = "system" if (target == "system" or (disk and disk["system"])) else target
            args = ["pkexec", HELPER, "enable", arg]
            self._set_message("Server wird eingerichtet …")
        else:
            args = ["pkexec", HELPER, "disable"]
            self._set_message("Server wird ausgeschaltet …")
        self._busy = True
        self.changed.emit()

        def done(code, out, err):
            self._busy = False
            try:
                result = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
            except ValueError:
                result = {}
            if code == 126 or code == 127:
                self._set_message("Abgebrochen – ohne Passwort bleibt alles, wie es ist.")
            elif result.get("ok"):
                self._set_message("Der Server läuft. Lege deine Webseite in den Ordner „Webseite“." if on
                                  else "Der Server ist aus. Deine Dateien bleiben erhalten.")
            else:
                self._set_message(result.get("error") or "Das hat nicht geklappt.")
            QTimer.singleShot(600, self.refresh)

        self._run.run(args, done, timeout_ms=0)

    @Slot(str, str)
    def enableInternet(self, name, token):
        if self._busy:
            return
        name, token = name.strip(), token.strip()
        if not name or not token:
            self._set_message("Bitte DuckDNS-Name und Token eingeben.")
            return
        self._busy = True
        self._set_message("Internet-Zugang wird eingerichtet – das Zertifikat kann eine Minute dauern …")
        self.changed.emit()

        def done(code, out, _err):
            self._busy = False
            try:
                result = json.loads(out.strip().splitlines()[-1]) if out.strip() else {}
            except ValueError:
                result = {}
            if code in (126, 127):
                self._set_message("Abgebrochen – es bleibt beim Heimnetz.")
            elif result.get("ok"):
                self._set_message(f"Fertig! Deine Webseite ist unter https://{result.get('domain')} erreichbar "
                                  "(sobald die Ports im Router freigegeben sind).")
            else:
                self._set_message(result.get("error") or "Das hat nicht geklappt.")
            QTimer.singleShot(600, self.refresh)

        self._run.run(["pkexec", HELPER, "internet", name], done, stdin=token + "\n", timeout_ms=0)

    @Slot()
    def disableInternet(self):
        if self._busy:
            return
        self._busy = True
        self.changed.emit()

        def done(code, _out, _err):
            self._busy = False
            self._set_message("Der Server ist jetzt nur noch im Heimnetz erreichbar." if code == 0 else
                              "Abgebrochen.")
            QTimer.singleShot(600, self.refresh)

        self._run.run(["pkexec", HELPER, "internet-off"], done, timeout_ms=0)

    @Slot()
    def openDuckDns(self):
        QDesktopServices.openUrl(QUrl("https://www.duckdns.org/"))

    @Slot()
    def openDatabase(self):
        command = 'read -r -p "MariaDB-Benutzer: " db_user && [[ -n "$db_user" ]] && exec mariadb --user="$db_user" --password'
        if not shutil.which("mariadb") or not spawn_detached(["konsole", "--hold", "-e", "bash", "-c", command]):
            self._set_message("Der MariaDB-Client konnte nicht geöffnet werden.")

    @Slot()
    def openWebsite(self):
        QDesktopServices.openUrl(QUrl("http://localhost"))

    @Slot()
    def openFolder(self):
        site = self._state.get("site")
        if site and not spawn_detached(["creative-files", site]):
            QDesktopServices.openUrl(QUrl.fromLocalFile(site))

    def _set_message(self, text):
        self._message = text
        self.messageChanged.emit()

    installed = Property(bool, lambda self: self._installed, notify=changed)
    active = Property(bool, lambda self: self._active, notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    disks = Property("QVariantList", lambda self: self._disks, notify=changed)
    choice = Property(str, lambda self: self._choice, notify=changed)
    site = Property(str, lambda self: self._state.get("site", ""), notify=changed)
    php = Property(bool, lambda self: bool(self._state.get("php")), notify=changed)
    urls = Property("QVariantList", lambda self: addresses(), notify=changed)
    message = Property(str, lambda self: self._message, notify=messageChanged)
    domain = Property(str, lambda self: self._state.get("domain", ""), notify=changed)
    localIp = Property(str, lambda self: next((u[7:] for u in addresses()[1:]), ""), notify=changed)
