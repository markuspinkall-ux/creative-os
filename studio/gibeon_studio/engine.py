"""Mischpult von Studio: Quellen → Bild und Ton → Vorschau, Aufnahme, Stream.

Aufbau
  Mischpult (läuft, solange Studio offen ist)
    Hauptbild (Bildschirm / Kamera / Capture-Karte) + Kamera-Einblendung → compositor → Vorschau
    Mikrofon, Desktop-Ton, weitere Tonquelle → je Lautstärke + Pegel → audiomixer
    Bild und Ton gehen zusätzlich an zwei appsinks („vout“, „aout“).
  Ausgänge (je eine eigene Pipeline: Aufnahme, Twitch, YouTube, eigener Server)
    appsrc → Videokodierer (Grafikkarte, wenn möglich) + AAC → MP4/MKV-Datei oder FLV → RTMP

Weil jeder Ausgang eine eigene Pipeline ist, reißt ein abgebrochener Stream weder Vorschau noch
Aufnahme mit, und das Beenden schließt Dateien sauber ab.
"""

import re
import threading
import time

from . import gst

CANVAS = {"720p30": (1280, 720, 30), "720p60": (1280, 720, 60),
          "1080p30": (1920, 1080, 30), "1080p60": (1920, 1080, 60)}
PREVIEW = (960, 540)
AUDIO_CAPS = "audio/x-raw,format=F32LE,rate=48000,channels=2,layout=interleaved"
CORNERS = ("oben-links", "oben-rechts", "unten-links", "unten-rechts")
CAM_SIZES = {"klein": 0.22, "mittel": 0.30, "gross": 0.40}
AUDIO_SLOTS = ("mic", "desktop", "extra")

# Videokodierer in dieser Reihenfolge versuchen: Grafikkarte zuerst, dann Prozessor.
VIDEO_ENCODERS = (
    ("nvh264enc", "NVIDIA NVENC"), ("nvautogpuh264enc", "NVIDIA NVENC"),
    ("vah264enc", "Grafikkarte (VA-API)"), ("vaapih264enc", "Grafikkarte (VA-API)"),
    ("x264enc", "Prozessor (x264)"), ("openh264enc", "Prozessor (OpenH264)"),
)
AUDIO_ENCODERS = ("avenc_aac", "fdkaacenc", "voaacenc", "faac")


def pick(factories):
    for f in factories:
        if gst.has(f[0] if isinstance(f, tuple) else f):
            return f
    return None


GPU_ENCODERS = {"nvh264enc", "nvautogpuh264enc", "vah264enc", "vaapih264enc"}


def video_encoder(cpu_only=False):
    return pick([f for f in VIDEO_ENCODERS if not (cpu_only and f[0] in GPU_ENCODERS)])


def configure_video_encoder(enc, factory, kbps, fps):
    gop = max(1, int(fps) * 2)                       # alle 2 Sekunden ein Schlüsselbild (Twitch/YouTube)
    if factory == "openh264enc":
        gst.set_prop(enc, "bitrate", kbps * 1000)
        gst.set_prop(enc, "gop-size", gop)
        gst.set_prop(enc, "rate-control", "bitrate")
        return
    gst.set_prop(enc, "bitrate", kbps)
    for name in ("gop-size", "key-int-max", "keyframe-period"):
        gst.set_prop(enc, name, gop)
    for name in ("rc-mode", "rate-control"):
        gst.set_prop(enc, name, "cbr")
    if factory == "x264enc":
        gst.set_prop(enc, "speed-preset", "veryfast")
        gst.set_prop(enc, "tune", "zerolatency")
    if factory in ("nvh264enc", "nvautogpuh264enc"):
        gst.set_prop(enc, "zerolatency", True)
        gst.set_prop(enc, "bframes", 0)


def _q(text):
    """Wert für eine Pipeline-Beschreibung in Anführungszeichen."""
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def video_source(src):
    """Beschreibung einer Bildquelle. src: {"type": "screen"|"video"|"test", …}"""
    t = src.get("type")
    if t == "screen" and src.get("fd") is not None:
        return (f"pipewiresrc fd={int(src['fd'])} path={int(src['node'])} always-copy=true "
                "keepalive-time=1000 do-timestamp=true")
    if t == "video" and src.get("device"):
        return f"v4l2src device={_q(src['device'])} do-timestamp=true ! decodebin"
    if t == "test":
        return f"videotestsrc is-live=true pattern={src.get('pattern', 'smpte')}"
    return None


def audio_source(slot, src):
    t = src.get("type", slot)
    if t == "test":
        return f"audiotestsrc is-live=true wave=sine freq={int(src.get('freq', 440))} volume=0.3"
    dev = src.get("device") or ""
    if t == "desktop":
        dev = dev or "@DEFAULT_MONITOR@"
    if t in ("mic", "desktop", "device"):
        return f"pulsesrc do-timestamp=true client-name=Studio" + (f" device={_q(dev)}" if dev else "")
    return None


def cam_rect(canvas_w, canvas_h, corner, size):
    w = int(canvas_w * CAM_SIZES.get(size, 0.30)) // 2 * 2
    h = (w * 9 // 16) // 2 * 2
    m = int(canvas_h * 0.035)
    x = m if "links" in corner else canvas_w - w - m
    y = m if "oben" in corner else canvas_h - h - m
    return x, y, w, h


def build_description(cfg, main_src, cam_src, audio):
    """Text-Beschreibung des Mischpults. audio: {slot: quellen-dict} (nur eingeschaltete)."""
    w, h, fps = CANVAS.get(cfg.get("canvas"), CANVAS["1080p30"])
    pw, ph = PREVIEW
    raw = f"video/x-raw,width={w},height={h},framerate={fps}/1"
    parts = [
        f"compositor name=mix background=black sink_0::zorder=0 sink_1::zorder=1 sink_2::zorder=2 "
        f"! {raw} ! tee name=vt allow-not-linked=true",
        f"vt. ! queue leaky=downstream max-size-buffers=2 max-size-bytes=0 max-size-time=0 ! videoconvert "
        f"! videoscale ! video/x-raw,format=BGRA,width={pw},height={ph} "
        f"! appsink name=preview max-buffers=1 drop=true sync=false",
        f"vt. ! queue leaky=downstream max-size-buffers=4 max-size-bytes=0 max-size-time=0 "
        f"! appsink name=vout max-buffers=4 drop=true sync=false emit-signals=true",
        f"videotestsrc is-live=true pattern=black ! {raw} ! mix.sink_0",
    ]
    desc = video_source(main_src) if main_src else None
    if desc:
        parts.append(f"{desc} ! videoconvert ! videoscale add-borders=true ! videorate "
                     f"! video/x-raw,width={w},height={h},pixel-aspect-ratio=1/1,framerate={fps}/1 "
                     f"! queue max-size-buffers=3 leaky=downstream ! mix.sink_1")
    desc = video_source(cam_src) if cam_src else None
    if desc:
        x, y, cw, ch = cam_rect(w, h, cam_src.get("corner", "unten-rechts"), cam_src.get("size", "mittel"))
        parts[0] = parts[0].replace("sink_2::zorder=2",
                                    f"sink_2::zorder=2 sink_2::xpos={x} sink_2::ypos={y} "
                                    f"sink_2::width={cw} sink_2::height={ch}")
        parts.append(f"{desc} ! videoconvert ! videoscale add-borders=true ! videorate "
                     f"! video/x-raw,width={cw},height={ch},pixel-aspect-ratio=1/1,framerate={fps}/1 "
                     f"! queue max-size-buffers=3 leaky=downstream ! mix.sink_2")
    parts += [
        f"audiomixer name=amix ! {AUDIO_CAPS} ! tee name=at allow-not-linked=true",
        f"at. ! queue leaky=downstream max-size-time=1000000000 ! appsink name=aout max-buffers=50 "
        f"drop=true sync=false emit-signals=true",
        f"audiotestsrc is-live=true wave=silence ! {AUDIO_CAPS} ! amix.",
    ]
    for slot, src in audio.items():
        d = audio_source(slot, src)
        if not d:
            continue
        vol = max(0.0, min(2.0, float(src.get("volume", 1.0))))
        parts.append(f"{d} ! audioconvert ! audioresample ! {AUDIO_CAPS} "
                     f"! volume name=vol_{slot} volume={vol:.3f} mute={'true' if src.get('muted') else 'false'} "
                     f"! level name=lvl_{slot} interval=50000000 post-messages=true "
                     f"! queue max-size-time=500000000 leaky=downstream ! amix.")
    return "  ".join(parts), (w, h, fps)


LEVEL_RE = re.compile(r"peak=\([A-Za-z]+\)[{<]([^}>]*)[}>]")


class Output:
    """Ein Ausgang (Aufnahme oder Stream) in eigener Pipeline."""

    def __init__(self, kind, target, fps, kbps, fmt="mp4", cpu_only=False):
        self.kind = kind               # "record" oder Name des Stream-Ziels
        self.kbps, self.fmt = kbps, fmt
        self.target = target           # Dateipfad oder rtmp://…
        self.started = time.monotonic()
        self.start_pts = None
        self.error = ""
        self.done = False
        self.stopping = False
        self.v_caps = self.a_caps = False
        venc = video_encoder(cpu_only)
        self.gpu = bool(venc) and venc[0] in GPU_ENCODERS
        aenc = pick(AUDIO_ENCODERS)
        if not venc or not aenc:
            raise RuntimeError("Kein passender Kodierer für Bild oder Ton gefunden.")
        self.encoder_name = venc[1]
        if kind == "record":
            if fmt == "mkv":
                mux, sink = "matroskamux name=mux", f"filesink location={_q(target)}"
            else:
                mux, sink = "mp4mux name=mux fragment-duration=2000", f"filesink location={_q(target)}"
        else:
            sinkf = "rtmp2sink" if gst.has("rtmp2sink") else "rtmpsink"
            mux, sink = "flvmux name=mux streamable=true", f"{sinkf} name=out location={_q(target)}"
        desc = (f"appsrc name=v format=time is-live=true do-timestamp=false max-bytes=0 "
                f"! queue max-size-time=3000000000 max-size-bytes=0 max-size-buffers=0 ! videoconvert "
                f"! {venc[0]} name=venc ! h264parse config-interval=-1 ! video/x-h264,stream-format=avc "
                f"! queue ! {mux} ! {sink}  "
                f"appsrc name=a format=time is-live=true do-timestamp=false max-bytes=0 "
                f"! queue max-size-time=3000000000 max-size-bytes=0 max-size-buffers=0 ! audioconvert "
                f"! audioresample ! {aenc} name=aenc ! aacparse ! queue ! mux.")
        self.pipe = gst.launch(desc)
        configure_video_encoder(gst.bin_by_name(self.pipe, b"venc"), venc[0], kbps, fps)
        gst.set_prop(gst.bin_by_name(self.pipe, b"aenc"), "bitrate", 160000)
        self.v = gst.bin_by_name(self.pipe, b"v")
        self.a = gst.bin_by_name(self.pipe, b"a")
        self.bus = gst.get_bus(self.pipe)
        self.lock = threading.Lock()
        if gst.set_state(self.pipe, gst.STATE_PLAYING) == 0:
            raise RuntimeError("Der Ausgang ließ sich nicht starten.")

    def take(self, sample, video):
        """Ein Stück (Bild oder Ton) aus dem Mischpult übernehmen – läuft im GStreamer-Thread."""
        with self.lock:
            if self.stopping or self.done:
                return
            buf = gst.sample_buffer(sample)
            pts = _pts(buf)
            if pts == gst.NONE_TIME:
                return
            if self.start_pts is None:
                if not video:
                    return                      # Startzeit am ersten Bild festmachen
                self.start_pts = pts
            if pts < self.start_pts:
                return
            src = self.v if video else self.a
            if not (self.v_caps if video else self.a_caps):
                caps = gst.sample_caps(sample)
                if not caps:
                    return
                gst.appsrc_set_caps(src, caps)
                if video:
                    self.v_caps = True
                else:
                    self.a_caps = True
            gst.appsrc_push_buffer(src, _shifted(buf, self.start_pts))

    def stop(self):
        with self.lock:
            if self.stopping:
                return
            self.stopping = True
            self.stop_at = time.monotonic()
            gst.appsrc_eos(self.v)
            gst.appsrc_eos(self.a)

    def poll(self):
        """Meldungen abholen. True, sobald der Ausgang fertig ist."""
        while True:
            m = gst.pop(self.bus)
            if not m:
                break
            typ, src, text = m
            if typ == gst.MSG_EOS:
                self.done = True
            elif typ == gst.MSG_ERROR:
                self.error = text.split(" | ")[0]
                self.done = True
        if self.stopping and not self.done and time.monotonic() - self.stop_at > 8:
            self.done = True                        # hängt fest → trotzdem beenden
        if self.done:
            self.close()
        return self.done

    def close(self):
        if self.pipe:
            gst.set_state(self.pipe, gst.STATE_NULL)
            for el in (self.v, self.a, self.bus, self.pipe):
                if el:
                    gst.object_unref(el)
            self.pipe = self.v = self.a = self.bus = None


class Mixer:
    """Das Mischpult. Wird bei geänderten Quellen neu aufgebaut (nicht während Aufnahme/Stream)."""

    def __init__(self):
        gst.init()
        self.pipe = None
        self.bus = self.preview = self.vout = self.aout = None
        self.size = CANVAS["1080p30"]
        self.levels = {}
        self.errors = []
        self.outputs = {}
        self._handlers = []
        self._lock = threading.Lock()

    # ---- Aufbau ----------------------------------------------------------------------------
    def build(self, cfg, main_src, cam_src, audio):
        if self.outputs:
            raise RuntimeError("Während Aufnahme oder Stream lassen sich die Quellen nicht tauschen.")
        self.stop()
        desc, self.size = build_description(cfg, main_src, cam_src, audio)
        try:
            self.pipe = gst.launch(desc)
        except ValueError:
            # z. B. Kamera oder Bildschirm nicht verfügbar → ohne Hauptbild/Kamera weiter
            if main_src or cam_src:
                self.errors.append("Eine Bildquelle ist gerade nicht verfügbar.")
                desc, self.size = build_description(cfg, None, None, audio)
                self.pipe = gst.launch(desc)
            else:
                raise
        self.bus = gst.get_bus(self.pipe)
        self.preview = gst.bin_by_name(self.pipe, b"preview")
        self.vout = gst.bin_by_name(self.pipe, b"vout")
        self.aout = gst.bin_by_name(self.pipe, b"aout")
        self._handlers = [(self.vout, gst.connect_new_sample(self.vout, self._on_video)),
                          (self.aout, gst.connect_new_sample(self.aout, self._on_audio))]
        self.levels = {slot: -90.0 for slot in audio}
        gst.set_state(self.pipe, gst.STATE_PLAYING)

    def stop(self):
        for out in list(self.outputs.values()):
            out.stop()
            out.close()
        self.outputs.clear()
        if self.pipe:
            for el, h in self._handlers:
                gst.signal_disconnect(el, h)
            self._handlers = []
            gst.set_state(self.pipe, gst.STATE_NULL)
            for el in (self.preview, self.vout, self.aout, self.bus, self.pipe):
                if el:
                    gst.object_unref(el)
        self.pipe = self.bus = self.preview = self.vout = self.aout = None

    # ---- Daten an die Ausgänge (GStreamer-Thread) ----------------------------------------
    def _on_video(self, sink):
        with self._lock:
            outs = list(self.outputs.values())
        if not outs:
            gst.forward_sample(sink, None, 0, True)
            return gst.FLOW_OK
        self._fan_out(sink, outs, video=True)
        return gst.FLOW_OK

    def _on_audio(self, sink):
        with self._lock:
            outs = list(self.outputs.values())
        if not outs:
            gst.forward_sample(sink, None, 0, True)
            return gst.FLOW_OK
        self._fan_out(sink, outs, video=False)
        return gst.FLOW_OK

    def _fan_out(self, sink, outs, video):
        s = gst.pull_sample_blocking(sink)
        if not s:
            return
        try:
            for out in outs:
                out.take(s, video)
        finally:
            gst.mini_unref(s)

    # ---- Ausgänge ----------------------------------------------------------------------------
    def start_output(self, key, target, kbps, fmt="mp4", cpu_only=False):
        if not self.pipe:
            raise RuntimeError("Studio ist noch nicht bereit.")
        out = Output(key, target, self.size[2], kbps, fmt, cpu_only)
        with self._lock:
            self.outputs[key] = out
        return out

    def stop_output(self, key):
        out = self.outputs.get(key)
        if out:
            out.stop()

    # ---- Einstellungen im laufenden Betrieb -------------------------------------------------
    def set_volume(self, slot, volume, muted):
        el = gst.bin_by_name(self.pipe, f"vol_{slot}".encode()) if self.pipe else None
        if el:
            gst.set_prop(el, "volume", f"{max(0.0, min(2.0, volume)):.3f}")
            gst.set_prop(el, "mute", bool(muted))
            gst.object_unref(el)

    def frame(self):
        return gst.pull_frame(self.preview) if self.preview else None

    def poll(self):
        """Meldungen verarbeiten. Liefert [(schlüssel, fehler)] beendeter Ausgänge."""
        while self.bus:
            m = gst.pop(self.bus)
            if not m:
                break
            typ, src, text = m
            if typ == gst.MSG_ELEMENT and src.startswith("lvl_"):
                mm = LEVEL_RE.search(text)
                if mm:
                    vals = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", mm.group(1))]
                    if vals:
                        self.levels[src[4:]] = max(-90.0, max(vals))
            elif typ == gst.MSG_ERROR:
                self.errors.append(f"{src}: {text.split(' | ')[0]}")
        finished = []
        for key, out in list(self.outputs.items()):
            if out.poll():
                with self._lock:
                    self.outputs.pop(key, None)
                finished.append((key, out.error, out))
        return finished


def _pts(buf):
    return gst.ctypes.cast(buf, gst.ctypes.POINTER(gst._BufferHead)).contents.pts


def _shifted(buf, start):
    out = gst.buffer_copy(buf)
    head = gst.ctypes.cast(out, gst.ctypes.POINTER(gst._BufferHead)).contents
    head.pts -= start
    if head.dts != gst.NONE_TIME:
        head.dts = head.dts - start if head.dts >= start else 0
    return out
