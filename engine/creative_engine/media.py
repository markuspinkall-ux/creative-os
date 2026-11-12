"""Videos für Splash, Seiten und Menüs: in Ogg Theora (.ogv) umwandeln – das Format, das Godot ohne
Zusatz abspielt – plus Vorschaubild, Seitenverhältnis und Länge. Nutzt ffmpeg (im Flatpak das des Systems)."""

import os
import re
import shutil
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import QApplication, QProgressDialog

from . import project as proj

VIDEO_FILTER = "Videos (*.mp4 *.mkv *.mov *.webm *.avi *.ogv *.m4v)"


def ffmpeg():
    if shutil.which("ffmpeg"):
        return ["ffmpeg"]
    if os.path.exists("/.flatpak-info") and shutil.which("flatpak-spawn"):
        return ["flatpak-spawn", "--host", "ffmpeg"]
    return None


def poster_of(rel):
    """Vorschaubild zu einem Video (liegt neben dem Video, nur für den Editor)."""
    return rel + ".jpg" if rel else ""


def _run(cmd, parent, title, total=0.0):
    """ffmpeg mit Fortschrittsanzeige laufen lassen. Rückgabe: (Erfolg, Ausgabe)."""
    proc = QProcess(parent)
    proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
    dlg = QProgressDialog(title, "Abbrechen", 0, 1000 if total > 0 else 0, parent)
    dlg.setWindowTitle("Video vorbereiten")
    dlg.setWindowModality(Qt.WindowModality.WindowModal)
    dlg.setMinimumDuration(400)
    out = []

    def read():
        text = bytes(proc.readAll()).decode("utf-8", "replace")
        out.append(text)
        m = re.findall(r"time=(\d+):(\d+):([\d.]+)", text)
        if m and total > 0:
            h, mi, se = m[-1]
            dlg.setValue(min(999, int((int(h) * 3600 + int(mi) * 60 + float(se)) / total * 1000)))
    proc.readyRead.connect(read)
    stopped = []
    dlg.canceled.connect(lambda: (stopped.append(True), proc.kill()) if proc.state() != QProcess.ProcessState.NotRunning else None)
    proc.start(cmd[0], cmd[1:])
    proc.waitForStarted(5000)
    while proc.state() != QProcess.ProcessState.NotRunning:
        QApplication.processEvents()
        proc.waitForFinished(50)
    read()
    ok = proc.exitStatus() == QProcess.ExitStatus.NormalExit and proc.exitCode() == 0 and not stopped
    dlg.canceled.disconnect()
    dlg.close()
    return ok, "".join(out)


def probe(text):
    """Seitenverhältnis und Länge aus der ffmpeg-Ausgabe lesen."""
    ratio, duration = 16 / 9, 0.0
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", text)
    if m and int(m.group(2)):
        ratio = int(m.group(1)) / int(m.group(2))
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", text)
    if m:
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return round(ratio, 4), round(duration, 2)


def import_video(folder, source, parent):
    """Video ins Projekt holen. Rückgabe: {"rel", "ratio", "duration"} oder (Fehlertext als str)."""
    cmd = ffmpeg()
    if cmd is None:
        return "Zum Umwandeln von Videos wird ffmpeg gebraucht – es ist nicht installiert."
    folder = Path(folder)
    source = Path(source)
    assets = folder / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", source.stem) or "video"
    target = assets / f"{stem}.ogv"
    n = 2
    while target.exists():
        target = assets / f"{stem}-{n}.ogv"
        n += 1
    # Länge vorab (für den Fortschritt)
    _ok, info = _run(cmd + ["-hide_banner", "-i", str(source)], parent, "Video wird gelesen …")
    ratio, duration = probe(info)
    if source.suffix.lower() == ".ogv":
        shutil.copy2(source, target)
    else:
        ok, log = _run(cmd + ["-hide_banner", "-y", "-i", str(source), "-vf", "scale='min(1920,iw)':-2",
                              "-c:v", "libtheora", "-q:v", "7", "-c:a", "libvorbis", "-q:a", "4", str(target)],
                       parent, f"„{source.name}“ wird für das Spiel umgewandelt …", duration)
        if not ok or not target.exists() or target.stat().st_size == 0:
            target.unlink(missing_ok=True)
            tail = [l for l in log.splitlines() if l.strip()][-1:] or ["unbekannter Fehler"]
            return f"Das Video ließ sich nicht umwandeln: {tail[0][:200]}"
    rel = f"assets/{target.name}"
    at = "1" if duration > 2 else "0"
    _run(cmd + ["-hide_banner", "-y", "-ss", at, "-i", str(target), "-frames:v", "1", "-vf", "scale=640:-2",
                str(folder / poster_of(rel))], parent, "Vorschaubild …")
    return {"rel": rel, "ratio": ratio, "duration": duration}


def import_image(folder, source):
    return proj.import_asset(folder, source)
