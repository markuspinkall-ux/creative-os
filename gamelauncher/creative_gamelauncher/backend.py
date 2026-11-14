"""Daten und Aktionen des Game Launchers für die Oberfläche."""

import json
import os
import queue
import shutil
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

from PySide6.QtCore import Property, QObject, QProcess, QTimer, QUrl, Signal, Slot

from creative_shell.mainthread import post

from . import steam
from .pad import Pads

CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "creative-gamelauncher"
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "creative-os" / "gamelauncher.json"


def load_config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(**changes):
    data = {**load_config(), **changes}
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(CONFIG)


def size_text(n):
    if n <= 0:
        return ""
    gb = n / 1e9
    return (f"{gb:.1f} GB" if gb >= 1 else f"{n / 1e6:.0f} MB").replace(".", ",")


def play_text(minutes):
    if minutes <= 0:
        return ""
    if minutes < 60:
        return f"{minutes} Min. gespielt"
    hours = minutes / 60
    return (f"{hours:.1f}".replace(".", ",").replace(",0", "") if hours < 10 else str(round(hours))) + " Std. gespielt"


def last_text(stamp):
    if stamp <= 0:
        return ""
    days = (time.time() - stamp) / 86400
    if days < 1 and time.localtime(stamp).tm_yday == time.localtime().tm_yday:
        return "heute"
    if days < 2:
        return "gestern"
    if days < 14:
        return f"vor {int(days)} Tagen"
    return time.strftime("%d.%m.%Y", time.localtime(stamp))


def steam_command():
    for c in ("steam",):
        if shutil.which(c):
            return [c]
    if shutil.which("flatpak") and (Path.home() / ".var/app/com.valvesoftware.Steam").is_dir():
        return ["flatpak", "run", "com.valvesoftware.Steam"]
    return None


def _pid_alive(pidfile):
    try:
        pid = int(Path(pidfile).read_text().strip())
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes()
    except (OSError, ValueError):
        return False
    return b"steam" in cmd.lower()


def steam_running():
    """Läuft Steam schon (auch unsichtbar im Hintergrund)?"""
    home = Path.home()
    for pidfile in (home / ".steam/steam.pid", home / ".var/app/com.valvesoftware.Steam/.steam/steam.pid"):
        if _pid_alive(pidfile):
            return True
    return False


class Launcher(QObject):
    changed = Signal()
    gamesChanged = Signal()
    action = Signal(str)            # Controller-Taste: a, b, x, y, lb, rb, menu, view, guide, left, right, up, down
    toast = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = None
        self._games = []
        self._pads = 0
        self._loading = True
        self._images = queue.Queue()
        self._asked = set()
        CACHE.mkdir(parents=True, exist_ok=True)
        threading.Thread(target=self._image_worker, daemon=True).start()
        self._padreader = Pads(lambda name: post(self.action.emit, name),
                               lambda n: post(self._set_pads, n))
        self._padreader.start()
        self._poll = QTimer(self)
        self._poll.setInterval(4000)
        self._poll.timeout.connect(self._refresh_progress)
        self._poll.start()
        # Steam leise im Hintergrund starten und erst dann den Auftrag schicken
        self._pending = []                 # wartende steam://-Aufträge
        self._wait_since = 0.0
        self._ready_at = 0.0
        self._steam_wait = QTimer(self)
        self._steam_wait.setInterval(1000)
        self._steam_wait.timeout.connect(self._check_steam_started)
        self.refresh()

    # ---- Bibliothek ------------------------------------------------------------------------
    @Slot()
    def refresh(self):
        def work():
            try:
                root, games = steam.library()
            except Exception as exc:  # noqa: BLE001 – kaputte Steam-Dateien dürfen nichts abstürzen lassen
                print("Game Launcher: Bibliothek nicht lesbar:", exc)
                root, games = steam.steam_root(), []
            post(self._apply, root, games)
        threading.Thread(target=work, daemon=True).start()

    def _apply(self, root, games):
        self._root = root
        self._games = [self._decorate(g) for g in games]
        self._loading = False
        self.gamesChanged.emit()
        self.changed.emit()

    def _decorate(self, g):
        appid = g["appid"]
        out = dict(g)
        out["sizeText"] = size_text(g.get("size", 0))
        out["playText"] = play_text(g.get("minutes", 0))
        out["lastText"] = last_text(g.get("lastPlayed", 0))
        for kind in ("cover", "hero"):
            local = steam.image(self._root, appid, kind) if self._root else ""
            if not local and kind == "hero":
                local = steam.image(self._root, appid, "header") if self._root else ""
            cached = CACHE / f"{appid}_{kind}.jpg"
            if not local and cached.is_file() and cached.stat().st_size > 0:
                local = str(cached)
            out[kind] = QUrl.fromLocalFile(local).toString() if local else ""
            if not local and (appid, kind) not in self._asked:
                self._asked.add((appid, kind))
                self._images.put((appid, kind))
        return out

    def _image_worker(self):
        while True:
            appid, kind = self._images.get()
            target = CACHE / f"{appid}_{kind}.jpg"
            missing = CACHE / f"{appid}_{kind}.fehlt"
            if missing.exists():
                continue
            try:
                req = Request(steam.CDN.format(appid=appid, name=steam.CDN_NAMES[kind]),
                              headers={"User-Agent": "CreativeOS-GameLauncher/1.0"})
                with urlopen(req, timeout=10) as r:
                    data = r.read(8 * 1024 * 1024)
                tmp = target.with_suffix(".tmp")
                tmp.write_bytes(data)
                tmp.replace(target)
                post(self._image_ready, appid, kind, str(target))
            except OSError as exc:
                if getattr(exc, "code", None) == 404:
                    missing.touch()

    def _image_ready(self, appid, kind, path):
        for g in self._games:
            if g["appid"] == appid:
                g[kind] = QUrl.fromLocalFile(path).toString()
                self.gamesChanged.emit()
                return

    def _refresh_progress(self):
        """Download-Fortschritt und neu installierte Spiele (nur Manifeste, schnell)."""
        if self._root is None:
            return
        try:
            now = steam.installed_games(self._root)
        except Exception:  # noqa: BLE001
            return
        changed = False
        known = {g["appid"]: g for g in self._games}
        for appid, g in now.items():
            cur = known.get(appid)
            if cur is None:
                self.refresh()
                return
            for key in ("installed", "ready", "progress", "size"):
                if cur.get(key) != g[key]:
                    cur[key] = g[key]
                    changed = True
            cur["sizeText"] = size_text(cur.get("size", 0))
        for appid, cur in known.items():
            if cur.get("installed") and appid not in now:     # deinstalliert
                cur.update(installed=False, ready=False, progress=0.0, size=0, sizeText="")
                changed = True
        if changed:
            self.gamesChanged.emit()

    def _set_pads(self, n):
        if n != self._pads:
            self._pads = n
            self.changed.emit()

    # ---- Aktionen ---------------------------------------------------------------------------
    def _steam(self, url, message, quiet=False):
        """Auftrag an Steam schicken. quiet: Steam vorher unsichtbar starten (nur Tray-Symbol),
        damit sich nicht das große Steam-Fenster öffnet – z. B. beim Installieren und Spielen."""
        cmd = steam_command()
        if cmd is None:
            self.toast.emit("Steam ist nicht installiert.")
            return False
        if quiet and not steam_running():
            self._pending.append(url)
            if not self._steam_wait.isActive():
                QProcess.startDetached(cmd[0], cmd[1:] + ["-silent"])
                self._wait_since = time.monotonic()
                self._ready_at = 0.0
                self._steam_wait.start()
                self.changed.emit()
            if message:
                self.toast.emit("Steam startet im Hintergrund … " + message)
            return True
        QProcess.startDetached(cmd[0], cmd[1:] + [url])
        if message:
            self.toast.emit(message)
        return True

    def _check_steam_started(self):
        """Warten, bis Steam läuft und bereit ist – dann die wartenden Aufträge schicken."""
        now = time.monotonic()
        if not self._ready_at and steam_running():
            self._ready_at = now + 8          # Steam braucht nach dem Start noch einen Moment
        if self._ready_at and now >= self._ready_at:
            self._steam_wait.stop()
            self.changed.emit()
            cmd = steam_command()
            for url in self._pending:
                QProcess.startDetached(cmd[0], cmd[1:] + [url])
            self._pending = []
            return
        if now - self._wait_since > 180:      # z. B. Steam-Update beim ersten Start dauert zu lange
            self._steam_wait.stop()
            self.changed.emit()
            cmd = steam_command()
            for url in self._pending:          # trotzdem schicken – notfalls öffnet sich Steam normal
                QProcess.startDetached(cmd[0], cmd[1:] + [url])
            self._pending = []

    @Slot(int, str)
    def play(self, appid, name):
        self._steam(f"steam://rungameid/{appid}", f"„{name}“ startet …", quiet=True)

    @Slot(int, str)
    def install(self, appid, name):
        self._steam(f"steam://install/{appid}",
                    f"Gleich fragt Steam in einem kleinen Fenster, wohin „{name}“ installiert werden soll. "
                    "Den Fortschritt siehst du hier im Game Launcher.", quiet=True)

    @Slot(int)
    def details(self, appid):
        self._steam(f"steam://nav/games/details/{appid}", "")

    @Slot()
    def openStore(self):
        self._steam("steam://store", "Der Steam-Shop öffnet sich …")

    @Slot()
    def openSteam(self):
        self._steam("steam://open/main", "")

    # ---- QML -------------------------------------------------------------------------------
    games = Property("QVariantList", lambda self: self._games, notify=gamesChanged)
    steamFound = Property(bool, lambda self: self._root is not None, notify=changed)
    steamInstalled = Property(bool, lambda self: steam_command() is not None, constant=True)
    loading = Property(bool, lambda self: self._loading, notify=changed)
    steamStarting = Property(bool, lambda self: self._steam_wait.isActive(), notify=changed)
    pads = Property(int, lambda self: self._pads, notify=changed)
    padSupport = Property(bool, lambda self: self._padreader.available, constant=True)
