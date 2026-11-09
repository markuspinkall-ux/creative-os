"""Timeline data and FFmpeg export for Creative Cut."""

import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Media:
    path: str
    duration: int
    audio: bool

    @property
    def name(self):
        return Path(self.path).name


@dataclass(frozen=True)
class Clip:
    media: Media
    start: int
    end: int
    volume: int = 100

    @property
    def duration(self):
        return self.end - self.start


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
    if not any(s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
               for s in streams):
        raise ValueError(f"Keine Videospur: {file.name}")
    duration = float(data.get("format", {}).get("duration", 0))
    if not math.isfinite(duration) or duration < 0.05:
        raise ValueError(f"Ungültige Videodauer: {file.name}")
    return Media(str(file), round(duration * 1000), any(s.get("codec_type") == "audio" for s in streams))


def read_project(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Unbekanntes Creative-Cut-Projektformat.")
    media = {}
    for item in data["media"]:
        if (not isinstance(item["path"], str) or not Path(item["path"]).is_absolute()
                or type(item["duration"]) is not int or item["duration"] < 50
                or type(item["audio"]) is not bool):
            raise ValueError("Ungültige Mediendaten im Projekt.")
        source = Media(**item)
        media[source.path] = source
    clips = []
    for item in data["timeline"]:
        source = media[item["path"]]
        start, end, volume = item["start"], item["end"], item["volume"]
        if (any(type(value) is not int for value in (start, end, volume))
                or not 0 <= start < end <= source.duration or end - start < 50 or not 0 <= volume <= 100):
            raise ValueError("Ungültiger Clip in der Timeline.")
        clips.append(Clip(source, start, end, volume))
    return list(media.values()), clips


def segment_args(clip, target, width, height, fps):
    duration = f"{clip.duration / 1000:.3f}"
    args = ["-hide_banner", "-nostdin", "-loglevel", "error", "-filter_threads", "1",
            "-progress", "pipe:1", "-ss", f"{clip.start / 1000:.3f}", "-protocol_whitelist",
            "file,pipe", "-i", clip.media.path]
    if not clip.media.audio:
        args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    return args + [
        "-map", "0:V:0", "-map", "0:a:0" if clip.media.audio else "1:a:0",
        "-t", duration,
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
               f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}",
        "-af", f"volume={clip.volume / 100:.2f},apad",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(target),
    ]


def join_args(manifest, output):
    return ["-hide_banner", "-nostdin", "-loglevel", "error", "-f", "concat", "-safe", "1",
            "-i", str(manifest), "-c", "copy", "-movflags", "+faststart", str(output)]
