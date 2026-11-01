"""Prozessliste wie im Windows-Taskmanager: Apps, Hintergrundprozesse, Systemprozesse.

Apps = Programme mit einem offenen Fenster (die Shell schreibt die Fensterliste
nach $XDG_RUNTIME_DIR/creative-shell/windows.json). Alle Unterprozesse einer App
(z. B. die vielen Brave-Prozesse) werden darunter zusammengefasst.
"""

import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

import psutil

UID = os.getuid()

# Was nicht als „App“ gilt, auch wenn es ein Fenster hat bzw. Elternprozess ist
SESSION_PARENTS = {"systemd", "kwin_wayland", "kwin_wayland_wrapper", "creative-session", "creative-shell-supervisor",
                   "startplasma-wayland", "sddm", "sddm-helper", "plasma_session", "dbus-daemon", "dbus-broker",
                   "xdg-desktop-portal", "flatpak-portal", "kded6", "bwrap", "init"}
HIDE_FROM_APPS = {"creative-shell", "creative-taskmanager"}

# Freundliche Namen für bekannte Hintergrund- und Systemprozesse
FRIENDLY = {
    "creative-shell": "Creative Shell (Taskleiste)",
    "creative-assistant": "Sprachassistent",
    "creative-automount": "Laufwerke automatisch verbinden",
    "kwin_wayland": "Fensterverwaltung (KWin)",
    "kwin_wayland_wrapper": "Fensterverwaltung (KWin)",
    "pipewire": "Audio-Dienst (PipeWire)",
    "pipewire-pulse": "Audio-Dienst (PipeWire)",
    "wireplumber": "Audio-Sitzung (WirePlumber)",
    "kded6": "KDE-Hintergrunddienst",
    "Xwayland": "Kompatibilität für ältere Programme (Xwayland)",
    "polkit-kde-authentication-agent-1": "Passwortabfrage",
    "dbus-broker": "Systembus (D-Bus)",
    "dbus-daemon": "Systembus (D-Bus)",
    "NetworkManager": "Netzwerk",
    "systemd": "Systemstart (systemd)",
    "systemd-journald": "Systemprotokoll",
    "systemd-logind": "Anmeldung",
    "systemd-udevd": "Geräteerkennung",
    "systemd-resolved": "Namensauflösung (DNS)",
    "systemd-oomd": "Speicherwächter",
    "sddm": "Anmeldebildschirm",
    "cupsd": "Druckdienst",
    "udisksd": "Laufwerksdienst",
    "upowerd": "Energieverwaltung",
    "polkitd": "Berechtigungen (polkit)",
    "firewalld": "Firewall",
    "chronyd": "Uhrzeit-Abgleich",
    "rpm-ostreed": "Update-Dienst",
    "caddy": "Mein Server (Webserver)",
    "php-fpm": "Mein Server (PHP)",
    "gvfsd": "Dateisystem-Dienst",
    "xdg-desktop-portal": "Programm-Schnittstellen (Portal)",
    "xdg-desktop-portal-kde": "Programm-Schnittstellen (Portal)",
    "baloo_file": "Dateisuche",
    "steamwebhelper": "Steam",
    "mpv": "Musik (Sprachassistent)",
    "bluetoothd": "Bluetooth",
    "avahi-daemon": "Netzwerkerkennung",
    "ModemManager": "Mobilfunk",
    "abrtd": "Fehlerberichte",
    "packagekitd": "Software-Dienst",
    "gnome-software": "Software (Hintergrund)",
    "plasma-discover": "Software",
    "DiscoverNotifier": "Update-Hinweise",
    "sshd": "Fernzugriff (SSH)",
    "flatpak-session-helper": "Flatpak",
}

# Python-Programme erkennt man am Modul (python3 -m creative_files → creative-files)
PY_MODULE = re.compile(r"-m\s+(creative_\w+)")


def windows_file():
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{UID}"
    return Path(base) / "creative-shell" / "windows.json"


def read_windows():
    try:
        data = json.loads(windows_file().read_text(encoding="utf-8"))
        return [w for w in data.get("windows", []) if isinstance(w, dict)]
    except (OSError, ValueError):
        return []


_desktop_cache = {}


def desktop_info(desktop_id):
    """Name und Symbol aus der .desktop-Datei."""
    if not desktop_id:
        return None
    if desktop_id in _desktop_cache:
        return _desktop_cache[desktop_id]
    dirs = [Path("/usr/share/creative-os/data/applications"), Path.home() / ".local/share/applications",
            Path("/var/lib/flatpak/exports/share/applications"), Path.home() / ".local/share/flatpak/exports/share/applications",
            Path("/usr/local/share/applications"), Path("/usr/share/applications")]
    found = None
    for d in dirs:
        f = d / (desktop_id if desktop_id.endswith(".desktop") else desktop_id + ".desktop")
        if f.exists():
            name = icon = ""
            try:
                section = ""
                for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("["):
                        section = line
                        continue
                    if section != "[Desktop Entry]":
                        continue
                    if line.startswith("Name=") and not name:
                        name = line[5:].strip()
                    elif line.startswith("Name[de]="):
                        name = line[9:].strip()
                    elif line.startswith("Icon=") and not icon:
                        icon = line[5:].strip()
            except OSError:
                continue
            found = {"name": name, "icon": icon}
            break
    _desktop_cache[desktop_id] = found
    return found


def display_name(p):
    """Lesbarer Name eines Prozesses."""
    name = p["name"]
    cmd = p["cmdline"]
    if name.startswith("python") and cmd:
        m = PY_MODULE.search(" ".join(cmd))
        if m:
            name = m.group(1).replace("_", "-")
        elif len(cmd) > 1 and not cmd[1].startswith("-"):
            name = os.path.basename(cmd[1])
    elif name in ("sh", "bash") and len(cmd) > 1 and cmd[1].startswith("/"):
        name = os.path.basename(cmd[1])
    return FRIENDLY.get(name, name), name


class ProcessTable:
    """Hält psutil-Prozessobjekte über mehrere Abfragen, damit CPU-% stimmt."""

    def __init__(self):
        self._procs = {}
        self._io = {}
        self._t = time.monotonic()
        self.ncpu = psutil.cpu_count() or 1
        self.total_mem = psutil.virtual_memory().total

    def snapshot(self):
        now = time.monotonic()
        dt = max(0.2, now - self._t)
        self._t = now
        rows = {}
        seen = set()
        for proc in psutil.process_iter(["pid", "ppid", "name", "username", "uids", "status", "cmdline", "exe",
                                         "num_threads", "create_time"]):
            pid = proc.info["pid"]
            seen.add(pid)
            if pid in (0, 2) or proc.info["ppid"] == 2:           # Kernel-Threads weglassen
                continue
            old = self._procs.get(pid)
            if old is None or old.info.get("create_time") != proc.info.get("create_time"):
                self._procs[pid] = proc
                cpu = 0.0
                try:
                    proc.cpu_percent(None)
                except psutil.Error:
                    pass
            else:
                proc = old
                try:
                    cpu = proc.cpu_percent(None) / self.ncpu
                except psutil.Error:
                    continue
            try:
                mi = proc.memory_info()
                mem = max(0, mi.rss - getattr(mi, "shared", 0))      # ungefähr „privater Arbeitssatz“
            except psutil.Error:
                mem = 0
            disk = 0.0
            try:
                io = proc.io_counters()
                prev = self._io.get(pid)
                total = io.read_bytes + io.write_bytes
                if prev is not None:
                    disk = max(0.0, (total - prev) / dt)
                self._io[pid] = total
            except (psutil.Error, AttributeError):
                pass
            info = old.info if old is not None else proc.info
            uids = info.get("uids")
            rows[pid] = {
                "pid": pid, "ppid": info.get("ppid") or 0, "name": info.get("name") or "?",
                "user": info.get("username") or "", "uid": uids.real if uids else -1,
                "status": info.get("status") or "", "cmdline": info.get("cmdline") or [],
                "exe": info.get("exe") or "", "threads": info.get("num_threads") or 0,
                "cpu": cpu, "mem": mem, "disk": disk,
            }
        for pid in list(self._procs):
            if pid not in seen:
                self._procs.pop(pid, None)
                self._io.pop(pid, None)
        return rows

    # ---- Gruppieren ---------------------------------------------------------------------------
    def grouped(self, rows=None):
        rows = rows if rows is not None else self.snapshot()
        children = {}
        for r in rows.values():
            children.setdefault(r["ppid"], []).append(r["pid"])

        windows = read_windows()
        win_pids = {}
        for w in windows:
            pid = int(w.get("pid") or 0)
            if pid > 0 and pid in rows:
                win_pids.setdefault(pid, []).append(w)

        # App-Wurzel: höchster eigener Vorfahr, der kein Sitzungs-Prozess ist
        def root_of(pid):
            cur = pid
            while True:
                parent = rows.get(rows[cur]["ppid"])
                if not parent or parent["uid"] != UID or display_name(parent)[1] in SESSION_PARENTS:
                    return cur
                if parent["pid"] in win_pids:            # Elternteil hat selbst ein Fenster (z. B. Terminal)
                    return cur
                cur = parent["pid"]

        apps, claimed = {}, set()
        for pid, wins in win_pids.items():
            root = root_of(pid)
            if root in claimed and root not in apps:
                continue
            app = apps.setdefault(root, {"root": root, "windows": []})
            app["windows"].extend(wins)
            claimed.add(root)

        def subtree(pid, acc):
            acc.append(pid)
            for c in children.get(pid, []):
                if c in rows and c not in claimed_tree and c not in apps:
                    claimed_tree.add(c)
                    subtree(c, acc)
            return acc

        claimed_tree = set(apps)
        out_apps = []
        for root, app in apps.items():
            pids = subtree(root, [])
            members = [rows[p] for p in pids]
            dn, raw = display_name(rows[root])
            if raw in HIDE_FROM_APPS:
                claimed_tree.difference_update(pids)
                continue
            w0 = app["windows"][0]
            info = desktop_info(w0.get("app") or "") or desktop_info((w0.get("cls") or "").lower())
            name = (info or {}).get("name") or dn
            icon = (info or {}).get("icon") or w0.get("app") or w0.get("cls") or raw
            titles = [w.get("title") for w in app["windows"] if w.get("title")]
            out_apps.append(self._group(name, icon, members, "app", titles=titles,
                                        window_ids=[w.get("id") for w in app["windows"]]))

        background, system = [], []
        for pid, r in rows.items():
            if pid in claimed_tree:
                continue
            dn, raw = display_name(r)
            entry = self._group(dn, "", [r], "bg" if r["uid"] == UID else "sys")
            (background if r["uid"] == UID else system).append(entry)
        return out_apps, self._merge(background), self._merge(system)

    @staticmethod
    def _merge(entries):
        """Gleichnamige Hintergrundprozesse zusammenfassen (z. B. 5× „php-fpm“)."""
        by = {}
        for e in entries:
            if e["name"] in by:
                g = by[e["name"]]
                g["pids"] += e["pids"]
                g["cpu"] += e["cpu"]
                g["mem"] += e["mem"]
                g["disk"] += e["disk"]
                g["members"] += e["members"]
                g["count"] += 1
            else:
                by[e["name"]] = e
        return list(by.values())

    @staticmethod
    def _group(name, icon, members, kind, titles=None, window_ids=None):
        return {
            "name": name, "icon": icon, "kind": kind,
            "pids": [m["pid"] for m in members],
            "cpu": sum(m["cpu"] for m in members),
            "mem": sum(m["mem"] for m in members),
            "disk": sum(m["disk"] for m in members),
            "count": len(members),
            "titles": titles or [],
            "windowIds": window_ids or [],
            "members": [{"pid": m["pid"], "name": display_name(m)[0], "cpu": m["cpu"], "mem": m["mem"],
                         "disk": m["disk"], "user": m["user"], "status": m["status"]} for m in members],
            "exe": members[0]["exe"] if members else "",
            "user": members[0]["user"] if members else "",
            "status": members[0]["status"] if members else "",
        }


# ---- Beenden --------------------------------------------------------------------------------------
def end_pids(pids, force=False):
    """Beendet Prozesse. → (ok, brauchen_admin)"""
    sig = signal.SIGKILL if force else signal.SIGTERM
    need_admin = []
    for pid in pids:
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            need_admin.append(pid)
    return need_admin


def end_pids_admin(pids, force=False):
    if not pids:
        return True
    r = subprocess.run(["pkexec", "/usr/bin/kill", "-KILL" if force else "-TERM", *map(str, pids)],
                       capture_output=True, text=True, timeout=120)
    return r.returncode == 0


def alive(pids):
    return [p for p in pids if psutil.pid_exists(p)]


# ---- Autostart ----------------------------------------------------------------------------------------
def autostart_dirs():
    user = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart"
    return user, [Path("/etc/xdg/autostart"), Path("/usr/share/creative-os/xdg/autostart")]


HIDDEN_AUTOSTART = {"creative-", "org.kde.", "xdg-user-dirs", "polkit", "kde", "baloo", "pam_kwallet", "at-spi",
                    "gnome-keyring", "geoclue", "org.freedesktop", "pipewire", "wireplumber", "spice-vdagent",
                    "imsettings", "abrt", "gmenudbusmenuproxy", "xembedsniproxy", "powerdevil", "kaccess", "klipper"}


def _parse_desktop(path):
    data = {}
    section = ""
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("["):
                section = line.strip()
                continue
            if section == "[Desktop Entry]" and "=" in line:
                k, v = line.split("=", 1)
                data.setdefault(k.strip(), v.strip())
    except OSError:
        pass
    return data


def list_autostart():
    user, system = autostart_dirs()
    entries = {}
    for d in system + [user]:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.desktop")):
            data = _parse_desktop(f)
            entries[f.name] = {"file": f.name, "data": data, "user": d == user}
    out = []
    for fname, e in entries.items():
        if any(fname.startswith(h) for h in HIDDEN_AUTOSTART) and not e["user"]:
            continue
        d = e["data"]
        if d.get("NoDisplay", "").lower() == "true" and not e["user"]:
            continue
        only = d.get("OnlyShowIn", "")
        if only and "KDE" not in only:
            continue
        enabled = d.get("Hidden", "false").lower() != "true" and d.get("X-GNOME-Autostart-enabled", "true").lower() != "false"
        out.append({"file": fname, "name": d.get("Name[de]") or d.get("Name") or fname[:-8],
                    "icon": d.get("Icon", ""), "command": d.get("Exec", ""), "enabled": enabled,
                    "publisher": d.get("X-Creative-Publisher", "")})
    out.sort(key=lambda x: x["name"].casefold())
    return out


def set_autostart(fname, enabled):
    user, system = autostart_dirs()
    user.mkdir(parents=True, exist_ok=True)
    target = user / fname
    if not target.exists():
        for d in system:
            if (d / fname).exists():
                target.write_text((d / fname).read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                break
        else:
            return False
    lines = [l for l in target.read_text(encoding="utf-8", errors="replace").splitlines()
             if not l.startswith(("Hidden=", "X-GNOME-Autostart-enabled="))]
    out, inserted = [], False
    for l in lines:
        out.append(l)
        if l.strip() == "[Desktop Entry]" and not inserted:
            out.append(f"Hidden={'false' if enabled else 'true'}")
            inserted = True
    target.write_text("\n".join(out) + "\n", encoding="utf-8")
    return True
