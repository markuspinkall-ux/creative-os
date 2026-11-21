"""Mischpult von Studio: Quellen → Bild und Ton → Vorschau, Aufnahme, Stream.

Aufbau
  Mischpult (läuft, solange Studio offen ist)
    Alle Bildquellen aller Szenen (Bildschirm, Kameras, Capture-Karten, Bilder) → compositor → Vorschau.
    Eine Szene ist nur eine Anordnung: Szenenwechsel, Verschieben und Größe ändern setzen die
    Pad-Eigenschaften des Mischpults im laufenden Betrieb – ohne Ruckler, auch während des Streams.
    Kameras laufen durch ein cairooverlay, das bei Bedarf die Ecken durchsichtig macht.
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


GST_FORMATS = {"NV12": "NV12", "YUYV": "YUY2", "UYVY": "UYVY", "YU12": "I420"}


def _rate(fps):
    """59.94 → 60000/1001, 60 → 60/1"""
    for base in (24, 30, 60, 120):
        if abs(fps - base * 1000 / 1001) < 0.02:
            return f"{base * 1000}/1001"
    return f"{int(round(fps))}/1"


def mode_caps(mode):
    """Feste Einstellung für v4l2src (Capture-Karten: z. B. 1080p60 NV12) – oder ""."""
    if not mode:
        return ""
    size = f"width={int(mode['width'])},height={int(mode['height'])},framerate={_rate(float(mode['fps']))}"
    if mode.get("format") == "MJPG":
        return f" ! image/jpeg,{size} ! jpegdec"
    fmt = GST_FORMATS.get(mode.get("format"))
    return f" ! video/x-raw,format={fmt},{size}" if fmt else ""


def video_source(src):
    """Beschreibung einer Bildquelle. src: {"type": "screen"|"video"|"test", …}"""
    t = src.get("type")
    if t == "screen" and src.get("fd") is not None:
        return (f"pipewiresrc fd={int(src['fd'])} path={int(src['node'])} always-copy=true "
                "keepalive-time=1000 do-timestamp=true")
    if t == "video" and src.get("device"):
        caps = mode_caps(src.get("mode"))
        if caps:
            return f"v4l2src device={_q(src['device'])} do-timestamp=true{caps}"
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


ROUND = 0.14            # Eckenradius im Verhältnis zur kürzeren Seite
IMAGE_MAX = 2560        # größere Bilder werden beim Laden verkleinert


def _even(v):
    return max(2, int(round(v)) // 2 * 2)


def source_branch(src, w, h, fps, n):
    """Beschreibung eines Bildzweigs bis vor das Mischpult (ohne „! mix.sink_n“) oder None.
    Kameras bekommen ein cairooverlay „round_n“ für abgerundete Ecken."""
    t = src.get("type")
    raw = f"width={w},height={h},pixel-aspect-ratio=1/1,framerate={fps}/1"
    if t == "image":
        # Studio legt jedes Bild vorher als PNG ab (beliebige Formate, passende Größe) – pngdec reicht
        f = src.get("file")
        if not f:
            return None
        iw, ih = _even(src.get("w", w)), _even(src.get("h", h))
        return (f"filesrc location={_q(f)} ! pngdec ! videoconvert n-threads=0 ! videoscale n-threads=0 "
                f"! video/x-raw,format=BGRA,width={iw},height={ih},pixel-aspect-ratio=1/1 "
                f"! imagefreeze is-live=true ! video/x-raw,framerate={fps}/1 ! queue max-size-buffers=3 leaky=downstream")
    if t not in ("screen", "video", "test") or not video_source(src):
        return None
    # Kameras, Capture-Karten und Bildschirm laufen in einer eigenen kleinen Pipeline (Feeder) und
    # kommen über appsrc ins Mischpult: hakt eine Kamera (z. B. die virtuelle, wenn gerade nichts
    # liefert), läuft das Mischpult weiter.
    return (f"appsrc name=feed_{n} is-live=true do-timestamp=true format=time block=false max-bytes=0 "
            f"caps={_q('video/x-raw,format=BGRA,' + raw)} "
            f"! queue max-size-buffers=2 leaky=downstream ! cairooverlay name=round_{n} "
            f"! queue max-size-buffers=2 leaky=downstream")


def feeder_description(src, w, h, fps):
    """Zuliefer-Pipeline einer Bildquelle bis appsink „out“ (BGRA in Mischpultgröße).
    src["green"]: grünen Hintergrund durchsichtig machen (z. B. „Gibeon Kamera“ mit Greenscreen)."""
    desc = video_source(src)
    if not desc:
        return None
    raw = f"video/x-raw,format=BGRA,width={w},height={h},pixel-aspect-ratio=1/1,framerate={fps}/1"
    chain = "videoconvert n-threads=0 ! "
    if src.get("type") in ("video", "test"):
        if src.get("green") and gst.has("alpha"):
            chain += "alpha method=green angle=24 noise-level=3 black-sensitivity=80 white-sensitivity=80 ! videoconvert n-threads=0 ! "
        if gst.has("aspectratiocrop"):
            chain += "aspectratiocrop aspect-ratio=16/9 ! "
    return (f"{desc} ! {chain}videoscale n-threads=0 add-borders=true ! videorate ! {raw} "
            f"! appsink name=out max-buffers=2 drop=true sync=false emit-signals=true")


class Feeder:
    """Eigene Pipeline je Kamera / Capture-Karte / Bildschirm. Fällt sie aus, versucht Studio es
    nach ein paar Sekunden neu – das Mischpult (und ein laufender Stream) bleibt unberührt."""

    RETRY = 4.0

    def __init__(self, key, src, appsrc, size):
        self.key, self.src, self.appsrc = key, src, appsrc
        self.size = size
        self.pipe = self.sink = self.bus = None
        self.handler = None
        self.retry_at = 0.0
        self.error = ""
        self.reported = False
        self.no_mode = False            # feste Einstellung klappt nicht → GStreamer wählen lassen
        self.start()

    def start(self):
        w, h, fps = self.size
        src = self.src
        if self.no_mode:
            src = dict(src, mode=None)
        desc = feeder_description(src, w, h, fps)
        try:
            self.pipe = gst.launch(desc)
        except (ValueError, TypeError) as e:
            self._failed(str(e))
            return
        self.sink = gst.bin_by_name(self.pipe, b"out")
        self.bus = gst.get_bus(self.pipe)
        self.handler = gst.connect_new_sample(self.sink, self._on_sample)
        if gst.set_state(self.pipe, gst.STATE_PLAYING) == 0:
            self._failed("lässt sich nicht starten")

    def _on_sample(self, sink):
        gst.relay_sample(sink, self.appsrc)
        return gst.FLOW_OK

    def _failed(self, text):
        if self.src.get("mode") and not self.no_mode:
            self.no_mode = True             # gleich nochmal ohne feste Einstellung
            self.close()
            self.retry_at = time.monotonic() + 0.5
            return
        self.close()
        self.error = text
        self.retry_at = time.monotonic() + self.RETRY

    def poll(self):
        """Meldungen abholen; Fehlertext beim ersten Ausfall, sonst None."""
        if not self.pipe:
            if self.retry_at and time.monotonic() >= self.retry_at:
                self.retry_at = 0.0
                self.start()
            return self._report()
        while self.bus:
            m = gst.pop(self.bus)
            if not m:
                break
            typ, _src, text = m
            if typ in (gst.MSG_ERROR, gst.MSG_EOS):
                self._failed(text.split(" | ")[0] if typ == gst.MSG_ERROR else "beendet")
                break
        if self.pipe:
            self.reported = False
        return self._report()

    def _report(self):
        if self.error and not self.reported:
            self.reported = True
            return self.error
        return None

    def close(self):
        if self.pipe:
            if self.handler:
                gst.signal_disconnect(self.sink, self.handler)
                self.handler = None
            gst.set_state(self.pipe, gst.STATE_NULL)
            for el in (self.sink, self.bus, self.pipe):
                if el:
                    gst.object_unref(el)
        self.pipe = self.sink = self.bus = None

    def stop(self):
        self.retry_at = 0.0
        self.close()
        if self.appsrc:
            gst.object_unref(self.appsrc)
            self.appsrc = None


def pad_props(rect, z):
    """Pad-Eigenschaften des Mischpults für ein Rechteck (x, y, b, h) – None = ausgeblendet."""
    if not rect:
        return {"alpha": 0.0}
    x, y, rw, rh = rect
    return {"xpos": int(x), "ypos": int(y), "width": _even(rw), "height": _even(rh), "zorder": int(z), "alpha": 1.0}


def build_description(cfg, sources, audio, layout=None):
    """Text-Beschreibung des Mischpults.
    sources: [{"key": …, "type": "screen"|"video"|"image"|"test", …}] – jede Quelle einmal.
    layout: {key: (x, y, b, h, z)} in Pixeln – was nicht drinsteht, ist unsichtbar.
    audio: {slot: quellen-dict} (nur eingeschaltete).
    Rückgabe: (Beschreibung, (b, h, fps), {key: padname})."""
    w, h, fps = CANVAS.get(cfg.get("canvas"), CANVAS["1080p30"])
    pw, ph = PREVIEW
    layout = layout or {}
    # Mischpult rechnet in BGRA wie alle Zulieferer – keine Umrechnung je Quelle und für die Vorschau
    raw = f"video/x-raw,format=BGRA,width={w},height={h},framerate={fps}/1"
    branches, pads, padprops = [], {}, ["sink_0::zorder=0"]
    n = 1
    for src in sources:
        d = source_branch(src, w, h, fps, n)
        if not d:
            continue
        key = src["key"]
        pads[key] = f"sink_{n}"
        L = layout.get(key)
        props = pad_props(L[:4] if L else None, L[4] if L else 0)
        padprops += [f"sink_{n}::{k}={v}" for k, v in props.items()]
        branches.append(f"{d} ! mix.sink_{n}")
        n += 1
    parts = [
        f"compositor name=mix background=black {' '.join(padprops)} "
        f"! {raw} ! tee name=vt allow-not-linked=true",
        f"vt. ! queue leaky=downstream max-size-buffers=2 max-size-bytes=0 max-size-time=0 ! videoconvert n-threads=0 "
        f"! videoscale n-threads=0 ! video/x-raw,format=BGRA,width={pw},height={ph} "
        f"! appsink name=preview max-buffers=1 drop=true sync=false emit-signals=true",
        f"vt. ! queue leaky=downstream max-size-buffers=4 max-size-bytes=0 max-size-time=0 "
        f"! appsink name=vout max-buffers=4 drop=true sync=false emit-signals=true",
        f"videotestsrc is-live=true pattern=black ! {raw} ! mix.sink_0",
    ] + branches
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
    return "  ".join(parts), (w, h, fps), pads


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
        if kind == "live":
            # Multistream: einmal kodieren, Ergebnis an alle Ziele (Sender) verteilen
            mux = sink = None
            desc = (f"appsrc name=v format=time is-live=true do-timestamp=false max-bytes=0 "
                    f"! queue max-size-time=3000000000 max-size-bytes=0 max-size-buffers=0 ! videoconvert n-threads=0 "
                    f"! {venc[0]} name=venc ! h264parse config-interval=-1 ! video/x-h264,stream-format=avc,alignment=au "
                    f"! appsink name=vo emit-signals=true sync=false max-buffers=0  "
                    f"appsrc name=a format=time is-live=true do-timestamp=false max-bytes=0 "
                    f"! queue max-size-time=3000000000 max-size-bytes=0 max-size-buffers=0 ! audioconvert "
                    f"! audioresample ! {aenc} name=aenc ! aacparse "
                    f"! appsink name=ao emit-signals=true sync=false max-buffers=0")
        elif kind == "record":
            if fmt == "mkv":
                mux, sink = "matroskamux name=mux", f"filesink location={_q(target)}"
            else:
                mux, sink = "mp4mux name=mux fragment-duration=2000", f"filesink location={_q(target)}"
        else:
            sinkf = "rtmp2sink" if gst.has("rtmp2sink") else "rtmpsink"
            mux, sink = "flvmux name=mux streamable=true", f"{sinkf} name=out location={_q(target)}"
        if mux:
            desc = (f"appsrc name=v format=time is-live=true do-timestamp=false max-bytes=0 "
                    f"! queue max-size-time=3000000000 max-size-bytes=0 max-size-buffers=0 ! videoconvert n-threads=0 "
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
        self._setup()
        if gst.set_state(self.pipe, gst.STATE_PLAYING) == 0:
            raise RuntimeError("Der Ausgang ließ sich nicht starten.")

    def _setup(self):
        pass

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


class Sender:
    """Ein Stream-Ziel beim Multistream: fertig kodiertes Bild/Ton → FLV → RTMP(S).
    Eigene Pipeline: bricht ein Ziel ab, laufen die anderen weiter."""

    def __init__(self, key, target):
        self.key, self.target = key, target
        self.error = ""
        self.done = False
        self.stopping = False
        self.caps = {True: False, False: False}
        self.lock = threading.Lock()
        if target.startswith("file://"):                     # für Tests: in eine Datei statt ins Netz
            sink = f"filesink location={_q(target[7:])}"
        else:
            sinkf = "rtmp2sink" if gst.has("rtmp2sink") else "rtmpsink"
            sink = f"{sinkf} name=out location={_q(target)}"
        # Pads ausdrücklich benennen: ohne Caps beim Aufbau wüsste flvmux sonst nicht, was Bild und was Ton ist
        desc = (f"flvmux name=mux streamable=true ! {sink}  "
                f"appsrc name=v format=time is-live=true do-timestamp=false max-bytes=0 "
                f"! queue max-size-time=3000000000 max-size-bytes=0 max-size-buffers=0 ! mux.video  "
                f"appsrc name=a format=time is-live=true do-timestamp=false max-bytes=0 "
                f"! queue max-size-time=3000000000 max-size-bytes=0 max-size-buffers=0 ! mux.audio")
        self.pipe = gst.launch(desc)
        self.v = gst.bin_by_name(self.pipe, b"v")
        self.a = gst.bin_by_name(self.pipe, b"a")
        self.bus = gst.get_bus(self.pipe)
        if gst.set_state(self.pipe, gst.STATE_PLAYING) == 0:
            self.close()
            raise RuntimeError("Das Ziel ließ sich nicht starten.")

    def push(self, sample, video):
        with self.lock:
            if self.done or self.stopping or not self.pipe:
                return
            src = self.v if video else self.a
            if not self.caps[video]:
                caps = gst.sample_caps(sample)
                if not caps:
                    return
                gst.appsrc_set_caps(src, caps)
                self.caps[video] = True
            gst.appsrc_push_buffer(src, gst.buffer_copy(gst.sample_buffer(sample)))

    def finish(self):
        with self.lock:
            if self.stopping or not self.pipe:
                return
            self.stopping = True
            self.stop_at = time.monotonic()
            gst.appsrc_eos(self.v)
            gst.appsrc_eos(self.a)

    def poll(self):
        while self.bus and not self.done:
            m = gst.pop(self.bus)
            if not m:
                break
            typ, _src, text = m
            if typ == gst.MSG_EOS:
                self.done = True
            elif typ == gst.MSG_ERROR:
                self.error = text.split(" | ")[0]
                self.done = True
        if self.stopping and not self.done and time.monotonic() - self.stop_at > 8:
            self.done = True
        if self.done:
            self.close()
        return self.done

    def close(self):
        with self.lock:
            if self.pipe:
                gst.set_state(self.pipe, gst.STATE_NULL)
                for el in (self.v, self.a, self.bus, self.pipe):
                    if el:
                        gst.object_unref(el)
                self.pipe = self.v = self.a = self.bus = None


class LiveEncoder(Output):
    """Multistream: Mischpult → ein Kodierer → alle Ziele (Twitch, YouTube, Kick, TikTok, eigener Server).
    Spart bei mehreren Zielen viel Leistung; jedes Ziel hat trotzdem seine eigene Pipeline."""

    def __init__(self, targets, fps, kbps, cpu_only=False):
        self.senders = {}
        self.finished = []
        self._pending = dict(targets)
        super().__init__("live", "", fps, kbps, "flv", cpu_only)

    def _setup(self):
        for key, url in self._pending.items():
            try:
                self.senders[key] = Sender(key, url)
            except (RuntimeError, ValueError) as e:
                self.finished.append((key, str(e)))
        if not self.senders:
            raise RuntimeError(self.finished[0][1] if self.finished else "Kein Ziel")
        self.vo = gst.bin_by_name(self.pipe, b"vo")
        self.ao = gst.bin_by_name(self.pipe, b"ao")
        self._h = [(self.vo, gst.connect_new_sample(self.vo, lambda s: self._out(s, True))),
                   (self.ao, gst.connect_new_sample(self.ao, lambda s: self._out(s, False)))]

    def _out(self, sink, video):
        s = gst.pull_sample_blocking(sink)
        if s:
            try:
                for snd in list(self.senders.values()):
                    snd.push(s, video)
            finally:
                gst.mini_unref(s)
        return gst.FLOW_OK

    def stop_target(self, key):
        snd = self.senders.get(key)
        if snd:
            snd.finish()

    def poll(self):
        """True, sobald alles beendet ist. Beendete Ziele landen in self.finished."""
        while self.bus and not self.done:
            m = gst.pop(self.bus)
            if not m:
                break
            typ, _src, text = m
            if typ == gst.MSG_EOS:
                self.done = True
            elif typ == gst.MSG_ERROR:
                self.error = text.split(" | ")[0]
                self.done = True
        if self.done:
            for snd in self.senders.values():
                snd.finish()
        for key, snd in list(self.senders.items()):
            if snd.poll():
                self.finished.append((key, snd.error or (self.error if self.done else "")))
                del self.senders[key]
        if not self.senders and not self.stopping:
            self.stop()                                  # letztes Ziel weg → Kodierer beenden
        if self.stopping and not self.done and time.monotonic() - self.stop_at > 8:
            self.done = True
        if self.done and not self.senders:
            for el, h in getattr(self, "_h", []):
                gst.signal_disconnect(el, h)
                gst.object_unref(el)
            self._h = []
            self.close()
            return True
        return False


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
        self.pads = {}                  # Quelle → Pad-Name am Mischpult
        self.feeders = {}               # Quelle → Feeder (Kameras, Bildschirm)
        self.on_frame = None            # fn(bytes, b, h) – jedes Vorschaubild, sobald es fertig ist
        self.last_frame = None
        self.rounds = {}                # Pad-Name → Eckenradius (Anteil), 0 = eckig
        self._overlays = []
        self._handlers = []
        self._lock = threading.Lock()

    # ---- Aufbau ----------------------------------------------------------------------------
    def build(self, cfg, sources, audio, layout=None, rounds=None):
        if self.outputs:
            raise RuntimeError("Während Aufnahme oder Stream lassen sich die Quellen nicht tauschen.")
        self.stop()
        self.cfg = cfg
        desc, self.size, pads = build_description(cfg, sources, audio, layout)
        try:
            self.pipe = gst.launch(desc)
        except ValueError:
            # z. B. Kamera, Bild oder Bildschirm nicht verfügbar → einzeln prüfen, Kaputtes weglassen
            if not sources:
                raise
            good = [s for s in sources if self._branch_ok(s)]
            self.errors.append("Eine Bildquelle ist gerade nicht verfügbar.")
            desc, self.size, pads = build_description(cfg, good, audio, layout)
            self.pipe = gst.launch(desc)
        self.pads = pads
        self.bus = gst.get_bus(self.pipe)
        self.preview = gst.bin_by_name(self.pipe, b"preview")
        self.vout = gst.bin_by_name(self.pipe, b"vout")
        self.aout = gst.bin_by_name(self.pipe, b"aout")
        self._handlers = [(self.vout, gst.connect_new_sample(self.vout, self._on_video)),
                          (self.aout, gst.connect_new_sample(self.aout, self._on_audio)),
                          (self.preview, gst.connect_new_sample(self.preview, self._on_preview))]
        self.rounds = {}
        for key, pad in pads.items():
            self._hook_round(pad)
        by_key = {s["key"]: s for s in sources}
        for key, pad in pads.items():
            feed = gst.bin_by_name(self.pipe, f"feed_{pad[5:]}".encode())
            if feed:
                self.feeders[key] = Feeder(key, by_key[key], feed, self.size)
        self.set_rounds(rounds or {})
        self.levels = {slot: -90.0 for slot in audio}
        gst.set_state(self.pipe, gst.STATE_PLAYING)

    def _branch_ok(self, src):
        w, h, fps = CANVAS.get(self.cfg.get("canvas"), CANVAS["1080p30"])
        d = source_branch(src, w, h, fps, 1)
        if not d:
            return False
        try:
            el = gst.launch(d.replace("name=round_1", "") + " ! fakesink")
        except ValueError:
            return False
        ok = gst.set_state(el, gst.STATE_PAUSED) != 0
        gst.set_state(el, gst.STATE_NULL)
        gst.object_unref(el)
        return ok

    def _hook_round(self, pad):
        el = gst.bin_by_name(self.pipe, f"round_{pad[5:]}".encode())
        if not el:
            return
        w, h = self.size[0], self.size[1]

        def draw(cr, pad=pad):
            r = self.rounds.get(pad, 0.0)
            if r > 0:
                gst.clear_corners(cr, w, h, r * min(w, h))
        self._overlays.append((el, gst.connect_draw(el, draw)))

    # ---- Anordnung im laufenden Betrieb (Szenen, Verschieben, Größe) ------------------------
    def apply_layout(self, layout):
        """layout: {key: (x, y, b, h, z)} – alles andere wird ausgeblendet."""
        if not self.pipe:
            return
        mix = gst.bin_by_name(self.pipe, b"mix")
        if not mix:
            return
        try:
            for key, pad_name in self.pads.items():
                pad = gst.static_pad(mix, pad_name.encode())
                if not pad:
                    continue
                L = layout.get(key)
                for k, v in pad_props(L[:4] if L else None, L[4] if L else 0).items():
                    gst.set_prop(pad, k, v)
                gst.object_unref(pad)
        finally:
            gst.object_unref(mix)

    def set_rounds(self, rounds):
        """rounds: {key: anteil} – Ecken der Kameras."""
        self.rounds = {self.pads[k]: float(v) for k, v in rounds.items() if k in self.pads}

    def add_live(self, src, layout=None):
        """Neue Bildquelle in das laufende Mischpult hängen (z. B. Bild während des Streams)."""
        if not self.pipe or src["key"] in self.pads:
            return False
        w, h, fps = self.size
        n = 100 + len(self.pads)
        d = source_branch(src, w, h, fps, n)
        if not d:
            return False
        try:
            branch = gst.make_bin(d)
        except ValueError:
            return False
        mix = gst.bin_by_name(self.pipe, b"mix")
        pad = gst.request_pad(mix, b"sink_%u")
        L = (layout or {}).get(src["key"])
        for k, v in pad_props(L[:4] if L else None, L[4] if L else 0).items():
            gst.set_prop(pad, k, v)
        gst.bin_add(self.pipe, branch)
        out = gst.static_pad(branch, b"src")
        ok = gst.pad_link(out, pad) == 0
        gst.object_unref(out)
        name = gst.pad_name(pad)
        gst.object_unref(pad)
        gst.object_unref(mix)
        if not ok:
            gst.bin_remove(self.pipe, branch)
            return False
        self.pads[src["key"]] = name
        feed = gst.bin_by_name(branch, f"feed_{n}".encode())
        if feed:
            self.feeders[src["key"]] = Feeder(src["key"], src, feed, self.size)
        el = gst.bin_by_name(branch, f"round_{n}".encode())
        if el:
            wv, hv = w, h

            def draw(cr, pad=name):
                r = self.rounds.get(pad, 0.0)
                if r > 0:
                    gst.clear_corners(cr, wv, hv, r * min(wv, hv))
            self._overlays.append((el, gst.connect_draw(el, draw)))
        gst.sync_state(branch)
        return True

    def stop(self):
        for out in list(self.outputs.values()):
            out.stop()
            out.close()
        self.outputs.clear()
        if self.pipe:
            for el, h in self._handlers:
                gst.signal_disconnect(el, h)
            self._handlers = []
            for f in self.feeders.values():
                f.stop()
            self.feeders = {}
            for el, h in self._overlays:
                gst.signal_disconnect(el, h)
                gst.object_unref(el)
            self._overlays = []
            self.pads = {}
            gst.set_state(self.pipe, gst.STATE_NULL)
            for el in (self.preview, self.vout, self.aout, self.bus, self.pipe):
                if el:
                    gst.object_unref(el)
        self.pipe = self.bus = self.preview = self.vout = self.aout = None
        self.last_frame = None

    # ---- Daten an die Ausgänge (GStreamer-Thread) ----------------------------------------
    def _on_video(self, sink):
        with self._lock:
            outs = list(self.outputs.values())
        if not outs:
            gst.forward_sample(sink, None, 0, True)
            return gst.FLOW_OK
        self._fan_out(sink, outs, video=True)
        return gst.FLOW_OK

    def _on_preview(self, sink):
        # Vorschau im Takt der Bilder (statt mit einem Zeitgeber abholen) – läuft gleichmäßig
        f = gst.pull_frame(sink, blocking=True)
        if f:
            self.last_frame = f
            if self.on_frame:
                self.on_frame(*f)
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
        elif "live" in self.outputs and key in self.outputs["live"].senders:
            self.outputs["live"].stop_target(key)

    def start_live(self, targets, kbps, cpu_only=False):
        """Multistream an alle Ziele {schlüssel: adresse}. Rückgabe: der Kodierer."""
        if not self.pipe:
            raise RuntimeError("Studio ist noch nicht bereit.")
        enc = LiveEncoder(targets, self.size[2], kbps, cpu_only)
        with self._lock:
            self.outputs["live"] = enc
        return enc

    # ---- Einstellungen im laufenden Betrieb -------------------------------------------------
    def set_volume(self, slot, volume, muted):
        el = gst.bin_by_name(self.pipe, f"vol_{slot}".encode()) if self.pipe else None
        if el:
            gst.set_prop(el, "volume", f"{max(0.0, min(2.0, volume)):.3f}")
            gst.set_prop(el, "mute", bool(muted))
            gst.object_unref(el)

    def frame(self):
        return self.last_frame if self.pipe else None

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
        for key, f in list(self.feeders.items()):
            err = f.poll()
            if err:
                self.errors.append(f"feeder:{f.src.get('type')}: {err}")
        finished = []
        for key, out in list(self.outputs.items()):
            done = out.poll()
            if isinstance(out, LiveEncoder):
                # beim Multistream meldet jedes Ziel einzeln
                while out.finished:
                    target, err = out.finished.pop(0)
                    finished.append((target, err, out))
                if done:
                    with self._lock:
                        self.outputs.pop(key, None)
                continue
            if done:
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
