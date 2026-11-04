"""Datensicherung: eigene Dateien auf eine externe Platte sichern (rsync).

Ziel:  <Laufwerk>/Creative-OS-Sicherung/<Rechner>-<Benutzer>/
Was dort gelöscht oder überschrieben würde, wandert nach „Ältere Versionen/<Datum>“ –
so geht nichts verloren. Ausgelassen werden Zwischenspeicher, Papierkorb und große
Spiele-Bibliotheken (lassen sich jederzeit neu laden).

Auch als Befehl nutzbar:  creative-backup --run | --auto
  --auto sichert nur, wenn automatisch eingeschaltet ist, das Ziel eingesteckt ist
  und die letzte Sicherung über einen Tag her ist (läuft stündlich im Hintergrund).
"""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

CFG = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "creative-os" / "backup.json"
EXCLUDES = [
    ".cache/", ".local/share/Trash/", ".local/share/Steam/", ".steam/", ".var/app/*/cache/",
    ".local/share/containers/", ".local/share/flatpak/", ".local/share/baloo/", "Creative-OS-Sicherung/",
    "*.tmp", ".thumbnails/", "ISOs/", ".mozilla/firefox/*/cache2/",
]


def load():
    cfg = {"target": "", "uuid": "", "label": "", "auto": False, "last": 0, "lastResult": ""}
    try:
        data = json.loads(CFG.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            cfg.update({k: v for k, v in data.items() if k in cfg})
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg):
    CFG.parent.mkdir(parents=True, exist_ok=True)
    tmp = CFG.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CFG)


def drives():
    """Beschreibbare Zusatz-Laufwerke (USB-Platten, zweite Platte) – nie das System."""
    try:
        out = subprocess.run(["lsblk", "-J", "--tree=PATH", "-b", "-o", "PATH,UUID,LABEL,FSTYPE,MOUNTPOINTS,FSAVAIL,FSSIZE,TRAN,RM"],
                             capture_output=True, text=True, timeout=5).stdout
        data = json.loads(out).get("blockdevices", [])
    except (OSError, ValueError, subprocess.SubprocessError):
        return []

    def walk(nodes):
        for n in nodes or []:
            yield n
            yield from walk(n.get("children"))

    res = []
    for n in walk(data):
        for m in n.get("mountpoints") or []:
            if not m or not (m.startswith("/run/media/") or m.startswith("/var/mnt/") or m.startswith("/mnt/")):
                continue
            if not os.access(m, os.W_OK):
                continue
            free = int(n.get("fsavail") or 0)
            size = int(n.get("fssize") or 0)
            name = n.get("label") or Path(m).name
            res.append({"path": m, "uuid": n.get("uuid") or "", "label": name,
                        "free": free, "size": size,
                        "text": f"{name} · {free / 1e9:.0f} GB frei von {size / 1e9:.0f} GB"})
    return res


def target_dir(mount):
    return Path(mount) / "Creative-OS-Sicherung" / f"{socket.gethostname()}-{os.environ.get('USER', 'benutzer')}"


def find_target(cfg):
    """Ziel-Laufwerk wiederfinden – auch wenn es beim nächsten Mal woanders eingehängt ist."""
    for d in drives():
        if cfg.get("uuid") and d["uuid"] == cfg["uuid"]:
            return d["path"]
    if cfg.get("target") and os.path.ismount(cfg["target"]):
        return cfg["target"]
    return ""


def run(progress=None):
    """Sicherung ausführen. progress(prozent, text). Gibt (ok, text) zurück."""
    cfg = load()
    mount = find_target(cfg)
    if not mount:
        return False, "Das Sicherungs-Laufwerk ist nicht eingesteckt."
    if not shutil.which("rsync"):
        return False, "rsync fehlt."
    dest = target_dir(mount)
    dest.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d_%H-%M")
    args = ["rsync", "-a", "--delete", "--backup", f"--backup-dir={dest.parent / 'Ältere Versionen' / stamp}",
            "--info=progress2", "--no-inc-recursive", "--human-readable"]
    if _is_fat(mount):
        args += ["--no-perms", "--no-owner", "--no-group", "--modify-window=2"]
    for e in EXCLUDES:
        args += ["--exclude", e]
    args += [str(Path.home()) + "/", str(dest) + "/"]
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
                         env={**os.environ, "LC_ALL": "C"})
    buf = ""
    while True:
        ch = p.stdout.read(1)
        if not ch:
            break
        if ch in "\r\n":
            m = re.search(r"(\d+)%", buf)
            if m and progress:
                speed = re.search(r"([\d.,]+[kMG]B/s)", buf)
                progress(int(m.group(1)), "Sichere … " + (speed.group(1) if speed else ""))
            buf = ""
        else:
            buf += ch
    err = p.stderr.read()
    code = p.wait()
    ok = code in (0, 23, 24)            # 23/24: einzelne Dateien nicht lesbar/verschwunden – trotzdem gesichert
    cfg["last"] = int(time.time()) if ok else cfg.get("last", 0)
    cfg["lastResult"] = "ok" if code == 0 else ("teilweise" if ok else "fehler")
    save(cfg)
    if ok:
        return True, "Sicherung fertig." if code == 0 else "Sicherung fertig – einige Dateien waren gesperrt und fehlen."
    return False, "Sicherung fehlgeschlagen: " + (err.strip().splitlines() or ["unbekannter Fehler"])[-1][:160]


def _is_fat(mount):
    try:
        out = subprocess.run(["findmnt", "-n", "-o", "FSTYPE", mount], capture_output=True, text=True).stdout.strip()
        return out in ("vfat", "exfat", "ntfs", "ntfs3", "fuseblk")
    except OSError:
        return False


def _notify(title, body):
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", "Datensicherung", "-i", "drive-harddisk", title, body])
    else:
        subprocess.run(["gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications",
                        "--object-path", "/org/freedesktop/Notifications", "--method",
                        "org.freedesktop.Notifications.Notify", "Datensicherung", "0", "drive-harddisk",
                        title, body, "[]", "{}", "6000"], capture_output=True)


def cli():
    if "--auto" in sys.argv:
        cfg = load()
        if not cfg.get("auto") or time.time() - cfg.get("last", 0) < 23 * 3600 or not find_target(cfg):
            return 0
        _notify("Datensicherung läuft", "Deine Dateien werden auf „" + (cfg.get("label") or "das Laufwerk") + "“ gesichert.")
        ok, text = run()
        _notify("Datensicherung fertig" if ok else "Datensicherung fehlgeschlagen", text)
        return 0 if ok else 1
    if "--run" in sys.argv:
        ok, text = run(lambda pct, t: print(f"@@ {pct} {t}", flush=True))
        print(("@@ok " if ok else "@@fehler ") + text, flush=True)
        return 0 if ok else 1
    print(__doc__)
    return 0


# ---- Systemsteuerung -------------------------------------------------------------------------
try:
    from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot
except ImportError:      # als reiner Befehl ohne Qt nutzbar
    QObject = None

if QObject is not None:
    class BackupModel(QObject):
        changed = Signal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self._cfg = load()
            self._drives = []
            self._running = False
            self._percent = 0
            self._text = ""
            self._proc = None
            self.refresh()
            self._timer = QTimer(self)
            self._timer.setInterval(3000)
            self._timer.timeout.connect(self.refresh)
            self._timer.start()

        @Slot()
        def refresh(self):
            d = drives()
            if d != self._drives:
                self._drives = d
                self.changed.emit()

        @Slot(str)
        def setTarget(self, path):
            d = next((x for x in self._drives if x["path"] == path), None)
            if d:
                self._cfg.update({"target": d["path"], "uuid": d["uuid"], "label": d["label"]})
                save(self._cfg)
                self.changed.emit()

        @Slot(bool)
        def setAuto(self, on):
            self._cfg["auto"] = bool(on)
            save(self._cfg)
            self.changed.emit()

        @Slot()
        def start(self):
            if self._running:
                return
            self._running, self._percent, self._text = True, 0, "Sicherung startet …"
            self.changed.emit()
            p = QProcess(self)
            p.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            buf = {"s": ""}

            def read():
                buf["s"] += bytes(p.readAllStandardOutput()).decode("utf-8", "replace")
                *lines, buf["s"] = buf["s"].split("\n")
                for line in lines:
                    if line.startswith("@@ok ") or line.startswith("@@fehler "):
                        self._text = line.split(" ", 1)[1]
                    elif line.startswith("@@ "):
                        parts = line[3:].split(" ", 1)
                        try:
                            self._percent = int(parts[0])
                        except ValueError:
                            pass
                        self._text = parts[1] if len(parts) > 1 else self._text
                self.changed.emit()

            def finished(code, _status):
                read()
                self._running = False
                self._cfg = load()
                self.changed.emit()

            p.readyReadStandardOutput.connect(read)
            p.finished.connect(finished)
            self._proc = p
            p.start("creative-backup", ["--run"])

        @Slot()
        def stop(self):
            if self._proc is not None and self._running:
                self._proc.terminate()

        @Slot()
        def openBackup(self):
            mount = find_target(self._cfg)
            if mount:
                folder = target_dir(mount)
                prog = ["creative-files", str(folder)] if shutil.which("creative-files") else ["xdg-open", str(folder)]
                subprocess.Popen(prog, start_new_session=True)

        def _last_text(self):
            last = self._cfg.get("last", 0)
            if not last:
                return "Noch keine Sicherung"
            t = time.strftime("%d.%m.%Y um %H:%M Uhr", time.localtime(last))
            return f"Letzte Sicherung: {t}" + (" (einige Dateien fehlten)" if self._cfg.get("lastResult") == "teilweise" else "")

        drives = Property("QVariantList", lambda self: self._drives, notify=changed)
        target = Property(str, lambda self: find_target(self._cfg), notify=changed)
        targetLabel = Property(str, lambda self: self._cfg.get("label", ""), notify=changed)
        auto = Property(bool, lambda self: bool(self._cfg.get("auto")), notify=changed)
        running = Property(bool, lambda self: self._running, notify=changed)
        percent = Property(int, lambda self: self._percent, notify=changed)
        text = Property(str, lambda self: self._text, notify=changed)
        lastText = Property(str, _last_text, notify=changed)


if __name__ == "__main__":
    sys.exit(cli())
