"""Bereinigung (Systemsteuerung › Bereinigung) – Platz schaffen wie mit CCleaner.

Erst „Analysieren“: zeigt je Bereich, wie viel Platz frei würde. Dann „Bereinigen“: löscht nur,
was angehakt ist. Gelöscht werden ausschließlich Dinge, die sich von selbst neu bilden oder die
du schon weggeworfen hast – nie Dokumente, Bilder, Einstellungen oder Programme, die du nutzt.

Bereiche:
* Papierkorb (auch auf externen Laufwerken)
* Vorschaubilder (Miniaturansichten im Dateimanager)
* Browser-Zwischenspeicher (Firefox, Chromium, Chrome, Gibeon-Browser …)
* Programm-Zwischenspeicher (~/.cache und die der Flatpak-Apps) – ohne KI-Modelle
* KI-Modelle (aus) – mehrere GB, werden aber bei der nächsten Nutzung neu geladen
* Shader-Cache von Spielen (aus) – Spiele bauen ihn beim nächsten Start neu (ruckelt kurz)
* Ungenutzte Flatpak-Laufzeiten – Reste deinstallierter Apps
* Systemprotokolle (aus, braucht Passwort) – auf die letzten 100 MB kürzen
"""

import os
import shutil
import subprocess
import threading
from pathlib import Path

# Modelle für KI-Helfer, 3D Studio, Broadcast-Upscaling: groß und teuer neu zu laden – eigener Bereich
MODEL_CACHES = ("huggingface", "torch", "creative-ki", "creative3d", "gibeon-3d", "trellis", "onnx", "ollama")
BROWSER_CACHES = ("mozilla", "chromium", "google-chrome", "BraveSoftware", "vivaldi", "microsoft-edge",
                  "creative-browser", "gibeon-browser", "zen", "librewolf")
# Bleibt stehen, auch wenn es unter ~/.cache liegt
KEEP = {"thumbnails", "flatpak", "fontconfig"}


def home():
    return Path.home()


def cache_home():
    return Path(os.environ.get("XDG_CACHE_HOME") or home() / ".cache")


def data_home():
    return Path(os.environ.get("XDG_DATA_HOME") or home() / ".local" / "share")


def size_of(path):
    """Belegter Platz in Bytes (Links werden nicht verfolgt)."""
    p = Path(path)
    try:
        if p.is_symlink() or p.is_file():
            return p.lstat().st_size
    except OSError:
        return 0
    total = 0
    for root, dirs, files in os.walk(p, onerror=lambda e: None):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_blocks * 512
            except OSError:
                pass
    return total


def remove(path):
    p = Path(path)
    try:
        if p.is_symlink() or p.is_file():
            p.unlink()
        elif p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
    except OSError:
        pass


def children(path):
    try:
        return list(Path(path).iterdir())
    except OSError:
        return []


def trash_dirs():
    out = [data_home() / "Trash"]
    uid = os.getuid()
    media = Path("/run/media") / (os.environ.get("USER") or home().name)
    for drive in children(media):
        out.append(drive / f".Trash-{uid}")
    return [d for d in out if d.exists()]


def _paths(key):
    """Was zu einem Bereich gehört (Liste von Pfaden, deren Inhalt gelöscht wird)."""
    cache = cache_home()
    if key == "trash":
        return [c for d in trash_dirs() for c in children(d) if c.name in ("files", "info", "expunged")]
    if key == "thumbs":
        return [cache / "thumbnails"]
    if key == "browser":
        out = [cache / n for n in BROWSER_CACHES]
        for app in children(home() / ".var" / "app"):
            low = app.name.lower()
            if any(b.lower() in low for b in ("firefox", "chromium", "chrome", "brave", "vivaldi", "librewolf", "zen")):
                out.append(app / "cache")
        return [p for p in out if p.exists()]
    if key == "apps":
        skip = KEEP | set(MODEL_CACHES) | set(BROWSER_CACHES)
        out = [c for c in children(cache) if c.name not in skip and not c.name.startswith(".")]
        for app in children(home() / ".var" / "app"):
            low = app.name.lower()
            if not any(b.lower() in low for b in ("firefox", "chromium", "chrome", "brave", "vivaldi", "librewolf", "zen")):
                out.append(app / "cache")
        return [p for p in out if p.exists()]
    if key == "models":
        return [cache / n for n in MODEL_CACHES if (cache / n).exists()]
    if key == "shader":
        out = [data_home() / "Steam" / "steamapps" / "shadercache",
               home() / ".steam" / "steam" / "steamapps" / "shadercache",
               home() / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam" / "steamapps" / "shadercache",
               cache / "mesa_shader_cache", cache / "mesa_shader_cache_db", cache / "nvidia" / "GLCache",
               cache / "radv_builtin_shaders"]
        seen, res = set(), []
        for p in out:
            try:
                r = p.resolve()
            except OSError:
                continue
            if p.exists() and r not in seen:
                seen.add(r)
                res.append(p)
        return res
    return []


CATEGORIES = [
    {"key": "trash", "name": "Papierkorb", "hint": "Alles, was du schon gelöscht hast – auch auf externen Laufwerken", "on": True},
    {"key": "thumbs", "name": "Vorschaubilder", "hint": "Miniaturansichten im Dateimanager – entstehen bei Bedarf neu", "on": True},
    {"key": "browser", "name": "Browser-Zwischenspeicher", "hint": "Zwischengespeicherte Webseiten. Anmeldungen und Lesezeichen bleiben. Browser vorher schließen", "on": True},
    {"key": "apps", "name": "Programm-Zwischenspeicher", "hint": "Zwischenspeicher aller Programme und Flatpak-Apps – bilden sich von selbst neu", "on": True},
    {"key": "flatpak", "name": "Ungenutzte Flatpak-Laufzeiten", "hint": "Reste von Apps, die nicht mehr installiert sind", "on": True},
    {"key": "shader", "name": "Shader-Cache von Spielen", "hint": "Spiele bauen ihn beim nächsten Start neu – kann anfangs kurz ruckeln", "on": False},
    {"key": "models", "name": "KI-Modelle", "hint": "KI-Helfer, 3D Studio, Broadcast: werden bei der nächsten Nutzung neu geladen (dauert)", "on": False},
    {"key": "journal", "name": "Systemprotokolle", "hint": "Auf die letzten 100 MB kürzen – fragt nach dem Passwort", "on": False},
]


def journal_size():
    try:
        r = subprocess.run(["journalctl", "--disk-usage"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return 0
    import re
    m = re.search(r"take up ([\d.,]+)\s*([KMGT]?)", r.stdout or "")
    if not m:
        return 0
    n = float(m.group(1).replace(",", "."))
    return int(n * {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3, "T": 1024 ** 4}[m.group(2)])


def analyze(key):
    """(Bytes, Anzahl Einträge oder Hinweis)."""
    if key == "flatpak":
        # Flatpak kann nicht vorab zählen, ohne zu löschen – geprüft wird beim Bereinigen
        return 0, "wird beim Bereinigen geprüft"
    if key == "journal":
        size = journal_size()
        return max(0, size - 100 * 1024 ** 2), ""
    total = 0
    for p in _paths(key):
        total += size_of(p)
    return total, ""


def clean(key):
    """Bereich leeren. Rückgabe: (ok, Text)."""
    if key == "flatpak":
        ok = True
        for scope in ("--user", "--system"):
            try:
                r = subprocess.run(["flatpak", "uninstall", scope, "--unused", "--noninteractive", "-y"],
                                   capture_output=True, text=True, timeout=600)
                ok = ok and r.returncode == 0
            except (OSError, subprocess.SubprocessError):
                ok = False
        return ok, ""
    if key == "journal":
        try:
            r = subprocess.run(["pkexec", "journalctl", "--vacuum-size=100M"], capture_output=True, text=True, timeout=300)
            return r.returncode == 0, "" if r.returncode == 0 else "abgebrochen"
        except (OSError, subprocess.SubprocessError) as e:
            return False, str(e)
    for p in _paths(key):
        if key in ("thumbs", "browser", "apps", "shader", "models") and p.is_dir():
            for c in children(p):          # den Ordner selbst stehen lassen, nur den Inhalt leeren
                remove(c)
        else:
            remove(p)
    return True, ""


def human(n):
    if n <= 0:
        return "0 MB"
    for unit, f in (("GB", 1024 ** 3), ("MB", 1024 ** 2)):
        if n >= f or unit == "MB":
            v = n / f
            return (f"{v:.1f}" if v < 10 else f"{v:.0f}").replace(".", ",") + " " + unit
    return f"{n} B"


try:
    from PySide6.QtCore import Property, QObject, Signal, Slot
except ImportError:
    QObject = None

if QObject is not None:
    class CleanupModel(QObject):
        changed = Signal()
        _done = Signal(object)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._rows = [dict(c, size=0, sizeText="", note="", checked=c["on"], done=False) for c in CATEGORIES]
            self._busy, self._phase, self._summary = False, "", ""
            self._done.connect(self._apply)

        def _run(self, phase, work):
            if self._busy:
                return
            self._busy, self._phase = True, phase
            self.changed.emit()
            threading.Thread(target=lambda: self._done.emit(work()), daemon=True).start()

        def _apply(self, result):
            phase, data = result
            for row in self._rows:
                if row["key"] in data:
                    row.update(data[row["key"]])
            self._busy, self._phase = False, ""
            if phase == "analyze":
                total = sum(r["size"] for r in self._rows if r["checked"])
                self._summary = f"Bereinigen gibt etwa {human(total)} frei."
            else:
                freed = sum(v.get("freed", 0) for v in data.values())
                self._summary = f"Fertig – {human(freed)} freigegeben."
            self.changed.emit()

        @Slot()
        def analyze(self):
            keys = [r["key"] for r in self._rows]

            def work():
                out = {}
                for k in keys:
                    size, note = analyze(k)
                    out[k] = {"size": size, "sizeText": human(size) if k != "flatpak" else "", "note": note, "done": False}
                return "analyze", out
            self._run("Analysiere …", work)

        @Slot()
        def clean(self):
            keys = [r["key"] for r in self._rows if r["checked"]]
            before = {r["key"]: r["size"] for r in self._rows}

            def work():
                out = {}
                for k in keys:
                    ok, note = clean(k)
                    size, _n = analyze(k)
                    out[k] = {"size": size, "sizeText": human(size) if k != "flatpak" else "",
                              "note": note or ("bereinigt" if ok else "nicht alles ging"), "done": ok,
                              "freed": max(0, before.get(k, 0) - size)}
                return "clean", out
            self._run("Bereinige …", work)

        @Slot(str, bool)
        def setChecked(self, key, on):
            for r in self._rows:
                if r["key"] == key:
                    r["checked"] = bool(on)
            total = sum(r["size"] for r in self._rows if r["checked"])
            if any(r["sizeText"] for r in self._rows):
                self._summary = f"Bereinigen gibt etwa {human(total)} frei."
            self.changed.emit()

        rows = Property("QVariantList", lambda self: [dict(r) for r in self._rows], notify=changed)
        busy = Property(bool, lambda self: self._busy, notify=changed)
        phase = Property(str, lambda self: self._phase, notify=changed)
        summary = Property(str, lambda self: self._summary, notify=changed)
