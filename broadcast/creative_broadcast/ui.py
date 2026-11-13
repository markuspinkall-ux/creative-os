"""Bedienung von Creative Broadcast (die Arbeit macht creative-broadcastd)."""

import json
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot

from . import daemon


class Broadcast(QObject):
    changed = Signal()
    statusChanged = Signal()
    previewChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cfg = daemon.load_config()
        self._status = {}
        self._cameras = daemon.list_cameras()
        try:
            from . import upscale
            self._up_reason = upscale.available()[1]
        except Exception as exc:
            self._up_reason = exc.__class__.__name__
        self._microphones = []
        self._preview_rev = 0
        self._preview_on = False
        self._preview_stamp = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(33)
        self._preview_timer.timeout.connect(self._update_preview)
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._ensure_daemon()
        self.refreshMicrophones()

    def _ensure_daemon(self):
        """Läuft der Hintergrunddienst nicht (z. B. frisch installiert), starten."""
        try:
            r = subprocess.run(["pgrep", "-u", str(__import__("os").getuid()), "-f", "creative_broadcast.daemon"],
                               capture_output=True, timeout=3)
            if r.returncode != 0:
                subprocess.Popen(["creative-broadcastd"], start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            pass

    @Slot()
    def refreshMicrophones(self):
        self._microphones = daemon.list_microphones()
        self.changed.emit()

    @Slot(str)
    def setVoiceInput(self, source):
        if any(mic["id"] == source for mic in self._microphones):
            self._set(voiceInput=source)

    def _tick(self):
        try:
            st = json.loads((daemon.runtime_dir() / "status.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            st = {}
        if st != self._status:
            self._status = st
            self.statusChanged.emit()
        if self._preview_on:
            flag = daemon.runtime_dir() / "preview-wanted"
            try:
                flag.touch()
            except OSError:
                pass
    def _update_preview(self):
        if not self._preview_on:
            return
        try:
            st = (daemon.runtime_dir() / "preview.jpg").stat()
        except OSError:
            return
        stamp = (st.st_ino, st.st_mtime_ns, st.st_size)
        if stamp != self._preview_stamp:
            self._preview_stamp = stamp
            self._preview_rev += 1
            self.previewChanged.emit()

    def _set(self, **kw):
        self._cfg.update(kw)
        daemon.save_config(self._cfg)
        self.changed.emit()

    @Slot(bool)
    def setVoice(self, on):
        self._set(voice=bool(on))

    @Slot(int)
    def setStrength(self, v):
        self._set(voiceStrength=int(v))

    @Slot(bool)
    def setCamera(self, on):
        self._set(camera=bool(on))

    @Slot(str)
    def setCameraDevice(self, dev):
        self._set(cameraDevice=dev)

    @Slot(str)
    def setEffect(self, e):
        self._set(effect=e)

    @Slot(str)
    def setBackground(self, url):
        path = QUrl(url).toLocalFile() if url.startswith("file:") else url
        self._set(background=path, effect="replace")

    @Slot(str)
    def setQuality(self, q):
        self._set(quality=q)

    @Slot(str)
    def setUpscale(self, level):
        if level in ("aus", "schnell", "beste"):
            self._set(upscale=level)

    @Slot(bool)
    def setPreview(self, on):
        self._preview_on = bool(on)
        if on:
            self._preview_stamp = None
            self._preview_timer.start()
            self._update_preview()
        else:
            self._preview_timer.stop()
        flag = daemon.runtime_dir() / "preview-wanted"
        try:
            if on:
                flag.touch()
            elif flag.exists():
                flag.unlink()
        except OSError:
            pass

    @Slot()
    def refreshCameras(self):
        self._cameras = daemon.list_cameras()
        self.changed.emit()

    def _preview_url(self):
        p = daemon.runtime_dir() / "preview.jpg"
        return (QUrl.fromLocalFile(str(p)).toString() + f"?r={self._preview_rev}") if p.exists() else ""

    voice = Property(bool, lambda self: bool(self._cfg["voice"]), notify=changed)
    strength = Property(int, lambda self: int(self._cfg["voiceStrength"]), notify=changed)
    camera = Property(bool, lambda self: bool(self._cfg["camera"]), notify=changed)
    cameraDevice = Property(str, lambda self: self._cfg["cameraDevice"], notify=changed)
    effect = Property(str, lambda self: self._cfg["effect"], notify=changed)
    background = Property(str, lambda self: self._cfg["background"], notify=changed)
    backgroundUrl = Property(str, lambda self: QUrl.fromLocalFile(self._cfg["background"]).toString()
                             if self._cfg["background"] else "", notify=changed)
    quality = Property(str, lambda self: self._cfg["quality"], notify=changed)
    cameras = Property("QVariantList", lambda self: self._cameras, notify=changed)
    microphones = Property("QVariantList", lambda self: self._microphones, notify=changed)
    voiceInput = Property(str, lambda self: self._cfg.get("voiceInput", ""), notify=changed)
    voiceStatus = Property(str, lambda self: self._status.get("voice", "aus"), notify=statusChanged)
    cameraStatus = Property(str, lambda self: self._status.get("camera", "aus"), notify=statusChanged)
    fps = Property(int, lambda self: int(self._status.get("fps", 0) or 0), notify=statusChanged)
    engine = Property(str, lambda self: self._status.get("engine", ""), notify=statusChanged)
    deepFilter = Property(bool, lambda self: daemon.ladspa_plugin() is not None, constant=True)
    previewUrl = Property(str, _preview_url, notify=previewChanged)
    upscale = Property(str, lambda self: self._cfg.get("upscale", "aus"), notify=changed)
    upscaleState = Property(str, lambda self: self._status.get("upscale", "aus"), notify=statusChanged)
    upscaleMs = Property(float, lambda self: float(self._status.get("upscaleMs", 0) or 0), notify=statusChanged)
    processingMs = Property(float, lambda self: float(self._status.get("processingMs", 0) or 0), notify=statusChanged)
    budgetMs = Property(float, lambda self: float(self._status.get("budgetMs", 0) or 0), notify=statusChanged)
    slow = Property(bool, lambda self: bool(self._status.get("slow", False)), notify=statusChanged)
    cameraMode = Property(str, lambda self: self._status.get("mode", ""), notify=statusChanged)
    outputMode = Property(str, lambda self: self._status.get("output", ""), notify=statusChanged)
    upscaleAvailable = Property(str, lambda self: self._up_reason, constant=True)
