"""Studio – Verbindung zwischen Oberfläche (QML), Mischpult, Bildschirmfreigabe und Konten."""

import copy
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, QSocketNotifier, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices, QImage, QImageReader, QPainter
from PySide6.QtQuick import QQuickPaintedItem

from . import engine, geraete, konten, umfrage

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
        "mic": {"on": True, "device": "", "volume": 1.0, "muted": False, "listen": False},
        "desktop": {"on": True, "device": "", "volume": 1.0, "muted": False, "listen": False},
        "extra": {"on": False, "device": "", "volume": 1.0, "muted": False, "listen": False},
    },
    # Mithören (z. B. Capture-Karte über Kopfhörer): Ausgabegerät, "" = Standard-Ausgabe
    "monitor_device": "",
    "format": "mp4",
    # Qualität: Stream eigens verkleinern/drosseln, Aufnahme-Qualität, Kodierer, 4K nach der Aufnahme
    "stream_res": "gleich",          # gleich | 1080 | 936 | 720
    "stream_fps": "gleich",          # gleich | 30
    "rec_quality": "normal",         # normal | hoch | sehr-hoch
    "encoder": "auto",               # auto (Grafikkarte, wenn möglich) | cpu
    "upscale": "aus",                # aus | schnell | ki
    # Umfragen: Kanal zum Mitlesen (ohne Anmeldung), eigenes CSS, zuletzt benutzte Einstellungen
    "twitch_channel": "",
    "poll_css": umfrage.DEFAULT_CSS,
    "poll_duration": 60,
    "poll_show": 20,
    "poll_native": False,
    "targets": {"twitch": True, "youtube": True, "kick": False, "tiktok": False, "custom": False},
    "custom_url": "",
    "custom_key": "",
    # Kick und TikTok: Server-Adresse und Stream-Schlüssel aus dem jeweiligen Dashboard
    # Twitch/YouTube ohne Anmeldung: nur den Stream-Schlüssel eintragen (Server ist bekannt)
    "twitch_key": "",
    "youtube_key": "",
    "kick_url": "",
    "kick_key": "",
    "kick_channel": "",
    "tiktok_url": "",
    "tiktok_key": "",
    "screen_token": "",
    "chat_open": True,
}
SOURCE_KEYS = ("canvas", "audio")
# Standard-Server, wenn jemand nur den Stream-Schlüssel einträgt
INGEST = {"twitch": "rtmp://ingest.global-contribute.live-video.net/app",
          "youtube": "rtmp://a.rtmp.youtube.com/live2"}
KINDS = {"screen": "Bildschirm", "camera": "Kamera", "capture": "Capture-Karte", "image": "Bild",
         "browser": "Browserquelle", "umfrage": "Umfrage", "test": "Test"}


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


def stable_paths():
    """/dev/videoN → feste Kennung (/dev/v4l/by-id/…, sonst by-path). Die Nummer N kann sich nach
    Neustart oder Umstecken ändern, die Kennung nicht – so bleibt die Capture-Karte in der Szene."""
    out = {}
    for kind in ("by-path", "by-id"):          # by-id gewinnt (enthält Hersteller und Seriennummer)
        for link in sorted(Path("/dev/v4l", kind).glob("*video-index0")):
            try:
                out[os.path.realpath(link)] = str(link)
            except OSError:
                pass
    return out


def video_devices():
    """Kameras und Capture-Karten: (Gerät, Name)."""
    out = []
    stable = stable_paths()
    root = Path("/sys/class/video4linux")
    for d in sorted(root.glob("video*"), key=lambda p: int(p.name[5:]) if p.name[5:].isdigit() else 999):
        try:
            if (d / "index").read_text().strip() != "0":
                continue
            name = (d / "name").read_text().strip()
        except OSError:
            continue
        info = geraete.describe(d)
        out.append({"id": stable.get(f"/dev/{d.name}", f"/dev/{d.name}"), "node": f"/dev/{d.name}", "name": name or d.name, "virtual": is_virtual(name),
                    "capture": info["capture"], "elgato": info["elgato"]})
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
    if k == "umfrage":
        return "umfrage"
    if k == "browser":
        # gleiche Seite in gleicher Größe = eine Quelle, auch über mehrere Szenen
        return f"web:{item.get('bw', 800)}x{item.get('bh', 600)}:{item['url']}" if item.get("url") else None
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
        self._sent = 0.0

    def push(self, img):
        with self._lock:
            self._img = img
            now = time.monotonic()
            # noch nicht abgeholt? Dann nicht stauen – außer es hängt (z. B. Vorschau gab es noch nicht)
            if self._waiting and now - self._sent < 0.25:
                return
            self._waiting = True
            self._sent = now
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
    pollUpdate = Signal(str)                      # [Zustand, CSS] als JSON für die Umfrage-Einblendung

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
        self.upscale_queue = []
        self.poll = None
        self.chat_reader = None
        self._poll_timer = QTimer(self, interval=500, timeout=self._poll_tick)
        self._poll_votes_at = 0.0
        self.upscale_job = None
        self.ki_ok, self.ki_why = False, ""
        self._images = {}                         # Datei → (png, b, h)
        if selftest:
            # Selbsttest beim Bauen: Testbild, abgerundete Test-Kamera mit Grünschlüssel, ein Bild
            self.cfg["scenes"] = [{"name": "Test", "items": [
                new_item(self.cfg, "test", pattern="smpte"),
                new_item(self.cfg, "test", pattern="ball", x=0.68, y=0.665, w=0.30, round=True, green=True)]}]
        elif migrate(self.cfg):
            self._first_start = not CFG.exists()
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
        self._devwatch = QTimer(self, interval=4000, timeout=self._watch_devices)
        if not selftest:
            self._devwatch.start()
        self._clock.start()
        if selftest:
            return
        if self._wants_screen():
            self._screen_wanted = True
            self._start_portal()
        self._check_ki()
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
        kick = self.cfg["kick_channel"].strip().lstrip("@")
        acc["kick"] = {"configured": True, "connected": bool(kick), "name": kick, "title": "", "category": "",
                       "categoryId": "", "chat": f"https://kick.com/popout/{kick}/chat" if kick else "",
                       "target": bool(self.cfg["kick_url"].strip()), "busy": ""}
        return {
            "cfg": self.cfg, "videoDevices": self.video_list, "audioDevices": self.audio_list,
            "accounts": acc, "live": self.live, "recording": self.recording,
            "liveTime": _clock(now - self.live_since) if self.live else "",
            "recTime": _clock(now - self.rec_since) if self.recording else "",
            "liveTargets": [t for t, _ in self.live_targets], "encoder": self.encoder or engine.video_encoder()[1]
            if engine.video_encoder() else "kein Kodierer", "status": self.status, "error": self.error,
            "screenReady": self.screen is not None, "screenAsking": self._portal is not None and self.screen is None,
            "recFile": self.rec_file, "canvases": list(engine.CANVAS),
            "canvasHeight": engine.canvas_size(self.cfg["canvas"])[1], "canvasFps": engine.canvas_size(self.cfg["canvas"])[2],
            "heights": list(engine.HEIGHTS), "rates": list(engine.RATES),
            "recMbit": round(self._rec_kbps() / 1000), "kiOk": self.ki_ok, "kiWhy": self.ki_why,
            "upscaleJob": {k: v for k, v in self.upscale_job.items() if k != "proc"} if self.upscale_job else {},
            "upscaleQueue": len(self.upscale_queue),
            "webSources": self._web_sources(),
            "poll": self.poll.state() if self.poll else {}, "pollChannel": self._poll_channel(),
            "twitchConnected": self.accounts["twitch"].connected,
            "locked": self.live or self.recording, "outputDevices": self.output_list,
            "unsupported": getattr(self, "unsupported", []),
            "sinkDevices": [{"id": d["id"][:-len(".monitor")] if d["id"] else "", "name": d["name"]} for d in self.output_list],
            "monitorEcho": self._monitor_echo(),
            "upload": self._upload_health(),
            "scenes": [{"name": sc["name"], "count": len(sc["items"])} for sc in self.cfg["scenes"]],
            "scene": self.cfg["scene"], "items": self._items_state(),
        }

    def _items_state(self):
        names = {d["id"]: d["name"] for d in self.video_list}
        out = []
        for it in self._scene()["items"]:
            label = it.get("name") or {
                "screen": "Bildschirm", "image": Path(it.get("file") or "Bild").name,
                "browser": (QUrl(it.get("url") or "").host() or "Browserquelle"),
            }.get(it["kind"]) or names.get(it.get("device")) or KINDS.get(it["kind"], it["kind"])
            out.append({"id": it["id"], "kind": it["kind"], "label": label, "device": it.get("device", ""),
                        "x": it["x"], "y": it["y"], "w": it["w"], "h": item_height(it),
                        "round": it.get("round", False), "green": it.get("green", False),
                        "hidden": it.get("hidden", False), "ok": item_key(it) is not None,
                        "virtual": is_virtual(names.get(it.get("device"), "")),
                        "url": it.get("url", ""), "bw": it.get("bw", 800), "bh": it.get("bh", 600)})
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
            if not (keys[0] == "audio" and keys[-1] in ("volume", "muted", "listen")):
                self.toast.emit("Quellen lassen sich während Aufnahme oder Stream nicht tauschen.")
                self.changed.emit()
                return
        node[keys[-1]] = value
        self._save()
        if keys[0] == "audio" and keys[-1] == "listen" or path == "monitor_device":
            self._apply_monitors()
            self.changed.emit()
            return
        if keys[0] == "audio" and keys[-1] in ("volume", "muted"):
            a = self.cfg["audio"][keys[1]]
            self.mixer.set_volume(keys[1], a["volume"], a["muted"])
            # Lautstärke und Stumm gehören zur Szene (z. B. „Pause“: Mikrofon stumm)
            self._scene().setdefault("audio", {})[keys[1]] = {"volume": a["volume"], "muted": a["muted"]}
            self._save()
        elif keys[0] in SOURCE_KEYS:
            self._rebuild_timer.start()
        self.changed.emit()

    @Slot()
    def refreshDevices(self):
        self.video_list = video_devices()
        self.audio_list = audio_inputs()
        self.output_list = audio_outputs()
        try:
            self.unsupported = geraete.unsupported()
        except OSError:
            self.unsupported = []
        self._stable_devices()
        if getattr(self, "_first_start", False):
            self._first_start = False
            self._capture_scene()
        self.changed.emit()

    def _stable_devices(self):
        """Ältere Einträge mit /dev/videoN auf die feste Kennung umstellen."""
        by_node = {d["node"]: d["id"] for d in self.video_list}
        changed = False
        for sc in self.cfg["scenes"]:
            for it in sc["items"]:
                dev = it.get("device") or ""
                if dev in by_node and by_node[dev] != dev:
                    it["device"] = by_node[dev]
                    changed = True
        if changed:
            self._save()

    def _capture_scene(self):
        """Erster Start mit angeschlossener Capture-Karte (z. B. Elgato): gleich eine fertige Szene dafür."""
        card = next((d for d in self.video_list if d.get("elgato")), None) or \
            next((d for d in self.video_list if d.get("capture") and not d.get("virtual")), None)
        if not card or any(sc["name"] == "Capture-Karte" for sc in self.cfg["scenes"]):
            return
        it = new_item(self.cfg, "capture", device=card["id"])
        self.cfg["scenes"].append({"name": "Capture-Karte", "items": [it]})
        self._device_chosen(it)
        self._save()

    def _watch_devices(self):
        """Alle paar Sekunden: neu angesteckte Kameras/Karten erkennen (Studio verbindet sich dann
        von selbst wieder – die Szene kennt die Karte ja an ihrer festen Kennung)."""
        before = [(d["id"], d["node"]) for d in self.video_list]
        vids = video_devices()
        if [(d["id"], d["node"]) for d in vids] != before:
            self.refreshDevices()

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
            src = {"key": key, "type": "video", "device": it["device"], "green": bool(it.get("green"))}
            dev = next((d for d in self.video_list if d["id"] == it["device"]), {})
            if k == "capture" or dev.get("capture"):
                # Capture-Karten (z. B. Elgato): bestes Format fest einstellen, 1080p mit voller Bildrate
                _w, ch, cfps = engine.canvas_size(self.cfg["canvas"])
                src["mode"] = geraete.capture_mode(it["device"], fps_max=min(60, max(cfps, 30)), height=ch)
            return src
        if k == "image":
            img = self._image(it["file"])
            if not img:
                return None
            return {"key": key, "type": "image", "file": img[0], "w": img[1], "h": img[2]}
        if k == "test":
            return {"key": key, "type": "test", "pattern": it.get("pattern", "smpte"), "green": bool(it.get("green"))}
        if k in ("browser", "umfrage"):
            return {"key": key, "type": "browser", "w": it.get("bw", 800), "h": it.get("bh", 600)}
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
                           "volume": a["volume"], "muted": a["muted"], "monitorable": slot == "extra"}
        if self.selftest:
            audio = {"mic": {"type": "test", "freq": 440}, "desktop": {"type": "test", "freq": 660}}
        return out, audio

    def _layout(self):
        """Anordnung der aktiven Szene in Pixeln + Ecken: ({key: (x, y, b, h, z)}, {key: radius})."""
        W, H, _fps = engine.canvas_size(self.cfg["canvas"])
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
            self._apply_scene_audio()
            self._save_later.start()
            self.changed.emit()

    def _apply_scene_audio(self):
        """Lautstärke/Stumm, die in der Szene gespeichert sind, übernehmen."""
        for slot, a in (self._scene().get("audio") or {}).items():
            if slot in self.cfg["audio"]:
                cur = self.cfg["audio"][slot]
                cur["volume"] = float(a.get("volume", cur["volume"]))
                cur["muted"] = bool(a.get("muted", cur["muted"]))
                self.mixer.set_volume(slot, cur["volume"], cur["muted"])
        self.levelsChanged.emit()

    def _audio_snapshot(self):
        return {slot: {"volume": a["volume"], "muted": a["muted"]} for slot, a in self.cfg["audio"].items()}

    @Slot()
    def addScene(self):
        names = {sc["name"] for sc in self.cfg["scenes"]}
        n = len(self.cfg["scenes"]) + 1
        while f"Szene {n}" in names:
            n += 1
        self.cfg["scenes"].append({"name": f"Szene {n}", "items": [], "audio": self._audio_snapshot()})
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
        if kind == "browser":
            # z. B. StreamElements/Streamlabs-Alerts: oben rechts, 800×600, Adresse trägt man danach ein
            it = new_item(self.cfg, "browser", url="", bw=800, bh=600, aspect=800 / 600, w=0.32)
            it["x"], it["y"] = 1 - 0.32 - 0.02, 0.04
            items.append(it)
            self._structure()
            return len(items) - 1
        if kind not in ("camera", "capture"):
            return -1
        used = {it.get("device") for it in items}
        devs = [d for d in self.video_list if d["id"] not in used] or self.video_list
        # Kamera: am liebsten eine echte Kamera; Capture-Karte: am liebsten eine Elgato bzw. Capture-Karte
        if kind == "capture":
            dev = next((d for d in devs if d.get("elgato")), None) or next((d for d in devs if d.get("capture")), None) \
                or next((d for d in devs if not d.get("virtual")), devs[0] if devs else None)
        else:
            dev = next((d for d in devs if not d.get("virtual") and not d.get("capture")), None) \
                or next((d for d in devs if not d.get("virtual")), devs[0] if devs else None)
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
            match = matching_audio(os.path.realpath(it.get("device", "")), self.audio_list)
            if match:
                self.cfg["audio"]["extra"].update(on=True, device=match)

    def _item(self, index):
        items = self._scene()["items"]
        return items[index] if 0 <= index < len(items) else None

    @Slot(int, str, "QVariant")
    def setItem(self, index, field, value):
        it = self._item(index)
        if not it or field not in ("device", "round", "hidden", "green", "name", "url", "bw", "bh"):
            return
        if field in ("url", "bw", "bh"):
            if field == "url":
                url = str(value).strip()
                if url and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", url):
                    url = "https://" + url            # „streamelements.com/…“ → https://…
                it["url"] = url
            else:
                it[field] = max(64, min(3840, int(value or 0) // 2 * 2))
                # Seitengröße ändern: Höhe im Bild passt sich an, Breite bleibt
                it["aspect"] = it.get("bw", 800) / max(1, it.get("bh", 600))
            self._structure()
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
        self._apply_monitors()
        self.changed.emit()

    def _apply_monitors(self):
        """Mithören wie eingestellt (Kopfhörer) – läuft unabhängig von Stream und Aufnahme."""
        if self.selftest:
            return
        for slot in ("extra",):                    # nur die weitere Tonquelle (Capture-Karte) – das Mikrofon
            a = self.cfg["audio"][slot]             # würdest du doppelt hören
            want = a["listen"] and a["on"]
            mon = self.mixer.monitors.get(slot)
            if want and mon and getattr(mon, "device", None) == self.cfg["monitor_device"]:
                continue
            if not want and not mon:
                continue
            try:
                self.mixer.set_monitor(slot, want, self.cfg["monitor_device"])
                if want:
                    self.mixer.monitors[slot].device = self.cfg["monitor_device"]
            except (RuntimeError, ValueError) as e:
                self.toast.emit(str(e))

    def _upload_health(self):
        """Ampel je Stream-Ziel: [{key, label, state, backlog}]."""
        enc = self.mixer.outputs.get("live")
        if not enc or not hasattr(enc, "health"):
            return []
        return [{"key": k, "label": _target_label(k), "state": st, "backlog": round(b, 1)}
                for k, (st, b) in enc.health().items()]

    def _monitor_echo(self):
        """Hörst du die Capture-Karte über dasselbe Gerät mit, das „Desktop-Ton“ aufnimmt, landet sie
        doppelt im Stream (einmal direkt, einmal über den Desktop-Ton)."""
        a = self.cfg["audio"]
        if not (a["extra"]["listen"] and a["extra"]["on"] and a["desktop"]["on"]):
            return False
        dev = self.cfg["monitor_device"]
        desk = a["desktop"]["device"]
        return (not desk and not dev) or desk == f"{dev}.monitor"

    def _on_frame(self, data, w, h):
        # GStreamer-Thread: Bild kopieren, das Signal bringt es in den Hauptthread
        HUB.push(QImage(data, w, h, w * 4, QImage.Format.Format_ARGB32).copy())

    def _poll_engine(self):
        if getattr(self, "_dirty", False) and not (self.live or self.recording) and not self.mixer.outputs:
            self._rebuild()
        restart_live = []
        for key, err, out in self.mixer.poll():
            # Grafikkarten-Kodierer klappt nicht (z. B. alle NVENC-Plätze belegt) → mit Prozessor neu
            if err and out.gpu and time.monotonic() - out.started < 6 and out.kind == "live" and out.error:
                restart_live += [(t, u) for t, u in self.live_targets if t == key]
                continue
            if err and out.gpu and time.monotonic() - out.started < 6 and not out.stopping and key == "record":
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
                elif self.cfg["upscale"] != "aus" and engine.canvas_size(self.cfg["canvas"])[1] < 2160:
                    self.toast.emit("Aufnahme gespeichert – wird jetzt im Hintergrund auf 4K hochskaliert.")
                    self._start_upscale(out.target)
                else:
                    self.toast.emit("Aufnahme gespeichert")
            else:
                self.live_targets = [(t, u) for t, u in self.live_targets if t != key]
                if err:
                    self.toast.emit(f"{_target_label(key)}: Stream abgebrochen – {err}")
            self.changed.emit()
        if restart_live and "live" not in self.mixer.outputs:
            if self._start_live(restart_live, cpu_only=True):
                self.toast.emit("Die Grafikkarte kodiert gerade nicht – Studio nimmt den Prozessor.")
            else:
                self.live_targets = []
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
            out = self.mixer.start_output("record", self.rec_file, self._rec_kbps(), ext,
                                          cpu_only=self.cfg["encoder"] == "cpu")
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
            if not t[name]:
                continue
            if self.accounts[name].connected and self.targets[name]:
                out.append((name, self.targets[name]))          # angemeldet: Schlüssel holt Studio selbst
            elif self.cfg[f"{name}_key"].strip():
                out.append((name, f"{INGEST[name]}/{self.cfg[f'{name}_key'].strip()}"))
        for name in ("kick", "tiktok", "custom"):
            url = self.cfg[f"{name}_url"].strip().rstrip("/")
            if t[name] and url:
                key = self.cfg[f"{name}_key"].strip()
                out.append((name, f"{url}/{key}" if key else url))
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
            self.toast.emit("Wohin soll gestreamt werden? Schalte unter „Ziele“ ein Ziel ein und trage den "
                            "Stream-Schlüssel ein – oder melde dich bei Twitch bzw. YouTube an.")
            return
        self.live_since = time.monotonic()
        self._start_live(targets)
        self.changed.emit()

    def _rec_kbps(self):
        """Aufnahme-Bitrate nach Qualität, Auflösung und Bildrate (1080p30: 12 / 20 / 40 Mbit/s)."""
        w, h, fps = engine.canvas_size(self.cfg["canvas"])
        base = {"normal": 12000, "hoch": 20000, "sehr-hoch": 40000}.get(self.cfg["rec_quality"], 12000)
        return int(base * (w * h) / (1920 * 1080) * (fps / 30) ** 0.6)

    def _stream_size(self):
        """(b, h, fps) für den Stream oder None (wie die Leinwand)."""
        w, h, fps = engine.canvas_size(self.cfg["canvas"])
        if self.cfg["stream_res"].isdigit() and int(self.cfg["stream_res"]) < h:
            w, h = engine.size_for_height(int(self.cfg["stream_res"]))
        if self.cfg["stream_fps"] == "30" and fps > 30:
            fps = 30
        out = (w, h, fps)
        return None if out == engine.canvas_size(self.cfg["canvas"]) else out

    # ---- Browserquellen -----------------------------------------------------------------------------
    def _web_sources(self):
        """Alle Browserquellen aller Szenen (je Seite+Größe einmal) – die Oberfläche rendert sie."""
        seen, out = set(), []
        for sc in self.cfg["scenes"]:
            for it in sc["items"]:
                key = item_key(it) if it["kind"] in ("browser", "umfrage") else None
                if key and key not in seen:
                    seen.add(key)
                    url = QUrl.fromLocalFile(str(HERE / "umfrage.html")).toString() if key == "umfrage" else it["url"]
                    out.append({"key": key, "url": url, "w": it.get("bw", 800), "h": it.get("bh", 600),
                                "poll": key == "umfrage"})
        return out

    @Slot(str, QImage)
    def pushWeb(self, key, img):
        if img.isNull():
            return
        img = img.convertToFormat(QImage.Format.Format_ARGB32)       # nicht vormultipliziert = BGRA
        w, h = img.width(), img.height()
        data = bytes(img.constBits())[: w * h * 4] if img.bytesPerLine() == w * 4 else b"".join(
            bytes(img.constScanLine(y))[: w * 4] for y in range(h))
        self.mixer.push_web(key, data, w, h)

    # ---- Umfragen -------------------------------------------------------------------------------------
    def _poll_channel(self):
        tw = self.accounts["twitch"]
        return tw.login_name if tw.connected and tw.login_name else self.cfg["twitch_channel"].strip().lstrip("@#")

    def _poll_hint(self):
        n = len(self.poll.options) if self.poll else 0
        return "Abstimmen: " + ", ".join(str(i + 1) for i in range(n)) + " in den Chat schreiben"

    def _push_poll(self):
        st = self.poll.state(self._poll_hint()) if self.poll else {"phase": "vorbei"}
        self.pollUpdate.emit(json.dumps([st, self.cfg["poll_css"]]))

    @Slot()
    def pollRefresh(self):
        self._push_poll()

    @Slot(str, "QVariantList", int, int, bool)
    def startPoll(self, question, options, duration, show, native):
        opts = [str(o).strip() for o in options if str(o).strip()]
        if not question.strip() or len(opts) < 2:
            self.toast.emit("Bitte eine Frage und mindestens zwei Antworten eintragen.")
            return
        if self.poll and self.poll.phase() == "laeuft":
            self.toast.emit("Es läuft schon eine Umfrage.")
            return
        self.cfg.update(poll_duration=int(duration), poll_show=int(show), poll_native=bool(native))
        # Einblendung in die aktive Szene, falls sie dort noch fehlt (oben links, frei verschiebbar)
        items = self._scene()["items"]
        if not any(it["kind"] == "umfrage" for it in items):
            it = new_item(self.cfg, "umfrage", bw=600, bh=440, aspect=600 / 440, w=0.30, name="Umfrage")
            it["x"], it["y"] = 0.02, 0.05
            items.append(it)
            self._structure()
        self._save()
        self.poll = umfrage.Poll(question, opts, duration, show)
        channel = self._poll_channel()
        if channel:
            if not self.chat_reader or self.chat_reader.channel != channel.lower():
                if self.chat_reader:
                    self.chat_reader.stop()
                self.chat_reader = umfrage.ChatReader(channel, self._chat_vote)
        else:
            self.toast.emit("Trage unter „Ziele › Twitch“ deinen Kanalnamen ein – dann zählt Studio die Stimmen im Chat.")
        tw = self.accounts["twitch"]
        if tw.connected:
            poll = self.poll
            nums = " · ".join(f"{i + 1} = {o}" for i, o in enumerate(opts))
            self._bg(lambda: self.twitch_chat.send(f"📊 Umfrage: {question.strip()} – {nums} – schreib die Nummer in den Chat! ({int(duration)} s)"),
                     None, lambda m: None)
            if native:
                def done(pid, poll=poll):
                    poll.twitch_poll = pid

                def fail(_m):
                    self.toast.emit("Twitch-Umfrage geht nur für Affiliates/Partner – abgestimmt wird im Chat.")
                self._bg(lambda: tw.create_poll(question.strip(), opts, duration), done, fail)
        self._poll_timer.start()
        self._push_poll()
        self.changed.emit()

    def _chat_vote(self, user, text):
        # Hintergrund-Thread des Chat-Lesers
        if self.poll and self.poll.vote(user, text):
            self._async.emit(self._poll_changed)

    def _poll_changed(self):
        self._push_poll()
        self.changed.emit()

    def _poll_tick(self):
        p = self.poll
        if not p:
            self._poll_timer.stop()
            return
        tw = self.accounts["twitch"]
        if p.twitch_poll and not p.ended and time.monotonic() - self._poll_votes_at > 3:
            self._poll_votes_at = time.monotonic()

            def got(v, p=p):
                if len(v) == len(p.extra):
                    p.extra = v
            self._bg(lambda: tw.poll_votes(p.twitch_poll), got, lambda m: None)
        if not p.ended and p.remaining() == 0:
            self._finish_poll()
        elif p.phase() == "vorbei":
            self._poll_timer.stop()
            if self.chat_reader:
                self.chat_reader.stop()
                self.chat_reader = None
        self._push_poll()
        self.changed.emit()

    def _finish_poll(self):
        p = self.poll
        if not p or p.ended:
            return
        p.ended = time.monotonic()
        tw = self.accounts["twitch"]
        if tw.connected:
            if p.twitch_poll:
                self._bg(lambda: tw.end_poll(p.twitch_poll), None, lambda m: None)
            self._bg(lambda: self.twitch_chat.send("📊 " + p.result_text()), None, lambda m: None)
        self.toast.emit(p.result_text())

    @Slot()
    def endPoll(self):
        """Umfrage vorzeitig beenden – das Ergebnis wird wie gewohnt angezeigt."""
        self._finish_poll()
        self._push_poll()
        self.changed.emit()

    @Slot()
    def hidePoll(self):
        if self.poll:
            self._finish_poll()
            self.poll.show_result = 0
        self._push_poll()
        self.changed.emit()

    @Slot(str)
    def setPollCss(self, css):
        self.cfg["poll_css"] = css
        self._save()
        self._push_poll()

    @Slot()
    def resetPollCss(self):
        self.setPollCss(umfrage.DEFAULT_CSS)
        self.changed.emit()

    # ---- 4K nach der Aufnahme --------------------------------------------------------------------
    def _check_ki(self):
        p = QProcess(self)
        p.setProcessEnvironment(self._job_env())

        def done(*_a):
            out = bytes(p.readAllStandardOutput()).decode("utf-8", "replace").strip()
            self.ki_ok = out.startswith("ki ja")
            self.ki_why = out[len("ki nein "):] if out.startswith("ki nein") else ""
            p.deleteLater()
            self.changed.emit()
        p.finished.connect(done)
        p.start(sys.executable, ["-m", "gibeon_studio.hochskalieren", "--pruefen"])

    def _job_env(self):
        from PySide6.QtCore import QProcessEnvironment
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", str(HERE.parent))
        return env

    def _start_upscale(self, path):
        art = self.cfg["upscale"]
        if art == "ki" and not self.ki_ok:
            art = "schnell"
        src = Path(path)
        dst = src.with_name(f"{src.stem}_4K{src.suffix}")
        self.upscale_queue.append((str(src), str(dst), art))
        self._next_upscale()

    def _next_upscale(self):
        if self.upscale_job or not self.upscale_queue:
            return
        src, dst, art = self.upscale_queue.pop(0)
        p = QProcess(self)
        p.setProcessEnvironment(self._job_env())
        self.upscale_job = {"proc": p, "file": Path(dst).name, "path": dst, "pct": 0, "art": art, "error": ""}

        def read():
            for line in bytes(p.readAllStandardOutput()).decode("utf-8", "replace").splitlines():
                if line.startswith("fortschritt "):
                    try:
                        self.upscale_job["pct"] = int(line.split()[1])
                    except (ValueError, IndexError, TypeError):
                        pass
                elif line.startswith("fehler "):
                    self.upscale_job["error"] = line[7:]
            self.changed.emit()

        def done(code, _st):
            read()
            job, self.upscale_job = self.upscale_job, None
            if job.get("cancelled"):
                self.toast.emit("Hochskalieren abgebrochen.")
            elif code == 0 and not job["error"]:
                self.toast.emit(f"In 4K fertig: {job['file']}")
            else:
                self.toast.emit(f"Hochskalieren hat nicht geklappt: {job['error'] or 'unbekannter Fehler'}")
            p.deleteLater()
            self._next_upscale()
            self.changed.emit()
        p.readyReadStandardOutput.connect(read)
        p.finished.connect(done)
        # niedrige Priorität: Spiel, Stream und Aufnahme gehen vor
        p.start("nice", ["-n", "10", sys.executable, "-m", "gibeon_studio.hochskalieren", "--art", art, src, dst])
        self.changed.emit()

    @Slot()
    def cancelUpscale(self):
        self.upscale_queue.clear()
        if self.upscale_job:
            self.upscale_job["cancelled"] = True
            self.upscale_job["proc"].kill()

    def _start_live(self, targets, cpu_only=False):
        """Multistream: einmal kodieren, an alle Ziele gleichzeitig senden."""
        try:
            enc = self.mixer.start_live(dict(targets), self.cfg["kbps"], cpu_only or self.cfg["encoder"] == "cpu",
                                        self._stream_size())
        except (RuntimeError, ValueError) as e:
            self.toast.emit(f"Live startet nicht: {e}")
            return False
        self.encoder = enc.encoder_name
        self.live_targets = [(k, u) for k, u in targets if k in enc.senders]
        for key, err in enc.finished:
            self.toast.emit(f"{_target_label(key)}: {err}")
        enc.finished.clear()
        return True

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

    # ---- Fernsteuerung (Stream Deck über Deck) ------------------------------------------------------
    @Slot(str, result=str)
    def command(self, line):
        """„live“, „aufnahme“, „szene <Name oder Nummer>“, „naechste“, „stumm mic|desktop|extra“."""
        cmd, _sp, arg = line.strip().partition(" ")
        arg = arg.strip()
        if cmd == "live":
            self.toggleLive()
        elif cmd == "aufnahme":
            self.toggleRecord()
        elif cmd == "szene":
            names = [sc["name"].casefold() for sc in self.cfg["scenes"]]
            if arg.casefold() in names:
                index = names.index(arg.casefold())
            elif arg.isdigit() and 1 <= int(arg) <= len(names):
                index = int(arg) - 1
            else:
                return f"fehler Die Szene „{arg}“ gibt es in Studio nicht."
            self.setScene(index)
        elif cmd == "naechste":
            n = len(self.cfg["scenes"])
            if n:
                self.setScene((self.cfg["scene"] + 1) % n)
        elif cmd == "stumm" and arg in self.cfg["audio"]:
            self.set(f"audio.{arg}.muted", not self.cfg["audio"][arg]["muted"])
        else:
            return "fehler Unbekannter Befehl"
        return "ok"

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
        if self.chat_reader:
            self.chat_reader.stop()
        self.mixer.stop()
        for slot in list(self.mixer.monitors):
            self.mixer.set_monitor(slot, False)
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
    return {"twitch": "Twitch", "youtube": "YouTube", "kick": "Kick", "tiktok": "TikTok", "custom": "Eigener Server",
            "record": "Aufnahme"}.get(key, key)


def _nice_error(text):
    low = text.lower()
    if low.startswith("feeder:video"):
        return ("Eine Kamera liefert gerade kein Bild – Studio versucht es weiter. "
                "Für die Gibeon Kamera muss Broadcast laufen.")
    if low.startswith("feeder:screen"):
        return "Die Bildschirmfreigabe liefert gerade kein Bild – Studio versucht es weiter."
    if "v4l2" in low or "video" in low and "device" in low:
        return "Kamera oder Capture-Karte antwortet nicht – ist sie angeschlossen oder in einem anderen Programm offen?"
    if low.startswith("monitor:"):
        return "Mithören ist ausgefallen – sind die Kopfhörer noch angeschlossen?"
    if "pulse" in low:
        return "Eine Tonquelle ist nicht verfügbar."
    if "pipewire" in low:
        return "Die Bildschirmfreigabe wurde beendet."
    return text
