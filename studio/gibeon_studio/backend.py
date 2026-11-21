"""Studio – Verbindung zwischen Oberfläche (QML), Mischpult, Bildschirmfreigabe und Konten."""

import copy
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QSocketNotifier, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices, QImage, QImageReader, QPainter
from PySide6.QtQuick import QQuickPaintedItem

from . import engine, konten

try:
    from .audio_routing import matching_audio
except ImportError:                                  # Entwicklung: Datei liegt bei Capture
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "capture"))
    try:
        from creative_capture.audio_routing import matching_audio
    except ImportError:
        def matching_audio(_video, _candidates):
            return ""

HERE = Path(__file__).resolve().parent
CFG = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "gibeon-studio" / "studio.json"
CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "gibeon-studio" / "bilder"
CANVAS_ASPECT = 16 / 9
DEFAULTS = {
    "canvas": "1080p30",
    "kbps": 6000,
    # Szenen: je eine Anordnung der Quellen. x, y, w als Anteil der Bildbreite/-höhe, Höhe aus aspect.
    "scenes": [],
    "scene": 0,
    "next_id": 1,
    # alte Einstellungen (vor den Szenen) – werden einmal in „Szene 1“ übernommen
    "main": {"type": "screen", "device": ""},
    "cam": {"on": False, "device": "", "corner": "unten-rechts", "size": "mittel"},
    "audio": {
        "mic": {"on": True, "device": "", "volume": 1.0, "muted": False},
        "desktop": {"on": True, "device": "", "volume": 1.0, "muted": False},
        "extra": {"on": False, "device": "", "volume": 1.0, "muted": False},
    },
    "format": "mp4",
    "targets": {"twitch": True, "youtube": True, "custom": False},
    "custom_url": "",
    "custom_key": "",
    "screen_token": "",
    "chat_open": True,
}
SOURCE_KEYS = ("canvas", "audio")
KINDS = {"screen": "Bildschirm", "camera": "Kamera", "capture": "Capture-Karte", "image": "Bild", "test": "Test"}


def user_dir(kind, fallback):
    try:
        out = subprocess.run(["xdg-user-dir", kind], capture_output=True, text=True, timeout=3).stdout.strip()
        if out and Path(out) != Path.home():
            return Path(out)
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.home() / fallback


def merge(base, data):
    out = copy.deepcopy(base)
    for k, v in (data or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = merge(out[k], v)
        elif k in out and (type(v) is type(out[k]) or (isinstance(out[k], float) and isinstance(v, int))):
            out[k] = v
    return out


def video_devices():
    """Kameras und Capture-Karten: (Gerät, Name)."""
    out = []
    root = Path("/sys/class/video4linux")
    for d in sorted(root.glob("video*"), key=lambda p: int(p.name[5:]) if p.name[5:].isdigit() else 999):
        try:
            if (d / "index").read_text().strip() != "0":
                continue
            name = (d / "name").read_text().strip()
        except OSError:
            continue
        out.append({"id": f"/dev/{d.name}", "name": name or d.name, "virtual": is_virtual(name)})
    return out


def is_virtual(name):
    return any(k in (name or "") for k in ("Gibeon Kamera", "Orbit Kamera", "Creative Kamera"))


def broadcast_green():
    """Broadcast auf grünen Hintergrund stellen – Studio stellt ihn dann durchsichtig."""
    path = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "creative-os" / "broadcast.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict) or data.get("effect") == "green":
        return False
    data["effect"] = "green"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        return False
    return True


def audio_inputs():
    try:
        r = subprocess.run(["pactl", "-f", "json", "list", "sources"], capture_output=True, text=True, timeout=3)
        data = json.loads(r.stdout) if r.returncode == 0 else []
    except (OSError, ValueError, subprocess.SubprocessError):
        data = []
    return [{"id": s.get("name", ""), "name": s.get("description") or s.get("name", "")}
            for s in data if s.get("name") and not s["name"].endswith(".monitor")]


def audio_outputs():
    """Ausgänge, deren Ton Studio mitschneiden kann (Monitor der Lautsprecher/Kopfhörer)."""
    try:
        r = subprocess.run(["pactl", "-f", "json", "list", "sinks"], capture_output=True, text=True, timeout=3)
        data = json.loads(r.stdout) if r.returncode == 0 else []
    except (OSError, ValueError, subprocess.SubprocessError):
        data = []
    out = [{"id": "", "name": "Standard-Ausgabe"}]
    out += [{"id": s["name"] + ".monitor", "name": s.get("description") or s["name"]}
            for s in data if s.get("name")]
    return out


def migrate(cfg):
    """Alte Einstellungen (Hauptbild + Kamera-Ecke) → „Szene 1“."""
    if cfg["scenes"]:
        return False
    items = []
    m, c = cfg["main"], cfg["cam"]
    if m["type"] == "screen":
        items.append(new_item(cfg, "screen"))
    elif m["type"] == "video" and m["device"]:
        items.append(new_item(cfg, "capture", device=m["device"]))
    if c["on"] and c["device"]:
        x, y, w, _h = engine.cam_rect(1920, 1080, c["corner"], c["size"])
        items.append(new_item(cfg, "camera", device=c["device"], x=x / 1920, y=y / 1080, w=w / 1920))
    cfg["scenes"] = [{"name": "Szene 1", "items": items}]
    cfg["scene"] = 0
    return True


def new_item(cfg, kind, **kw):
    """Neue Quelle für eine Szene. Kameras starten abgerundet unten rechts, alles andere füllt das Bild."""
    item = {"id": f"q{cfg['next_id']}", "kind": kind, "device": "", "file": "", "name": "",
            "x": 0.0, "y": 0.0, "w": 1.0, "aspect": CANVAS_ASPECT, "round": False, "hidden": False}
    cfg["next_id"] += 1
    if kind == "camera":
        # 30 % breit, unten rechts mit etwas Rand, abgerundet (Höhe = Breite, weil beide 16:9 sind)
        item.update(x=1 - 0.30 - 0.02, y=1 - 0.30 - 0.035, w=0.30, round=True)
    item.update(kw)
    return item


def item_height(item):
    """Höhe als Anteil der Bildhöhe."""
    return item["w"] * CANVAS_ASPECT / max(0.01, item.get("aspect") or CANVAS_ASPECT)


def item_key(item):
    k = item.get("kind")
    if k == "screen":
        return "screen"
    if k in ("camera", "capture"):
        return f"video:{item['device']}" if item.get("device") else None
    if k == "image":
        return f"image:{item['file']}" if item.get("file") else None
    if k == "test":
        return f"test:{item['id']}"
    return None


def image_png(path, limit=engine.IMAGE_MAX):
    """Bild (jedes Format, das Qt lesen kann) als PNG im Zwischenspeicher: (png, breite, höhe) oder None."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    tag = hashlib.sha1(f"{path}|{st.st_mtime_ns}|{st.st_size}|{limit}".encode()).hexdigest()[:20]
    out = CACHE / f"{tag}.png"
    if out.exists():
        r = QImageReader(str(out))
        size = r.size()
        if size.isValid():
            return str(out), size.width(), size.height()
    r = QImageReader(path)
    r.setAutoTransform(True)
    img = r.read()
    if img.isNull():
        return None
    if max(img.width(), img.height()) > limit:
        img = img.scaled(limit, limit, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    w, h = img.width() // 2 * 2, img.height() // 2 * 2
    img = img.copy(0, 0, max(2, w), max(2, h)).convertToFormat(QImage.Format.Format_ARGB32)
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        if not img.save(str(out), "PNG"):
            return None
    except OSError:
        return None
    return str(out), img.width(), img.height()


class Hub(QObject):
    """Verteilt Vorschaubilder an alle Vorschau-Flächen. Kommt der Hauptthread nicht hinterher,
    wird nur das neueste Bild gezeigt (kein Stau, keine Verzögerung)."""
    frame = Signal()

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._img = QImage()
        self._waiting = False

    def push(self, img):
        with self._lock:
            self._img = img
            if self._waiting:
                return
            self._waiting = True
        self.frame.emit()

    def take(self):
        with self._lock:
            self._waiting = False
            return self._img


HUB = Hub()


class Preview(QQuickPaintedItem):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._img = QImage()
        # Auf der Grafikkarte zeichnen – deutlich flüssiger als in den Arbeitsspeicher
        self.setRenderTarget(QQuickPaintedItem.RenderTarget.FramebufferObject)
        self.setOpaquePainting(True)
        HUB.frame.connect(self._on_frame)

    def _on_frame(self):
        self._img = HUB.take()
        self.update()

    def paint(self, painter):
        painter.fillRect(self.boundingRect(), QColor("#0b0d12"))
        if self._img.isNull():
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = self.boundingRect()
        w = r.width()
        h = w * self._img.height() / self._img.width()
        if h > r.height():
            h = r.height()
            w = h * self._img.width() / self._img.height()
        painter.drawImage(r.adjusted((r.width() - w) / 2, (r.height() - h) / 2,
                                     -(r.width() - w) / 2, -(r.height() - h) / 2), self._img)


class Studio(QObject):
    changed = Signal()
    levelsChanged = Signal()
    toast = Signal(str)
    loginCode = Signal(str, str, str)             # Dienst, Code, Adresse
    categories = Signal(str, "QVariantList")      # Dienst, Treffer
    _async = Signal(object)                       # Ergebnis aus einem Hintergrund-Thread

    def __init__(self, selftest=False, parent=None):
        super().__init__(parent)
        self.selftest = selftest
        self.cfg = copy.deepcopy(DEFAULTS)
        if not selftest:
            try:
                self.cfg = merge(DEFAULTS, json.loads(CFG.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass
        self.mixer = engine.Mixer()
        self.screen = None                        # {"fd":…, "node":…}
        self._portal = None
        self._portal_sock = None
        self._portal_note = None
        self._screen_wanted = False
        self.video_list = []
        self.audio_list = []
        self.output_list = []
        self._images = {}                         # Datei → (png, b, h)
        if selftest:
            # Selbsttest beim Bauen: Testbild, abgerundete Test-Kamera mit Grünschlüssel, ein Bild
            self.cfg["scenes"] = [{"name": "Test", "items": [
                new_item(self.cfg, "test", pattern="smpte"),
                new_item(self.cfg, "test", pattern="ball", x=0.68, y=0.665, w=0.30, round=True, green=True)]}]
        elif migrate(self.cfg):
            self._save()
        self.levels = {}
        self.status = ""
        self.error = ""
        self.rec_file = ""
        self.rec_since = 0.0
        self.live_since = 0.0
        self.live_targets = []
        self.encoder = ""
        self.busy = {}                            # Dienst → Text, solange etwas lädt
        self.channel = {"twitch": {}, "youtube": {}}
        self.targets = {"twitch": "", "youtube": ""}
        self.store = konten.load_store()
        svc = konten.services()
        self.svc = svc
        self.accounts = {
            "twitch": konten.Twitch(self.store.setdefault("twitch", {}), self._save_store, svc["twitch_client_id"]),
            "youtube": konten.YouTube(self.store.setdefault("youtube", {}), self._save_store,
                                      svc["youtube_client_id"], svc["youtube_client_secret"]),
        }
        self.twitch_chat = konten.TwitchChat(self.accounts["twitch"])
        self._async.connect(self._run_async)
        self._rebuild_timer = QTimer(self, singleShot=True, interval=350, timeout=self._rebuild)
        self._save_later = QTimer(self, singleShot=True, interval=600, timeout=self._save)
        self.mixer.on_frame = self._on_frame
        self._poll = QTimer(self, interval=100, timeout=self._poll_engine)
        self._clock = QTimer(self, interval=1000, timeout=self.changed.emit)
        self.refreshDevices()
        self._poll.start()
        self._clock.start()
        if selftest:
            return
        if self._wants_screen():
            self._screen_wanted = True
            self._start_portal()
        self._rebuild()
        for name, acc in self.accounts.items():
            if acc.connected:
                self._load_channel(name)

    # ---- Hilfen ------------------------------------------------------------------------------
    @Slot(object)
    def _run_async(self, fn):
        fn()

    def _save(self):
        if self.selftest:
            return
        try:
            CFG.parent.mkdir(parents=True, exist_ok=True)
            CFG.write_text(json.dumps(self.cfg, indent=1), encoding="utf-8")
        except OSError:
            pass

    def _save_store(self):
        if not self.selftest:
            konten.save_store(self.store)

    def _bg(self, work, done=None, fail=None):
        """work() im Hintergrund; done(ergebnis)/fail(text) danach wieder im Hauptthread."""
        def run():
            try:
                res = work()
            except Exception as e:      # Netz- oder API-Fehler
                msg = konten._msg(e) if isinstance(e, konten.ApiError) else str(e)
                self._async.emit(lambda: (fail or self._fail)(msg))
                return
            if done:
                self._async.emit(lambda: done(res))
        threading.Thread(target=run, daemon=True).start()

    def _fail(self, msg):
        self.toast.emit(msg)

    @property
    def live(self):
        return bool(self.live_targets)

    @property
    def recording(self):
        return "record" in self.mixer.outputs

    # ---- Zustand für die Oberfläche --------------------------------------------------------------
    def _state(self):
        now = time.monotonic()
        acc = {}
        for name, a in self.accounts.items():
            configured = bool(a.client_id)
            acc[name] = {
                "configured": configured, "connected": a.connected, "name": a.login_name,
                "title": self.channel[name].get("title", ""), "category": self.channel[name].get("category", ""),
                "categoryId": self.channel[name].get("category_id", ""),
                "chat": self._chat_url(name), "target": bool(self.targets[name]),
                "busy": self.busy.get(name, ""),
            }
        return {
            "cfg": self.cfg, "videoDevices": self.video_list, "audioDevices": self.audio_list,
            "accounts": acc, "live": self.live, "recording": self.recording,
            "liveTime": _clock(now - self.live_since) if self.live else "",
            "recTime": _clock(now - self.rec_since) if self.recording else "",
            "liveTargets": [t for t, _ in self.live_targets], "encoder": self.encoder or engine.video_encoder()[1]
            if engine.video_encoder() else "kein Kodierer", "status": self.status, "error": self.error,
            "screenReady": self.screen is not None, "screenAsking": self._portal is not None and self.screen is None,
            "recFile": self.rec_file, "canvases": list(engine.CANVAS),
            "locked": self.live or self.recording, "outputDevices": self.output_list,
            "scenes": [{"name": sc["name"], "count": len(sc["items"])} for sc in self.cfg["scenes"]],
            "scene": self.cfg["scene"], "items": self._items_state(),
        }

    def _items_state(self):
        names = {d["id"]: d["name"] for d in self.video_list}
        out = []
        for it in self._scene()["items"]:
            label = it.get("name") or {
                "screen": "Bildschirm", "image": Path(it.get("file") or "Bild").name,
            }.get(it["kind"]) or names.get(it.get("device")) or KINDS.get(it["kind"], it["kind"])
            out.append({"id": it["id"], "kind": it["kind"], "label": label, "device": it.get("device", ""),
                        "x": it["x"], "y": it["y"], "w": it["w"], "h": item_height(it),
                        "round": it.get("round", False), "green": it.get("green", False),
                        "hidden": it.get("hidden", False), "ok": item_key(it) is not None,
                        "virtual": is_virtual(names.get(it.get("device"), ""))})
        return out

    state = Property("QVariantMap", lambda self: self._state(), notify=changed)
    levelMap = Property("QVariantMap", lambda self: dict(self.levels), notify=levelsChanged)

    def _chat_url(self, name):
        a = self.accounts[name]
        if not a.connected:
            return ""
        dark = True
        try:
            look = (Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "creative-os" / "look.conf")
            dark = "design=porzellan" not in look.read_text(encoding="utf-8")
        except OSError:
            pass
        if name == "twitch":
            return a.chat_url(dark)
        return konten.YouTube.chat_url(self.channel["youtube"].get("video", ""), dark)

    # ---- Einstellungen --------------------------------------------------------------------------
    @Slot(str, "QVariant")
    def set(self, path, value):
        """Wert setzen, z. B. set("cam.corner", "oben-links")."""
        keys = path.split(".")
        node = self.cfg
        for k in keys[:-1]:
            node = node.get(k)
            if not isinstance(node, dict):
                return
        if keys[-1] not in node:
            return
        old = node[keys[-1]]
        if isinstance(old, bool):
            value = bool(value)
        elif isinstance(old, float):
            value = float(value)
        elif isinstance(old, int):
            value = int(value)
        elif isinstance(old, str):
            value = str(value)
        if old == value:
            return
        if keys[0] in SOURCE_KEYS and self.live or keys[0] in SOURCE_KEYS and self.recording:
            if not (keys[0] == "audio" and keys[-1] in ("volume", "muted")):
                self.toast.emit("Quellen lassen sich während Aufnahme oder Stream nicht tauschen.")
                self.changed.emit()
                return
        node[keys[-1]] = value
        self._save()
        if keys[0] == "audio" and keys[-1] in ("volume", "muted"):
            a = self.cfg["audio"][keys[1]]
            self.mixer.set_volume(keys[1], a["volume"], a["muted"])
        elif keys[0] in SOURCE_KEYS:
            self._rebuild_timer.start()
        self.changed.emit()

    @Slot()
    def refreshDevices(self):
        self.video_list = video_devices()
        self.audio_list = audio_inputs()
        self.output_list = audio_outputs()
        self.changed.emit()

    # ---- Bildschirm freigeben -----------------------------------------------------------------
    @Slot()
    def chooseScreen(self):
        """Anderen Bildschirm/anderes Fenster wählen (fragt KDE neu)."""
        if self.live or self.recording:
            self.toast.emit("Während Aufnahme oder Stream nicht möglich.")
            return
        self.cfg["screen_token"] = ""
        self._save()
        self._stop_portal()
        self.screen = None
        if not self._wants_screen():
            self._scene()["items"].insert(0, new_item(self.cfg, "screen"))
            self._save()
        self._screen_wanted = True
        self._start_portal()
        self._rebuild_timer.start()
        self.changed.emit()

    def _start_portal(self):
        if self._portal is not None or self.selftest:
            return
        ours, theirs = socket.socketpair()
        args = [sys.executable, "-m", "gibeon_studio.portal", "--sock", str(theirs.fileno())]
        if self.cfg["screen_token"]:
            args += ["--token", self.cfg["screen_token"]]
        env = dict(os.environ, PYTHONPATH=str(HERE.parent))
        try:
            self._portal = subprocess.Popen(args, pass_fds=[theirs.fileno()], stdin=subprocess.PIPE,
                                            stdout=subprocess.DEVNULL, env=env)
        except OSError as e:
            self.toast.emit(f"Bildschirmfreigabe startet nicht: {e}")
            ours.close()
            theirs.close()
            return
        theirs.close()
        ours.setblocking(False)
        self._portal_sock = ours
        self._portal_note = QSocketNotifier(ours.fileno(), QSocketNotifier.Type.Read, self)
        self._portal_note.activated.connect(self._portal_ready)
        self.changed.emit()

    def _portal_ready(self, *_a):
        try:
            data, fds, _flags, _addr = socket.recv_fds(self._portal_sock, 4096, 2)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            data, fds = b"", []
        self._portal_note.setEnabled(False)
        try:
            info = json.loads(data.decode().splitlines()[0]) if data else {"error": "Bildschirmfreigabe beendet"}
        except (ValueError, IndexError):
            info = {"error": "Bildschirmfreigabe: unerwartete Antwort"}
        if "error" in info or not fds:
            for fd in fds:
                os.close(fd)
            if info.get("error") != "abgebrochen":
                self.toast.emit(info.get("error", "Bildschirmfreigabe fehlgeschlagen"))
            self.cfg["screen_token"] = ""
            self._save()
            self._stop_portal()
            self.changed.emit()
            return
        self.screen = {"type": "screen", "fd": fds[0], "node": info["node"]}
        for fd in fds[1:]:
            os.close(fd)
        if info.get("token"):
            self.cfg["screen_token"] = info["token"]
            self._save()
        self._structure()
        self.changed.emit()

    def _stop_portal(self):
        if self._portal_note:
            self._portal_note.setEnabled(False)
            self._portal_note.deleteLater()
            self._portal_note = None
        if self._portal_sock:
            self._portal_sock.close()
            self._portal_sock = None
        if self._portal:
            try:
                self._portal.stdin.close()
                self._portal.wait(2)
            except (OSError, subprocess.TimeoutExpired):
                self._portal.kill()
            self._portal = None
        if self.screen:
            try:
                os.close(self.screen["fd"])
            except OSError:
                pass
            self.screen = None

    # ---- Szenen und Quellen ------------------------------------------------------------------------
    def _scene(self):
        sc = self.cfg["scenes"]
        if not sc:
            sc.append({"name": "Szene 1", "items": []})
        self.cfg["scene"] = max(0, min(self.cfg["scene"], len(sc) - 1))
        return sc[self.cfg["scene"]]

    def _wants_screen(self):
        return any(it["kind"] == "screen" for sc in self.cfg["scenes"] for it in sc["items"])

    def _image(self, path):
        if path not in self._images:
            self._images[path] = image_png(path)
        return self._images[path]

    def _src_of(self, it):
        """Quelle fürs Mischpult zu einem Szenen-Eintrag (oder None)."""
        key = item_key(it)
        if not key:
            return None
        k = it["kind"]
        if k == "screen":
            return dict(self.screen, key=key) if self.screen else None
        if k in ("camera", "capture"):
            return {"key": key, "type": "video", "device": it["device"], "green": bool(it.get("green"))}
        if k == "image":
            img = self._image(it["file"])
            if not img:
                return None
            return {"key": key, "type": "image", "file": img[0], "w": img[1], "h": img[2]}
        if k == "test":
            return {"key": key, "type": "test", "pattern": it.get("pattern", "smpte"), "green": bool(it.get("green"))}
        return None

    def _sources(self):
        seen, out = set(), []
        for sc in self.cfg["scenes"]:
            for it in sc["items"]:
                src = self._src_of(it)
                if src and src["key"] not in seen:
                    # Grünschlüssel gilt für die Quelle: an, sobald ein Eintrag ihn will
                    seen.add(src["key"])
                    out.append(src)
                elif src and src.get("green"):
                    next(o for o in out if o["key"] == src["key"])["green"] = True
        audio = {}
        for slot, a in self.cfg["audio"].items():
            if not a["on"]:
                continue
            if slot == "extra" and not a["device"]:
                continue
            audio[slot] = {"type": "device" if slot == "extra" else slot, "device": a["device"],
                           "volume": a["volume"], "muted": a["muted"]}
        if self.selftest:
            audio = {"mic": {"type": "test", "freq": 440}, "desktop": {"type": "test", "freq": 660}}
        return out, audio

    def _layout(self):
        """Anordnung der aktiven Szene in Pixeln + Ecken: ({key: (x, y, b, h, z)}, {key: radius})."""
        W, H, _fps = engine.CANVAS.get(self.cfg["canvas"], engine.CANVAS["1080p30"])
        layout, rounds = {}, {}
        for z, it in enumerate(self._scene()["items"], start=1):
            key = item_key(it)
            if not key or it.get("hidden") or key in layout:
                continue
            layout[key] = (it["x"] * W, it["y"] * H, it["w"] * W, item_height(it) * H, z)
            rounds[key] = engine.ROUND if it.get("round") else 0.0
        return layout, rounds

    def _apply(self):
        layout, rounds = self._layout()
        self.mixer.apply_layout(layout)
        self.mixer.set_rounds(rounds)

    def _structure(self):
        """Quellen haben sich geändert: neu aufbauen – oder während Stream/Aufnahme live nachladen."""
        if self._wants_screen() != self._screen_wanted:
            self._screen_wanted = self._wants_screen()
            if self._screen_wanted and self.screen is None:
                self._start_portal()
        if self.live or self.recording:
            layout, _r = self._layout()
            sources, _a = self._sources()
            for src in sources:
                if src["key"] not in self.mixer.pads and not self.mixer.add_live(src, layout):
                    self.toast.emit("Diese Quelle lässt sich erst nach Stream oder Aufnahme einbauen.")
            self._dirty = True
            self._apply()
        else:
            self._rebuild_timer.start()
        self._save()
        self.changed.emit()

    @Slot(int)
    def setScene(self, index):
        if 0 <= index < len(self.cfg["scenes"]) and index != self.cfg["scene"]:
            self.cfg["scene"] = index
            self._apply()
            self._save_later.start()
            self.changed.emit()

    @Slot()
    def addScene(self):
        names = {sc["name"] for sc in self.cfg["scenes"]}
        n = len(self.cfg["scenes"]) + 1
        while f"Szene {n}" in names:
            n += 1
        self.cfg["scenes"].append({"name": f"Szene {n}", "items": []})
        self.cfg["scene"] = len(self.cfg["scenes"]) - 1
        self._apply()
        self._save()
        self.changed.emit()

    @Slot(int)
    def duplicateScene(self, index):
        if not 0 <= index < len(self.cfg["scenes"]):
            return
        sc = copy.deepcopy(self.cfg["scenes"][index])
        sc["name"] = sc["name"] + " (Kopie)"
        for it in sc["items"]:
            it["id"] = f"q{self.cfg['next_id']}"
            self.cfg["next_id"] += 1
        self.cfg["scenes"].insert(index + 1, sc)
        self.cfg["scene"] = index + 1
        self._apply()
        self._save()
        self.changed.emit()

    @Slot(int, str)
    def renameScene(self, index, name):
        name = name.strip()
        if 0 <= index < len(self.cfg["scenes"]) and name:
            self.cfg["scenes"][index]["name"] = name[:40]
            self._save()
            self.changed.emit()

    @Slot(int)
    def removeScene(self, index):
        sc = self.cfg["scenes"]
        if len(sc) <= 1 or not 0 <= index < len(sc):
            self.toast.emit("Eine Szene braucht Studio mindestens.")
            return
        sc.pop(index)
        if self.cfg["scene"] >= index:
            self.cfg["scene"] = max(0, self.cfg["scene"] - 1)
        self._structure()

    @Slot(str, result=int)
    def addSource(self, kind):
        """Bildschirm, Kamera oder Capture-Karte zur aktiven Szene. Rückgabe: Platz in der Liste."""
        items = self._scene()["items"]
        if kind == "screen":
            for i, it in enumerate(items):
                if it["kind"] == "screen":
                    return i
            items.insert(0, new_item(self.cfg, "screen"))
            self._structure()
            return 0
        if kind not in ("camera", "capture"):
            return -1
        used = {it.get("device") for it in items}
        devs = [d for d in self.video_list if d["id"] not in used] or self.video_list
        # Kamera: am liebsten eine echte, sonst die virtuelle; Capture-Karte: eine, die keine Kamera ist
        dev = next((d for d in devs if not d.get("virtual")), devs[0] if devs else None)
        it = new_item(self.cfg, kind, device=dev["id"] if dev else "")
        if kind == "capture":
            items.insert(0, it)
            pos = 0
        else:
            items.append(it)
            pos = len(items) - 1
        self._device_chosen(it)
        self._structure()
        return pos

    @Slot(str, result=int)
    def addImage(self, url):
        path = QUrl(url).toLocalFile() if url.startswith("file:") else url
        img = image_png(path)
        if not img:
            self.toast.emit("Dieses Bild lässt sich nicht öffnen.")
            return -1
        self._images[path] = img
        aspect = img[1] / max(1, img[2])
        # so groß wie es passt, höchstens 40 % breit bzw. 50 % hoch, mittig
        w = min(0.40, 0.50 * aspect / CANVAS_ASPECT)
        it = new_item(self.cfg, "image", file=path, aspect=aspect, w=w)
        it["x"] = (1 - w) / 2
        it["y"] = (1 - item_height(it)) / 2
        items = self._scene()["items"]
        items.append(it)
        self._structure()
        return len(items) - 1

    def _device_chosen(self, it):
        name = next((d["name"] for d in self.video_list if d["id"] == it.get("device")), "")
        if is_virtual(name):
            # Gibeon Kamera (Broadcast): grünen Hintergrund durchsichtig machen, Person freigestellt zeigen
            it["green"] = True
            it["round"] = False
            if broadcast_green():
                self.toast.emit("Broadcast zeigt jetzt einen grünen Hintergrund – Studio blendet ihn aus.")
        elif it["kind"] == "capture" and not self.cfg["audio"]["extra"]["device"]:
            match = matching_audio(it.get("device", ""), self.audio_list)
            if match:
                self.cfg["audio"]["extra"].update(on=True, device=match)

    def _item(self, index):
        items = self._scene()["items"]
        return items[index] if 0 <= index < len(items) else None

    @Slot(int, str, "QVariant")
    def setItem(self, index, field, value):
        it = self._item(index)
        if not it or field not in ("device", "round", "hidden", "green", "name"):
            return
        if field == "device":
            it["device"] = str(value)
            it["green"] = False
            if it["kind"] == "camera":
                it["round"] = True
            self._device_chosen(it)
            self._structure()
            return
        it[field] = bool(value) if field != "name" else str(value)
        if field == "green":
            self._structure() if not (self.live or self.recording) else self._apply()
            if value:
                broadcast_green()
            return
        self._apply()
        self._save_later.start()
        self.changed.emit()

    @Slot(int, float, float, float)
    def moveItem(self, index, x, y, w):
        """Verschieben / Größe ändern (Anteile der Bildbreite/-höhe) – sofort im Bild, auch live."""
        it = self._item(index)
        if not it:
            return
        it["w"] = max(0.03, min(4.0, w))
        h = item_height(it)
        it["x"] = max(-it["w"] + 0.03, min(0.97, x))
        it["y"] = max(-h + 0.03, min(0.97, y))
        self._apply()
        self._save_later.start()
        self.changed.emit()

    @Slot(int)
    def fillItem(self, index):
        """Bildfüllend einpassen (Seitenverhältnis bleibt)."""
        it = self._item(index)
        if not it:
            return
        a = it.get("aspect") or CANVAS_ASPECT
        w = 1.0 if a >= CANVAS_ASPECT else a / CANVAS_ASPECT
        self.moveItem(index, (1 - w) / 2, (1 - w * CANVAS_ASPECT / a) / 2, w)

    @Slot(int, int, result=int)
    def orderItem(self, index, delta):
        """Nach vorne (+1) oder hinten (-1). Rückgabe: neuer Platz."""
        items = self._scene()["items"]
        j = index + delta
        if not (0 <= index < len(items) and 0 <= j < len(items)):
            return index
        items[index], items[j] = items[j], items[index]
        self._apply()
        self._save_later.start()
        self.changed.emit()
        return j

    @Slot(int)
    def removeItem(self, index):
        items = self._scene()["items"]
        if 0 <= index < len(items):
            items.pop(index)
            self._structure()

    # ---- Mischpult ------------------------------------------------------------------------------
    def _rebuild(self):
        if self.live or self.recording:
            return
        self._dirty = False
        sources, audio = self._sources()
        layout, rounds = self._layout()
        try:
            self.mixer.build(self.cfg, sources, audio, layout, rounds)
            self.error = ""
        except (ValueError, RuntimeError) as e:
            self.error = f"Studio konnte die Quellen nicht starten: {e}"
        self.levels = dict(self.mixer.levels)
        self.changed.emit()

    def _on_frame(self, data, w, h):
        # GStreamer-Thread: Bild kopieren, das Signal bringt es in den Hauptthread
        HUB.push(QImage(data, w, h, w * 4, QImage.Format.Format_ARGB32).copy())

    def _poll_engine(self):
        if getattr(self, "_dirty", False) and not (self.live or self.recording) and not self.mixer.outputs:
            self._rebuild()
        for key, err, out in self.mixer.poll():
            # Grafikkarten-Kodierer klappt nicht (z. B. alle NVENC-Plätze belegt) → mit Prozessor neu
            if err and out.gpu and time.monotonic() - out.started < 6 and not out.stopping:
                try:
                    again = self.mixer.start_output(key, out.target, out.kbps, out.fmt, cpu_only=True)
                    self.encoder = again.encoder_name
                    self.toast.emit("Die Grafikkarte kodiert gerade nicht – Studio nimmt den Prozessor.")
                    continue
                except (RuntimeError, ValueError):
                    pass
            if key == "record":
                self.rec_since = 0
                if err:
                    self.toast.emit(f"Aufnahme abgebrochen: {err}")
                else:
                    self.toast.emit("Aufnahme gespeichert")
            else:
                self.live_targets = [(t, u) for t, u in self.live_targets if t != key]
                if err:
                    self.toast.emit(f"{_target_label(key)}: Stream abgebrochen – {err}")
            self.changed.emit()
        while self.mixer.errors:
            e = self.mixer.errors.pop(0)
            self.toast.emit(_nice_error(e))
        if self.levels != self.mixer.levels:
            self.levels = dict(self.mixer.levels)
            self.levelsChanged.emit()

    # ---- Aufnahme ---------------------------------------------------------------------------------
    @Slot()
    def toggleRecord(self):
        if self.recording:
            self.mixer.stop_output("record")
            self.changed.emit()
            return
        folder = user_dir("VIDEOS", "Videos") / "Studio"
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.toast.emit("Der Ordner für Aufnahmen lässt sich nicht anlegen.")
            return
        ext = "mkv" if self.cfg["format"] == "mkv" else "mp4"
        self.rec_file = str(folder / f"Studio_{time.strftime('%Y-%m-%d_%H-%M-%S')}.{ext}")
        try:
            out = self.mixer.start_output("record", self.rec_file, self.cfg["kbps"] + 4000, ext)
        except (RuntimeError, ValueError) as e:
            self.toast.emit(f"Aufnahme startet nicht: {e}")
            return
        self.encoder = out.encoder_name
        self.rec_since = time.monotonic()
        self.changed.emit()

    @Slot()
    def openRecordings(self):
        folder = Path(self.rec_file).parent if self.rec_file else user_dir("VIDEOS", "Videos") / "Studio"
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    # ---- Live -------------------------------------------------------------------------------------
    def _wanted_targets(self):
        out = []
        t = self.cfg["targets"]
        for name in ("twitch", "youtube"):
            if t[name] and self.accounts[name].connected and self.targets[name]:
                out.append((name, self.targets[name]))
        if t["custom"] and self.cfg["custom_url"].strip():
            url = self.cfg["custom_url"].strip().rstrip("/")
            key = self.cfg["custom_key"].strip()
            out.append(("custom", f"{url}/{key}" if key else url))
        return out

    @Slot()
    def toggleLive(self):
        if self.live:
            for key, _ in self.live_targets:
                self.mixer.stop_output(key)
            self.changed.emit()
            return
        targets = self._wanted_targets()
        if not targets:
            self.toast.emit("Wohin soll gestreamt werden? Melde dich bei Twitch oder YouTube an "
                            "oder trage unter „Ziele“ einen eigenen Server ein.")
            return
        started = []
        for key, url in targets:
            try:
                out = self.mixer.start_output(key, url, self.cfg["kbps"])
                self.encoder = out.encoder_name
                started.append((key, url))
            except (RuntimeError, ValueError) as e:
                self.toast.emit(f"{_target_label(key)}: {e}")
        if started:
            self.live_targets = started
            self.live_since = time.monotonic()
        self.changed.emit()

    # ---- Konten --------------------------------------------------------------------------------------
    @Slot(str)
    def login(self, name):
        a = self.accounts.get(name)
        if not a:
            return
        if not a.client_id:
            self.toast.emit("Die Anmeldung ist für diesen Dienst noch nicht eingerichtet (dienste.json).")
            return
        self.busy[name] = "Anmelden …"
        self.changed.emit()
        self._bg(lambda: a.login(lambda code, url: self._async.emit(lambda: self.loginCode.emit(name, code, url))),
                 lambda _r: self._logged_in(name), lambda m: self._login_failed(name, m))

    def _logged_in(self, name):
        self.busy.pop(name, None)
        self.loginCode.emit(name, "", "")
        self.toast.emit(f"Angemeldet bei {_target_label(name)}")
        self._load_channel(name)
        self.changed.emit()

    def _login_failed(self, name, msg):
        self.busy.pop(name, None)
        self.loginCode.emit(name, "", "")
        if msg != "abgebrochen":
            self.toast.emit(f"{_target_label(name)}: {msg}")
        self.changed.emit()

    @Slot(str)
    def cancelLogin(self, name):
        a = self.accounts.get(name)
        if a:
            a.cancel.set()

    @Slot(str)
    def logout(self, name):
        a = self.accounts.get(name)
        if a:
            a.logout()
            self.channel[name] = {}
            self.targets[name] = ""
            self.changed.emit()

    @Slot(str)
    def openUrl(self, url):
        QDesktopServices.openUrl(QUrl(url))

    def _load_channel(self, name):
        a = self.accounts[name]
        self.busy[name] = "Lädt …"

        def work():
            return a.channel(), a.stream_target()

        def done(res):
            self.busy.pop(name, None)
            self.channel[name], self.targets[name] = res
            if not res[1]:
                self.toast.emit(f"{_target_label(name)}: Kein Stream-Schlüssel gefunden – ist Livestreaming freigeschaltet?")
            self.changed.emit()

        def fail(msg):
            self.busy.pop(name, None)
            self.toast.emit(f"{_target_label(name)}: {msg}")
            self.changed.emit()

        self._bg(work, done, fail)

    @Slot(str)
    def reloadChannel(self, name):
        if self.accounts.get(name) and self.accounts[name].connected:
            self._load_channel(name)

    @Slot(str, str, str)
    def applyTitle(self, title, twitch_category_id, twitch_category):
        title = title.strip()
        if not title:
            self.toast.emit("Bitte einen Titel eingeben.")
            return
        for name, a in self.accounts.items():
            if not a.connected:
                continue
            cat = twitch_category_id if name == "twitch" else None

            def work(a=a, cat=cat):
                a.set_channel(title, cat)
                return True

            def done(_r, name=name, cat=cat):
                self.channel[name]["title"] = title
                if cat:
                    self.channel[name].update(category_id=cat, category=twitch_category)
                self.toast.emit(f"{_target_label(name)}: Titel übernommen")
                self.changed.emit()

            self._bg(work, done, lambda m, name=name: self.toast.emit(f"{_target_label(name)}: {m}"))

    @Slot(str)
    def searchCategory(self, text):
        a = self.accounts["twitch"]
        if not a.connected or len(text.strip()) < 2:
            self.categories.emit("twitch", [])
            return
        self._bg(lambda: a.search_categories(text.strip()), lambda res: self.categories.emit("twitch", res),
                 lambda _m: self.categories.emit("twitch", []))

    @Slot(str, str)
    def sendChat(self, name, text):
        text = text.strip()
        if not text:
            return
        if name == "twitch":
            self._bg(lambda: self.twitch_chat.send(text))
        elif name == "youtube":
            chat = self.channel["youtube"].get("chat")
            if not chat:
                self.toast.emit("YouTube: Der Chat ist erst offen, wenn die Übertragung bereit ist.")
                return
            self._bg(lambda: self.accounts["youtube"].send_chat(chat, text))

    # ---- Ende -----------------------------------------------------------------------------------------
    @Slot()
    def shutdown(self):
        self._poll.stop()
        for key in list(self.mixer.outputs):
            self.mixer.stop_output(key)
        deadline = time.monotonic() + 6
        while self.mixer.outputs and time.monotonic() < deadline:
            self.mixer.poll()
            time.sleep(0.05)
        self.mixer.stop()
        self._stop_portal()

    @Slot(result=bool)
    def busyOutputs(self):
        return bool(self.mixer.outputs)

    # ---- Selbsttest (beim Bauen des Systems) -------------------------------------------------------
    def run_selftest(self, out_path):
        img = QImage(320, 180, QImage.Format.Format_ARGB32)
        img.fill(QColor("#2a6fdb"))
        png = os.path.join(os.path.dirname(out_path), "studio-test.png")
        img.save(png, "PNG")
        if self.addImage(png) < 0:
            return False, "Bild lässt sich nicht einbauen"
        self.moveItem(2, 0.05, 0.05, 0.2)
        sources, audio = self._sources()
        layout, rounds = self._layout()
        self.mixer.build(self.cfg, sources, audio, layout, rounds)
        time.sleep(0.8)
        out = self.mixer.start_output("record", out_path, 2000, "mp4")
        time.sleep(2.5)
        self.mixer.stop_output("record")
        deadline = time.monotonic() + 10
        while self.mixer.outputs and time.monotonic() < deadline:
            self.mixer.poll()
            time.sleep(0.05)
        frame = self.mixer.frame()
        self.mixer.stop()
        size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
        return size > 10000 and frame is not None, f"{out.encoder_name}, {size} Byte"


def _clock(sec):
    sec = int(max(0, sec))
    return f"{sec // 3600:d}:{sec // 60 % 60:02d}:{sec % 60:02d}"


def _target_label(key):
    return {"twitch": "Twitch", "youtube": "YouTube", "custom": "Eigener Server", "record": "Aufnahme"}.get(key, key)


def _nice_error(text):
    low = text.lower()
    if low.startswith("feeder:video"):
        return ("Eine Kamera liefert gerade kein Bild – Studio versucht es weiter. "
                "Für die Gibeon Kamera muss Broadcast laufen.")
    if low.startswith("feeder:screen"):
        return "Die Bildschirmfreigabe liefert gerade kein Bild – Studio versucht es weiter."
    if "v4l2" in low or "video" in low and "device" in low:
        return "Kamera oder Capture-Karte antwortet nicht – ist sie angeschlossen oder in einem anderen Programm offen?"
    if "pulse" in low:
        return "Eine Tonquelle ist nicht verfügbar."
    if "pipewire" in low:
        return "Die Bildschirmfreigabe wurde beendet."
    return text
