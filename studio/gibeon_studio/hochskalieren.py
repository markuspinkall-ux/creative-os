"""Aufnahme nachträglich auf 4K (3840×2160) hochskalieren – läuft als eigener Prozess im Hintergrund.

  python3 -m gibeon_studio.hochskalieren --art schnell|ki EINGANG AUSGANG
  python3 -m gibeon_studio.hochskalieren --pruefen          → „ki ja“ oder „ki nein <Grund>“

Ausgabe Zeile für Zeile: „fortschritt 42“, am Ende „fertig“ oder „fehler <Text>“.

  schnell – klassisch (Lanczos) mit ffmpeg; geht überall, schärft aber nichts nach
  ki      – KI-Upscaling (2xNomosUni, wie bei der Gibeon Kamera): Bild auf 1080p bringen, KI verdoppelt
            auf 4K. Braucht eine NVIDIA-Grafikkarte; deutlich schärfer, dauert länger als die Aufnahme.
Kodiert wird in HEVC (H.265) – bei 4K halb so groß wie H.264 – auf der Grafikkarte, wenn möglich.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

OUT_W, OUT_H = 3840, 2160
PREFIX = Path(os.environ.get("GIBEON_PREFIX") or "/usr")          # AppImage: zeigt ins AppImage
MODEL = PREFIX / "share/creative-broadcast/2xNomosUni_span_multijpg_fp16.onnx"
for _v in (PREFIX / "lib/creative-broadcast/vendor", PREFIX / "lib/creative-broadcast/gpu"):
    if _v.is_dir() and str(_v) not in sys.path:
        sys.path.insert(0, str(_v))


def say(text):
    print(text, flush=True)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate,nb_frames:format=duration", "-of", "json", path],
                         capture_output=True, text=True, timeout=60)
    data = json.loads(out.stdout or "{}")
    st = (data.get("streams") or [{}])[0]
    num, _sl, den = (st.get("r_frame_rate") or "30/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 30.0
    duration = float((data.get("format") or {}).get("duration") or 0)
    frames = int(st.get("nb_frames") or 0) or int(duration * fps)
    return {"w": int(st.get("width") or 0), "h": int(st.get("height") or 0), "fps": fps,
            "rate": st.get("r_frame_rate") or "30/1", "duration": duration, "frames": frames}


def encoders():
    try:
        out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    return {line.split()[1] for line in out.splitlines() if len(line.split()) > 1 and line.startswith(" V")}


def _candidates(ext):
    tag = ["-tag:v", "hvc1"] if ext == "mp4" else []
    yield [], "", ["-c:v", "hevc_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "20", "-b:v", "0"] + tag
    if os.path.exists("/dev/dri/renderD128"):
        yield (["-vaapi_device", "/dev/dri/renderD128"], ",format=nv12,hwupload",
               ["-c:v", "hevc_vaapi", "-qp", "22"] + tag)
    yield [], "", ["-c:v", "libx265", "-preset", "medium", "-crf", "20"] + tag
    yield [], "", ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]


def _works(pre, tail, enc):
    """ffmpeg listet z. B. NVENC auch ohne NVIDIA-Karte – also kurz ausprobieren."""
    cmd = (["ffmpeg", "-hide_banner", "-loglevel", "error"] + pre
           + ["-f", "lavfi", "-i", "color=c=gray:s=640x360:d=0.2", "-vf", "format=yuv420p" + tail]
           + enc + ["-f", "null", "-"])
    try:
        return subprocess.run(cmd, capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def encode_args(have, ext):
    """(Eingangs-Optionen, Filter-Anhang, Ausgangs-Optionen) für den besten HEVC-Kodierer, der hier läuft."""
    for pre, tail, enc in _candidates(ext):
        if enc[1] in have and _works(pre, tail, enc):
            return pre, tail, enc
    return [], "", ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]


FIT = (f"scale={OUT_W}:{OUT_H}:flags=lanczos:force_original_aspect_ratio=decrease,"
       f"pad={OUT_W}:{OUT_H}:(ow-iw)/2:(oh-ih)/2")


def schnell(src, dst, info):
    pre, tail, enc = encode_args(encoders(), Path(dst).suffix.lstrip("."))
    cmd = (["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + pre + ["-i", src, "-vf", FIT + tail]
           + enc + ["-c:a", "copy", "-progress", "pipe:1", "-nostats", dst])
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    last = -1
    for line in p.stdout:
        if line.startswith("out_time_us=") and info["duration"]:
            try:
                pct = int(min(99, int(line.split("=")[1]) / 1e6 / info["duration"] * 100))
            except ValueError:
                continue
            if pct != last:
                say(f"fortschritt {pct}")
                last = pct
    err = p.stderr.read()
    if p.wait() != 0:
        raise RuntimeError(err.strip().splitlines()[-1] if err.strip() else "ffmpeg ist abgebrochen")


def ki_available():
    if not MODEL.exists():
        return False, "KI-Modell fehlt"
    try:
        import onnxruntime as ort
    except ImportError:
        return False, "ONNX Runtime fehlt"
    if "CUDAExecutionProvider" not in ort.get_available_providers():
        return False, "nur mit NVIDIA-Grafikkarte"
    return True, ""


def ki(src, dst, info):
    ok, why = ki_available()
    if not ok:
        raise RuntimeError(f"KI-Hochskalieren geht hier nicht ({why})")
    import numpy as np
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sess = ort.InferenceSession(str(MODEL), sess_options=opts, providers=[
        ("CUDAExecutionProvider", {"cudnn_conv_algo_search": "HEURISTIC", "do_copy_in_default_stream": True})])
    inp = sess.get_inputs()[0]
    dtype = np.float16 if "float16" in inp.type else np.float32
    iw, ih = OUT_W // 2, OUT_H // 2                        # KI verdoppelt: 1080p → 4K
    pre, tail, enc = encode_args(encoders(), Path(dst).suffix.lstrip("."))
    reader = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", src, "-vf",
         f"scale={iw}:{ih}:flags=lanczos:force_original_aspect_ratio=decrease,pad={iw}:{ih}:(ow-iw)/2:(oh-ih)/2",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    writer = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + pre
        + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUT_W}x{OUT_H}", "-r", info["rate"], "-i", "-",
           "-i", src, "-map", "0:v", "-map", "1:a?"] + (["-vf", tail.lstrip(",")] if tail else [])
        + enc + ["-c:a", "copy", dst], stdin=subprocess.PIPE)
    size = iw * ih * 3
    n, last = 0, -1
    try:
        while True:
            buf = reader.stdout.read(size)
            if len(buf) < size:
                break
            x = np.frombuffer(buf, np.uint8).reshape(ih, iw, 3).transpose(2, 0, 1)[None].astype(dtype) * dtype(1 / 255)
            y = sess.run(None, {inp.name: x})[0][0]
            y = np.clip(y.transpose(1, 2, 0).astype(np.float32) * 255.0 + 0.5, 0, 255).astype(np.uint8)
            writer.stdin.write(y.tobytes())
            n += 1
            if info["frames"]:
                pct = int(min(99, n * 100 / info["frames"]))
                if pct != last:
                    say(f"fortschritt {pct}")
                    last = pct
    finally:
        writer.stdin.close()
        reader.stdout.close()
        reader.wait()
    if writer.wait() != 0:
        raise RuntimeError("Kodieren in 4K ist fehlgeschlagen")


def main(argv):
    if "--pruefen" in argv:
        ok, why = ki_available()
        say("ki ja" if ok else f"ki nein {why}")
        return 0
    try:
        art = argv[argv.index("--art") + 1]
        src, dst = [a for a in argv if not a.startswith("--") and a != art][-2:]
    except (ValueError, IndexError):
        say("fehler Aufruf: --art schnell|ki EINGANG AUSGANG")
        return 2
    try:
        info = probe(src)
        if not info["w"]:
            raise RuntimeError("Die Aufnahme lässt sich nicht lesen")
        tmp = str(Path(dst).with_name(".teil-" + Path(dst).name))
        (ki if art == "ki" else schnell)(src, tmp, info)
        os.replace(tmp, dst)
    except Exception as exc:                       # alles als Meldung an Studio
        try:
            os.unlink(str(Path(dst).with_name(".teil-" + Path(dst).name)))
        except OSError:
            pass
        say(f"fehler {exc}")
        return 1
    say("fortschritt 100")
    say("fertig")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
