"""Studio – Verbindung zwischen Oberfläche (QML), Mischpult, Bildschirmfreigabe und Konten."""

import copy
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QSocketNotifier, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QImage, QPainter
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
DEFAULTS = {
    "canvas": "1080p30",
    "kbps": 6000,
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
SOURCE_KEYS = ("canvas", "main", "cam", "audio")


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
        out.append({"id": f"/dev/{d.name}", "name": name or d.name})
    return out


def audio_inputs():
    try:
        r = subprocess.run(["pactl", "-f", "json", "list", "sources"], capture_output=True, text=True, timeout=3)
        data = json.loads(r.stdout) if r.returncode == 0 else []
    except (OSError, ValueError, subprocess.SubprocessError):
        data = []
    return [{"id": s.get("name", ""), "name": s.get("description") or s.get("name", "")}
            for s in data if s.get("name") and not s["name"].endswith(".monitor")]


class Hub(QObject):
    """Verteilt Vorschaubilder an alle Vorschau-Flächen."""
    frame = Signal(QImage)


HUB = Hub()


class Preview(QQuickPaintedItem):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._img = QImage()
        HUB.frame.connect(self._on_frame)

    def _on_frame(self, img):
        self._img = img
        self.update()

    def paint(self, painter):
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
        self._frames = QTimer(self, interval=33, timeout=self._pull_frame)
        self._poll = QTimer(self, interval=100, timeout=self._poll_engine)
        self._clock = QTimer(self, interval=1000, timeout=self.changed.emit)
        self.refreshDevices()
        self._frames.start()
        self._poll.start()
        self._clock.start()
        if selftest:
            return
        if self.cfg["main"]["type"] == "screen":
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
            "recFile": self.rec_file, "canvases": list(engine.CANVAS), "corners": list(engine.CORNERS),
            "locked": self.live or self.recording,
        }

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
            if path == "main.type":
                self._screen_wanted = value == "screen"
                if self._screen_wanted and self.screen is None:
                    self._start_portal()
                elif not self._screen_wanted:
                    self._stop_portal()
            if path == "main.device" and self.cfg["main"]["type"] == "video" and not self.cfg["audio"]["extra"]["device"]:
                match = matching_audio(value, self.audio_list)
                if match:
                    self.cfg["audio"]["extra"].update(on=True, device=match)
                    self._save()
            self._rebuild_timer.start()
        self.changed.emit()

    @Slot()
    def refreshDevices(self):
        self.video_list = video_devices()
        self.audio_list = audio_inputs()
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
        if self.cfg["main"]["type"] != "screen":
            self.cfg["main"]["type"] = "screen"
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
        self._rebuild_timer.start()
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

    # ---- Mischpult ------------------------------------------------------------------------------
    def _sources(self):
        if self.selftest:
            return ({"type": "test"}, {"type": "test", "pattern": "ball", "corner": "unten-rechts", "size": "klein"},
                    {"mic": {"type": "test", "freq": 440}, "desktop": {"type": "test", "freq": 660}})
        m = self.cfg["main"]
        main = None
        if m["type"] == "screen":
            main = self.screen
        elif m["type"] == "video" and m["device"]:
            main = {"type": "video", "device": m["device"]}
        c = self.cfg["cam"]
        cam = None
        if c["on"] and c["device"] and not (m["type"] == "video" and m["device"] == c["device"]):
            cam = {"type": "video", "device": c["device"], "corner": c["corner"], "size": c["size"]}
        audio = {}
        for slot, a in self.cfg["audio"].items():
            if not a["on"]:
                continue
            if slot == "extra" and not a["device"]:
                continue
            audio[slot] = {"type": "device" if slot == "extra" else slot, "device": a["device"],
                           "volume": a["volume"], "muted": a["muted"]}
        return main, cam, audio

    def _rebuild(self):
        if self.live or self.recording:
            return
        main, cam, audio = self._sources()
        try:
            self.mixer.build(self.cfg, main, cam, audio)
            self.error = ""
        except (ValueError, RuntimeError) as e:
            self.error = f"Studio konnte die Quellen nicht starten: {e}"
        self.levels = dict(self.mixer.levels)
        self.changed.emit()

    def _pull_frame(self):
        f = self.mixer.frame()
        if f:
            data, w, h = f
            img = QImage(data, w, h, w * 4, QImage.Format.Format_ARGB32).copy()
            HUB.frame.emit(img)

    def _poll_engine(self):
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
        self._frames.stop()
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
        main, cam, audio = self._sources()
        self.mixer.build(self.cfg, main, cam, audio)
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
    if "v4l2" in low or "video" in low and "device" in low:
        return "Kamera oder Capture-Karte antwortet nicht – ist sie angeschlossen oder in einem anderen Programm offen?"
    if "pulse" in low:
        return "Eine Tonquelle ist nicht verfügbar."
    if "pipewire" in low:
        return "Die Bildschirmfreigabe wurde beendet."
    return text
