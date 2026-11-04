"""creative-broadcastd – rauschfreies Mikrofon und virtueller Greenscreen.

Läuft in der Sitzung im Hintergrund und tut nichts, solange beides aus ist.

Mikrofon: PipeWire-Filter mit DeepFilterNet (KI-Rauschentfernung, CPU, sehr
sparsam) → neue Eingabe „Creative Mikrofon (rauschfrei)“, wird Standard.
Ohne DeepFilterNet: WebRTC-Rauschunterdrückung von PipeWire als Ersatz.

Kamera: echte Kamera → Robust Video Matting (KI-Freistellung) → Hintergrund
unscharf / Bild / Grün → virtuelle Kamera „Creative Kamera“ (v4l2loopback).
Gerechnet wird nur, solange ein Programm die Creative Kamera benutzt (oder die
Vorschau offen ist); sonst wird die echte Kamera freigegeben.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

LADSPA = [Path("/usr/lib64/ladspa/libdeep_filter_ladspa.so"), Path("/usr/lib/ladspa/libdeep_filter_ladspa.so")]
MODEL = Path("/usr/share/creative-broadcast/rvm_mobilenetv3_fp32.onnx")
VOICE_NODE = "creative_voice"
DEFAULTS = {"voice": False, "voiceStrength": 70, "realMic": "", "camera": False, "cameraDevice": "",
            "effect": "blur", "background": "", "quality": "sparsam"}

for _v in (Path("/usr/lib/creative-broadcast/vendor"), Path("/usr/lib/creative-broadcast/gpu")):
    if _v.is_dir() and str(_v) not in sys.path:
        sys.path.insert(0, str(_v))


def config_file():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "creative-os" / "broadcast.json"


def runtime_dir():
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    d = Path(base) / "creative-broadcast"
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    return d


def load_config():
    cfg = dict(DEFAULTS)
    try:
        data = json.loads(config_file().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            cfg.update({k: v for k, v in data.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    p = config_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def ladspa_plugin():
    return next((p for p in LADSPA if p.exists()), None)


def loopback_device():
    """/dev/videoN der virtuellen „Creative Kamera“."""
    for d in sorted(Path("/sys/class/video4linux").glob("video*")):
        try:
            if "Creative Kamera" in (d / "name").read_text():
                return f"/dev/{d.name}"
        except OSError:
            pass
    return ""


def list_cameras():
    """Echte Kameras (ohne die virtuelle)."""
    out = []
    for d in sorted(Path("/sys/class/video4linux").glob("video*"), key=lambda p: int(p.name[5:] or 0)):
        try:
            name = (d / "name").read_text().strip()
            index = int((d / "index").read_text().strip() or 0)
        except (OSError, ValueError):
            continue
        # virtuelle Kameras (unsere und die für OBS) sind keine echten Kameras
        if "Creative Kamera" in name or "OBS" in name or "Virtuelle" in name or index != 0:
            continue
        out.append({"device": f"/dev/{d.name}", "name": name})
    return out


class Status:
    def __init__(self):
        self.data = {"voice": "aus", "camera": "aus", "fps": 0, "engine": ""}
        self._lock = threading.Lock()

    def set(self, **kw):
        with self._lock:
            if all(self.data.get(k) == v for k, v in kw.items()):
                return
            self.data.update(kw)
            try:
                f = runtime_dir() / "status.json"
                f.with_suffix(".tmp").write_text(json.dumps(self.data, ensure_ascii=False))
                f.with_suffix(".tmp").replace(f)
            except OSError:
                pass


STATUS = Status()


# ---- Mikrofon ---------------------------------------------------------------------------------
class Voice:
    def __init__(self):
        self.proc = None
        self.key = None

    def _pactl(self, *args):
        try:
            return subprocess.run(["pactl", *args], capture_output=True, text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    def _conf(self, real_mic, strength):
        plugin = ladspa_plugin()
        target = f'target.object = "{real_mic}"' if real_mic else ""
        if plugin:
            # Stärke 0–100 → Dämpfungsgrenze 6–100 dB (100 = so viel wie möglich)
            limit = round(6 + 94 * max(0, min(100, strength)) / 100)
            module = f"""
{{ name = libpipewire-module-filter-chain
  args = {{
    node.description = "Creative Mikrofon (rauschfrei)"
    media.name = "Creative Mikrofon (rauschfrei)"
    filter.graph = {{
      nodes = [
        {{ type = ladspa name = deepfilter plugin = "{plugin}" label = deep_filter_mono
          control = {{ "Attenuation Limit (dB)" = {limit} }} }}
      ]
    }}
    audio.rate = 48000
    audio.position = [ MONO ]
    capture.props = {{ node.name = "creative_voice_in" node.passive = true {target} }}
    playback.props = {{ node.name = "{VOICE_NODE}" media.class = Audio/Source }}
  }}
}}"""
            engine = "DeepFilterNet"
        else:
            module = f"""
{{ name = libpipewire-module-echo-cancel
  args = {{
    library.name = aec/libspa-aec-webrtc
    aec.args = {{ webrtc.noise_suppression = true webrtc.gain_control = true webrtc.extended_filter = false }}
    capture.props = {{ node.name = "creative_voice_in" {target} }}
    source.props = {{ node.name = "{VOICE_NODE}" node.description = "Creative Mikrofon (rauschfrei)" }}
    sink.props = {{ node.name = "creative_voice_ref" node.description = "Creative Echo-Referenz" }}
  }}
}}"""
            engine = "WebRTC"
        text = f"""context.properties = {{ log.level = 0 }}
context.spa-libs = {{ audio.convert.* = audioconvert/libspa-audioconvert support.* = support/libspa-support }}
context.modules = [
  {{ name = libpipewire-module-rt args = {{ nice.level = -11 }} flags = [ ifexists nofail ] }}
  {{ name = libpipewire-module-protocol-native }}
  {{ name = libpipewire-module-client-node }}
  {{ name = libpipewire-module-adapter }}
  {module}
]
"""
        path = runtime_dir() / "voice.conf"
        path.write_text(text, encoding="utf-8")
        return str(path), engine

    def apply(self, cfg):
        want = bool(cfg["voice"])
        if not want:
            self.stop(cfg)
            return
        real = cfg.get("realMic") or ""
        current = self._pactl("get-default-source")
        if not real or real == VOICE_NODE:
            real = current if current and current != VOICE_NODE else ""
            if real:
                cfg["realMic"] = real
                save_config(cfg)
        key = (real, cfg["voiceStrength"])
        if self.proc and self.proc.poll() is None and key == self.key:
            return
        self.stop(cfg, restore=False)
        conf, engine = self._conf(real, cfg["voiceStrength"])
        try:
            self.proc = subprocess.Popen(["pipewire", "-c", conf], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            STATUS.set(voice="fehlt")
            return
        self.key = key
        # Neue Eingabe zum Standard machen (sobald sie da ist)
        for _ in range(30):
            time.sleep(0.2)
            if VOICE_NODE in self._pactl("list", "short", "sources"):
                self._pactl("set-default-source", VOICE_NODE)
                break
        STATUS.set(voice="aktiv", engine=engine)

    def stop(self, cfg=None, restore=True):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None
            self.key = None
            if restore and cfg and cfg.get("realMic"):
                self._pactl("set-default-source", cfg["realMic"])
        STATUS.set(voice="aus")


# ---- Kamera ---------------------------------------------------------------------------------------
def _consumers(dev, own_pids):
    """Wie viele andere Programme haben die Creative Kamera geöffnet?"""
    try:
        target = os.path.realpath(dev)
    except OSError:
        return 0
    n = 0
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) in own_pids:
            continue
        fd_dir = f"/proc/{pid}/fd"
        try:
            for fd in os.listdir(fd_dir):
                try:
                    if os.readlink(f"{fd_dir}/{fd}") == target:
                        n += 1
                        break
                except OSError:
                    pass
        except OSError:
            pass
    return n


class Matting:
    """Robust Video Matting über ONNX Runtime (CPU, mit NVIDIA ggf. CUDA)."""

    def __init__(self, quality):
        import numpy as np
        import onnxruntime as ort
        self.np = np
        if hasattr(ort, "preload_dlls") and Path("/usr/lib/creative-broadcast/gpu").is_dir():
            try:
                ort.preload_dlls(directory="", msvc=False)
            except Exception as exc:
                print(f"Creative Broadcast: CUDA-Bibliotheken nicht geladen: {exc}", file=sys.stderr)
        opts = ort.SessionOptions()
        threads = max(1, min(4, (os.cpu_count() or 2) // 2))
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        providers = [p for p in ("CUDAExecutionProvider", "ROCMExecutionProvider") if p in ort.get_available_providers()]
        providers.append("CPUExecutionProvider")
        self.sess = ort.InferenceSession(str(MODEL), sess_options=opts, providers=providers)
        # Tatsächlich registrierte Provider melden, nicht nur angeforderte.
        self.engine = self.sess.get_providers()[0].replace("ExecutionProvider", "")
        self.outputs = [output.name for output in self.sess.get_outputs()][1:]
        print(f"Creative Broadcast: KI-Backend {self.engine}", file=sys.stderr)
        self.size = (640, 360) if quality == "sparsam" else (1280, 720)
        self.ratio = np.array([0.375 if quality == "sparsam" else 0.25], dtype=np.float32)
        self.rec = [np.zeros((1, 1, 1, 1), dtype=np.float32)] * 4

    def alpha(self, frame_bgr):
        import cv2
        np = self.np
        h, w = frame_bgr.shape[:2]
        small = cv2.resize(frame_bgr, self.size, interpolation=cv2.INTER_AREA)
        src = small[:, :, ::-1].astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        out = self.sess.run(self.outputs, {"src": src, "r1i": self.rec[0], "r2i": self.rec[1], "r3i": self.rec[2],
                                   "r4i": self.rec[3], "downsample_ratio": self.ratio})
        pha = out[0][0, 0]
        self.rec = out[1:5]
        if (pha.shape[1], pha.shape[0]) != (w, h):
            pha = cv2.resize(pha, (w, h), interpolation=cv2.INTER_LINEAR)
        return pha


class Camera:
    W, H, FPS = 1280, 720, 30

    def __init__(self):
        self.thread = None
        self.stop_flag = threading.Event()
        self.key = None

    def apply(self, cfg):
        want = bool(cfg["camera"])
        key = (cfg["cameraDevice"], cfg["quality"])
        if not want:
            self.stop()
            return
        if self.thread and self.thread.is_alive() and key == self.key:
            return
        self.stop()
        self.key = key
        self.stop_flag.clear()
        self.thread = threading.Thread(target=self._run, args=(dict(cfg),), daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_flag.set()
        if self.thread:
            self.thread.join(timeout=5)
        self.thread = None
        STATUS.set(camera="aus", fps=0)

    def _run(self, cfg):
        try:
            import cv2
            import numpy as np
        except ImportError:
            STATUS.set(camera="fehlt: OpenCV")
            return
        dev = loopback_device()
        if not dev:
            STATUS.set(camera="fehlt: virtuelle Kamera (Neustart nötig?)")
            return
        if not MODEL.exists():
            STATUS.set(camera="fehlt: KI-Modell")
            return
        try:
            matting = Matting(cfg["quality"])
        except Exception as exc:
            STATUS.set(camera=f"fehlt: KI ({exc.__class__.__name__})")
            return
        STATUS.set(engine=matting.engine)
        ff = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
                               "-s", f"{self.W}x{self.H}", "-r", str(self.FPS), "-i", "-",
                               "-f", "v4l2", "-pix_fmt", "yuv420p", dev], stdin=subprocess.PIPE)
        own = {os.getpid(), ff.pid}
        cap = None
        idle = self._idle_frame(np, cv2)
        bg_cache = {}
        last_check, consumers = 0.0, 0
        t_frames, n_frames = time.monotonic(), 0
        prev_alpha = None
        last_preview = 0.0
        try:
            while not self.stop_flag.is_set():
                now = time.monotonic()
                if now - last_check > 2:
                    preview = (runtime_dir() / "preview-wanted").exists() and \
                        time.time() - (runtime_dir() / "preview-wanted").stat().st_mtime < 4
                    consumers = _consumers(dev, own) + (1 if preview else 0)
                    last_check = now
                    cfg.update({k: v for k, v in load_config().items() if k in ("effect", "background")})
                if consumers == 0:
                    # Niemand schaut zu: echte Kamera freigeben, kaum Last
                    if cap is not None:
                        cap.release()
                        cap = None
                        prev_alpha = None
                    STATUS.set(camera="bereit (wird gerade nicht benutzt)", fps=0)
                    ff.stdin.write(idle.tobytes())
                    ff.stdin.flush()
                    time.sleep(0.5)
                    continue
                if cap is None:
                    cap = self._open(cv2, cfg["cameraDevice"])
                    if cap is None:
                        STATUS.set(camera="keine Kamera gefunden", fps=0)
                        ff.stdin.write(idle.tobytes())
                        time.sleep(1)
                        continue
                capture_start = time.monotonic()
                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(0.05)
                    continue
                if frame.shape[1] != self.W or frame.shape[0] != self.H:
                    frame = cv2.resize(frame, (self.W, self.H))
                capture_ms = (time.monotonic() - capture_start) * 1000
                processing_start = time.monotonic()
                effect = cfg.get("effect", "blur")
                if effect == "none":
                    out = frame
                else:
                    a = matting.alpha(frame)
                    if prev_alpha is not None:          # ruhigere Kanten
                        a = 0.75 * a + 0.25 * prev_alpha
                    prev_alpha = a
                    bg = self._background(np, cv2, frame, effect, cfg.get("background", ""), bg_cache)
                    a3 = a[:, :, None]
                    out = (frame.astype(np.float32) * a3 + bg.astype(np.float32) * (1 - a3)).astype(np.uint8)
                processing_ms = (time.monotonic() - processing_start) * 1000
                output_start = time.monotonic()
                ff.stdin.write(out.tobytes())
                output_ms = (time.monotonic() - output_start) * 1000
                n_frames += 1
                if (runtime_dir() / "preview-wanted").exists() and time.monotonic() - last_preview >= 1 / self.FPS:
                    if cv2.imwrite(str(runtime_dir() / "preview.tmp.jpg"), cv2.resize(out, (640, 360)),
                                   [cv2.IMWRITE_JPEG_QUALITY, 80]):
                        os.replace(runtime_dir() / "preview.tmp.jpg", runtime_dir() / "preview.jpg")
                        last_preview = time.monotonic()
                measured_at = time.monotonic()
                if measured_at - t_frames >= 2:
                    STATUS.set(camera="aktiv", fps=round(n_frames / (measured_at - t_frames)),
                               captureMs=round(capture_ms, 1), processingMs=round(processing_ms, 1),
                               outputMs=round(output_ms, 1))
                    t_frames, n_frames = measured_at, 0
        except (BrokenPipeError, OSError) as exc:
            STATUS.set(camera=f"Fehler: {exc.__class__.__name__}")
        finally:
            if cap is not None:
                cap.release()
            try:
                ff.stdin.close()
            except OSError:
                pass
            ff.terminate()

    def _open(self, cv2, device):
        devices = [device] if device else [c["device"] for c in list_cameras()]
        for d in devices:
            cap = cv2.VideoCapture(d, cv2.CAP_V4L2)
            if not cap.isOpened():
                continue
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.W)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.H)
            cap.set(cv2.CAP_PROP_FPS, self.FPS)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return cap
        return None

    def _idle_frame(self, np, cv2):
        # schlichte Graphit-Fläche, ohne Schrift (sieht in Discord, Teams & Co. neutral aus)
        return np.full((self.H, self.W, 3), (34, 27, 21), dtype=np.uint8)     # Graphit (BGR)

    def _background(self, np, cv2, frame, effect, path, cache):
        if effect == "green":
            return np.full_like(frame, (0, 255, 0))
        if effect == "replace" and path:
            if cache.get("path") != path:
                img = cv2.imread(path)
                if img is not None:
                    h, w = img.shape[:2]
                    s = max(self.W / w, self.H / h)
                    img = cv2.resize(img, (int(w * s + 1), int(h * s + 1)))
                    y = (img.shape[0] - self.H) // 2
                    x = (img.shape[1] - self.W) // 2
                    cache.update(path=path, img=img[y:y + self.H, x:x + self.W])
                else:
                    cache.update(path=path, img=None)
            if cache.get("img") is not None:
                return cache["img"]
        # Unschärfe: klein rechnen, weichzeichnen, wieder groß – sparsam und weich
        small = cv2.resize(frame, (self.W // 8, self.H // 8), interpolation=cv2.INTER_AREA)
        small = cv2.GaussianBlur(small, (0, 0), 3)
        return cv2.resize(small, (self.W, self.H), interpolation=cv2.INTER_LINEAR)


# ---- Hauptschleife ---------------------------------------------------------------------------------------
def selftest():
    print("Creative Broadcast: DeepFilterNet", "da" if ladspa_plugin() else "FEHLT (Ersatz: WebRTC)")
    try:
        import numpy as np
        import cv2  # noqa: F401
        m = Matting("sparsam")
        a = m.alpha(np.zeros((720, 1280, 3), dtype=np.uint8))
        print(f"Creative Broadcast: KI-Freistellung ok ({m.engine}, {a.shape[1]}×{a.shape[0]})")
    except Exception as exc:
        print(f"Creative Broadcast: KI-Freistellung FEHLT ({exc})")
    return 0


def main():
    if "--selftest" in sys.argv:
        return selftest()
    voice, camera = Voice(), Camera()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    last = None
    while not stop.is_set():
        try:
            mtime = config_file().stat().st_mtime
        except OSError:
            mtime = 0
        if mtime != last:
            last = mtime
            cfg = load_config()
            threading.Thread(target=voice.apply, args=(cfg,), daemon=True).start()
            camera.apply(cfg)
        elif voice.proc is not None and voice.proc.poll() is not None:
            voice.proc = None              # Filter abgestürzt → beim nächsten Durchlauf neu
            last = None
        stop.wait(1.0)
    camera.stop()
    voice.stop(load_config())
    return 0


if __name__ == "__main__":
    sys.exit(main())
