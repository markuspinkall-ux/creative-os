"""Timeline data and FFmpeg export for Creative Cut.

Aufbau wie bei Final Cut: eine magnetische Hauptspur (Clips rutschen
zusammen), darüber eine Titelspur, darunter eine Musikspur.

Export in zwei Stufen:
  1. Jeder Clip wird einzeln gerendert (Zuschnitt, Look, Tempo, Rückwärts,
     Ken Burns, Blenden, Clip-Titel) – immer gleiche Größe und Bildrate.
  2. Abschluss: Clips mit Übergängen (xfade/acrossfade) zusammenfügen,
     Titelspur einblenden, Musik dazumischen. Ohne Übergänge, Titel und
     Musik werden die Clips nur verlustfrei aneinandergehängt.
"""

import json
import math
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# ---- Effekt-Kataloge (Schlüssel → Anzeigename) ---------------------------------------

LOOKS = {
    "": "Ohne",
    "kino": "Kino",
    "warm": "Warm",
    "kalt": "Kalt",
    "leuchtend": "Leuchtend",
    "vintage": "Vintage",
    "sw": "Schwarzweiß",
    "noir": "Noir",
}
LOOK_FILTERS = {
    "kino": "eq=contrast=1.08:saturation=0.9,colorbalance=rs=-0.04:bs=0.06:rh=0.07:bh=-0.05,vignette=PI/6",
    "warm": "colortemperature=temperature=4600,eq=saturation=1.08",
    "kalt": "colortemperature=temperature=9000",
    "leuchtend": "eq=saturation=1.35:contrast=1.06",
    "vintage": "curves=preset=vintage,vignette=PI/5",
    "sw": "hue=s=0,eq=contrast=1.12",
    "noir": "hue=s=0,eq=contrast=1.35:brightness=-0.04,vignette=PI/4",
}
TRANSITIONS = {
    "": "Harter Schnitt",
    "fade": "Überblenden",
    "fadeblack": "Schwarzblende",
    "wipeleft": "Wischen",
    "slideleft": "Schieben",
    "circleopen": "Kreis",
    "smoothleft": "Gleiten",
}
KENBURNS = {"": "Aus", "in": "Langsam heranzoomen", "out": "Langsam wegzoomen"}
SPEEDS = [25, 50, 75, 100, 150, 200, 400]          # Prozent
TITLE_STYLES = {
    "mitte": "Groß in der Mitte",
    "bauchbinde": "Bauchbinde",
    "kino": "Kino unten",
    "oben": "Oben links",
}
ZOOM = 0.15                                      # Ken Burns: 15 % Zoom über die Cliplänge
TITLE_FADE = 0.4                                  # s Ein-/Ausblenden der Titel


@dataclass(frozen=True)
class Media:
    path: str
    duration: int
    audio: bool
    video: bool = True

    @property
    def name(self):
        return Path(self.path).name


@dataclass(frozen=True)
class Clip:
    media: Media
    start: int
    end: int
    volume: int = 100
    title: str = ""
    fade_in: int = 0
    fade_out: int = 0
    brightness: int = 0
    contrast: int = 100
    saturation: int = 100
    look: str = ""
    speed: int = 100
    reverse: bool = False
    kenburns: str = ""
    transition: str = ""          # Übergang VOM vorigen Clip in diesen
    transition_ms: int = 1000

    @property
    def duration(self):
        """Länge im Quellvideo."""
        return self.end - self.start

    @property
    def length(self):
        """Länge in der Zeitleiste (nach Tempo)."""
        return max(50, round(self.duration * 100 / self.speed))


@dataclass(frozen=True)
class Title:
    text: str
    at: int                        # ms in der Zeitleiste
    duration: int = 3000
    style: str = "mitte"


@dataclass(frozen=True)
class Music:
    media: Media
    at: int = 0                    # ms in der Zeitleiste
    start: int = 0                 # ms im Musikstück
    end: int = 0
    volume: int = 80
    fade_in: int = 1000
    fade_out: int = 2000

    @property
    def duration(self):
        return self.end - self.start


# ---- Zeitleiste ------------------------------------------------------------------------

def transition_lengths(clips):
    """Tatsächliche Übergangslängen (ms) je Clip; Clip 0 hat nie einen.
    Ein Übergang ist höchstens halb so lang wie jeder der beiden Clips."""
    out = []
    for i, clip in enumerate(clips):
        if i == 0 or not clip.transition:
            out.append(0)
        else:
            out.append(max(0, min(clip.transition_ms, clips[i - 1].length // 2, clip.length // 2)))
    return out


def layout(clips):
    """Startzeiten der Clips in der Zeitleiste und Gesamtlänge (ms)."""
    starts, pos = [], 0
    for clip, t in zip(clips, transition_lengths(clips)):
        pos -= t
        starts.append(pos)
        pos += clip.length
    return starts, max(pos, 0)


# ---- Einlesen ---------------------------------------------------------------------------

def probe(path):
    file = Path(path).resolve(strict=True)
    if not file.is_file():
        raise ValueError(f"Keine reguläre Datei: {file}")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-show_streams",
         "-show_format", "-of", "json", str(file)],
        check=True, capture_output=True, text=True, timeout=10,
    )
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video = any(s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
                for s in streams)
    audio = any(s.get("codec_type") == "audio" for s in streams)
    if not video and not audio:
        raise ValueError(f"Weder Bild noch Ton: {file.name}")
    duration = float(data.get("format", {}).get("duration", 0))
    if not math.isfinite(duration) or duration < 0.05:
        raise ValueError(f"Ungültige Dauer: {file.name}")
    return Media(str(file), round(duration * 1000), audio, video)


def _int(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"Ungültiger Wert für {name}.")
    return value


def _text(value, limit=160):
    if not isinstance(value, str) or len(value) > limit or any(c in value for c in "\x00\r\n"):
        raise ValueError("Ungültiger Text im Projekt.")
    return value


def read_project(path):
    """→ (media, clips, titles, music). Liest Version 1 und 2."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") not in (1, 2):
        raise ValueError("Unbekanntes Creative-Cut-Projektformat.")
    media = {}
    for item in data["media"]:
        if (not isinstance(item["path"], str) or not Path(item["path"]).is_absolute()
                or type(item["duration"]) is not int or item["duration"] < 50
                or type(item["audio"]) is not bool or type(item.get("video", True)) is not bool):
            raise ValueError("Ungültige Mediendaten im Projekt.")
        source = Media(item["path"], item["duration"], item["audio"], item.get("video", True))
        media[source.path] = source
    clips = []
    for item in data["timeline"]:
        source = media[item["path"]]
        start, end = item["start"], item["end"]
        if (any(type(v) is not int for v in (start, end))
                or not 0 <= start < end <= source.duration or end - start < 50 or not source.video):
            raise ValueError("Ungültiger Clip in der Timeline.")
        fx = dict(
            volume=_int(item.get("volume", 100), 0, 100, "Lautstärke"),
            title=_text(item.get("title", "")),
            fade_in=_int(item.get("fade_in", 0), 0, end - start, "Einblenden"),
            fade_out=_int(item.get("fade_out", 0), 0, end - start, "Ausblenden"),
            brightness=_int(item.get("brightness", 0), -100, 100, "Helligkeit"),
            contrast=_int(item.get("contrast", 100), 50, 150, "Kontrast"),
            saturation=_int(item.get("saturation", 100), 0, 200, "Sättigung"),
            speed=_int(item.get("speed", 100), 25, 400, "Tempo"),
            transition_ms=_int(item.get("transition_ms", 1000), 100, 5000, "Übergangsdauer"),
        )
        look, kb, tr = item.get("look", ""), item.get("kenburns", ""), item.get("transition", "")
        reverse = item.get("reverse", False)
        if look not in LOOKS or kb not in KENBURNS or tr not in TRANSITIONS or type(reverse) is not bool:
            raise ValueError("Unbekannter Effekt im Projekt.")
        clip = Clip(source, start, end, look=look, kenburns=kb, transition=tr, reverse=reverse, **fx)
        if clip.fade_in + clip.fade_out > clip.length:
            raise ValueError("Ungültige Clip-Effekte im Projekt.")
        clips.append(clip)
    titles = []
    for item in data.get("titles", []):
        style = item.get("style", "mitte")
        if style not in TITLE_STYLES:
            raise ValueError("Unbekannter Titelstil im Projekt.")
        titles.append(Title(_text(item["text"]), _int(item["at"], 0, 10 ** 8, "Titelposition"),
                            _int(item.get("duration", 3000), 300, 600000, "Titeldauer"), style))
    music = []
    for item in data.get("music", []):
        source = media[item["path"]]
        if not source.audio:
            raise ValueError("Musik ohne Tonspur im Projekt.")
        start = _int(item.get("start", 0), 0, source.duration - 50, "Musikstart")
        end = _int(item.get("end", source.duration), start + 50, source.duration, "Musikende")
        music.append(Music(source, _int(item.get("at", 0), 0, 10 ** 8, "Musikposition"), start, end,
                           _int(item.get("volume", 80), 0, 100, "Musiklautstärke"),
                           _int(item.get("fade_in", 1000), 0, end - start, "Musik einblenden"),
                           _int(item.get("fade_out", 2000), 0, end - start, "Musik ausblenden")))
    return list(media.values()), clips, titles, music


def project_data(media, clips, titles, music):
    """→ JSON-fähiges Projekt (Version 2)."""
    def clip_data(clip):
        d = {k: getattr(clip, k) for k in Clip.__dataclass_fields__ if k != "media"}
        d["path"] = clip.media.path
        return d

    def music_data(m):
        d = {k: getattr(m, k) for k in Music.__dataclass_fields__ if k != "media"}
        d["path"] = m.media.path
        return d
    return {"version": 2,
            "media": [{"path": m.path, "duration": m.duration, "audio": m.audio, "video": m.video} for m in media],
            "timeline": [clip_data(c) for c in clips],
            "titles": [{"text": t.text, "at": t.at, "duration": t.duration, "style": t.style} for t in titles],
            "music": [music_data(m) for m in music]}


# ---- Stufe 1: ein Clip ---------------------------------------------------------------------

def _atempo(factor):
    parts = []
    while factor > 2.0:
        parts.append("atempo=2.0")
        factor /= 2.0
    while factor < 0.5:
        parts.append("atempo=0.5")
        factor /= 0.5
    if abs(factor - 1.0) > 1e-6:
        parts.append(f"atempo={factor:.4f}")
    return parts


def segment_args(clip, target, width, height, fps, title_file=None):
    length = clip.length / 1000
    source = clip.duration / 1000
    args = ["-hide_banner", "-nostdin", "-loglevel", "error", "-filter_threads", "1",
            "-progress", "pipe:1", "-ss", f"{clip.start / 1000:.3f}", "-t", f"{source:.3f}",
            "-protocol_whitelist", "file,pipe", "-i", clip.media.path]
    if not clip.media.audio:
        args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    video = [
        "setpts=PTS-STARTPTS",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2",
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2", "setsar=1",
    ]
    if (clip.brightness, clip.contrast, clip.saturation) != (0, 100, 100):
        video.append(f"eq=brightness={clip.brightness / 200:.3f}:"
                     f"contrast={clip.contrast / 100:.2f}:saturation={clip.saturation / 100:.2f}")
    if clip.look in LOOK_FILTERS:
        video.append(LOOK_FILTERS[clip.look])
    if clip.kenburns:
        progress = f"min(t/{source:.3f},1)"
        zoom = f"(1+{ZOOM}*{progress})" if clip.kenburns == "in" else f"(1+{ZOOM}-{ZOOM}*{progress})"
        video += [f"scale=w='trunc({width}*{zoom}/2)*2':h='trunc({height}*{zoom}/2)*2':eval=frame",
                  f"crop={width}:{height}", "setsar=1"]
    audio = [f"volume={clip.volume / 100:.2f}"]
    if clip.reverse:
        video.append("reverse")
        audio.append("areverse")
    if clip.speed != 100:
        video.append(f"setpts=PTS*{100 / clip.speed:.5f}")
        audio += _atempo(clip.speed / 100)
    video.append(f"fps={fps}")
    audio.append("apad")
    if title_file:
        # The name is generated by the renderer; the title itself stays outside the filter syntax.
        video.append(f"drawtext=textfile={title_file}:expansion=none:fontsize={height // 16}:"
                     "fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=12:"
                     "x=(w-tw)/2:y=h*0.82-th/2")
    for direction, ms, offset in (("in", clip.fade_in, 0), ("out", clip.fade_out, clip.length - clip.fade_out)):
        if ms:
            values = f"t={direction}:st={offset / 1000:.3f}:d={ms / 1000:.3f}"
            video.append(f"fade={values}")
            audio.append(f"afade={values}")
    return args + [
        "-map", "0:V:0", "-map", "0:a:0" if clip.media.audio else "1:a:0",
        "-t", f"{length:.3f}", "-vf", ",".join(video), "-af", ",".join(audio),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(target),
    ]


# ---- Stufe 2: zusammenfügen ------------------------------------------------------------------

def needs_finish(clips, titles, music):
    return bool(titles or music or any(transition_lengths(clips)))


def join_args(manifest, output):
    return ["-hide_banner", "-nostdin", "-loglevel", "error", "-f", "concat", "-safe", "1",
            "-i", str(manifest), "-c", "copy", "-movflags", "+faststart", str(output)]


def _title_filter(title, file, width, height):
    a, b = title.at / 1000, (title.at + title.duration) / 1000
    fade = min(TITLE_FADE, (b - a) / 3)
    alpha = f"if(lt(t,{a + fade:.3f}),(t-{a:.3f})/{fade:.3f},if(gt(t,{b - fade:.3f}),({b:.3f}-t)/{fade:.3f},1))"
    base = f"drawtext=textfile={file}:expansion=none:enable='between(t,{a:.3f},{b:.3f})':alpha='{alpha}'"
    style = {
        "mitte": f":fontsize={height // 9}:fontcolor=white:shadowcolor=black@0.6:shadowx=3:shadowy=3"
                 ":x=(w-tw)/2:y=(h-th)/2",
        "bauchbinde": f":fontsize={height // 20}:fontcolor=0x12151b:box=1:boxcolor=0x8fb3ff@0.95"
                      f":boxborderw={height // 60}:x=w*0.06:y=h*0.80-th",
        "kino": f":fontsize={height // 16}:fontcolor=white:shadowcolor=black@0.7:shadowx=2:shadowy=2"
                ":x=(w-tw)/2:y=h*0.88-th",
        "oben": f":fontsize={height // 24}:fontcolor=white:box=1:boxcolor=black@0.5"
                f":boxborderw={height // 90}:x=w*0.05:y=h*0.07",
    }[title.style]
    return base + style


def finish_args(segments, clips, titles, music, width, height, fps, title_files, output):
    """Ein FFmpeg-Aufruf: Übergänge, Titelspur und Musik. segments[i] gehört zu clips[i]."""
    args = ["-hide_banner", "-nostdin", "-loglevel", "error", "-progress", "pipe:1"]
    for seg in segments:
        args += ["-i", str(seg)]
    for m in music:
        args += ["-ss", f"{m.start / 1000:.3f}", "-t", f"{m.duration / 1000:.3f}",
                 "-protocol_whitelist", "file,pipe", "-i", m.media.path]
    starts, total = layout(clips)
    trans = transition_lengths(clips)
    graph = []
    for i in range(len(segments)):
        graph.append(f"[{i}:v]fps={fps},settb=AVTB,format=yuv420p,setsar=1[v{i}]")
        graph.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo[a{i}]")
    v, a = "v0", "a0"
    for i in range(1, len(segments)):
        t = trans[i] / 1000
        if t > 0:
            graph.append(f"[{v}][v{i}]xfade=transition={clips[i].transition}:duration={t:.3f}"
                         f":offset={starts[i] / 1000:.3f}[vx{i}]")
            graph.append(f"[{a}][a{i}]acrossfade=d={t:.3f}[ax{i}]")
        else:
            graph.append(f"[{v}][v{i}]concat=n=2:v=1:a=0[vx{i}]")
            graph.append(f"[{a}][a{i}]concat=n=2:v=0:a=1[ax{i}]")
        v, a = f"vx{i}", f"ax{i}"
    if titles:
        chain = ",".join(_title_filter(t, f, width, height) for t, f in zip(titles, title_files))
        graph.append(f"[{v}]{chain}[vt]")
        v = "vt"
    if music:
        mixed = [f"[{a}]"]
        for k, m in enumerate(music):
            idx = len(segments) + k
            length = m.duration / 1000
            parts = [f"volume={m.volume / 100:.2f}"]
            if m.fade_in:
                parts.append(f"afade=t=in:st=0:d={m.fade_in / 1000:.3f}")
            if m.fade_out:
                parts.append(f"afade=t=out:st={max(0, length - m.fade_out / 1000):.3f}:d={m.fade_out / 1000:.3f}")
            parts += ["aformat=sample_rates=48000:channel_layouts=stereo", f"adelay={m.at}:all=1"]
            graph.append(f"[{idx}:a]{','.join(parts)}[m{k}]")
            mixed.append(f"[m{k}]")
        graph.append(f"{''.join(mixed)}amix=inputs={len(mixed)}:duration=first:dropout_transition=0:normalize=0[am]")
        a = "am"
    return args + ["-filter_complex", ";".join(graph), "-map", f"[{v}]", "-map", f"[{a}]",
                   "-t", f"{total / 1000:.3f}",
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output)]


def thumbnail_args(media, at_ms, target, height=90):
    """Ein Vorschaubild für die Zeitleiste."""
    return ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-ss", f"{at_ms / 1000:.3f}",
            "-protocol_whitelist", "file,pipe", "-i", media.path, "-frames:v", "1",
            "-vf", f"scale=-2:{height}", "-y", str(target)]
