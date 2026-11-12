"""Musik-Visualizer hinter der Taskleiste.

Hört am „Monitor“ der Standard-Audioausgabe mit (alles, was gerade zu hören
ist – Creative Player, Brave, Spotify …) und rechnet daraus Balken.
Läuft nur, solange überhaupt etwas abgespielt wird; ist es still,
blenden die Balken aus und die Aufnahme wird beendet.
"""

import shutil
import subprocess
import threading
import time

from PySide6.QtCore import Property, QFileSystemWatcher, QObject, QTimer, Signal, Slot

from . import config
from .mainthread import post

try:
    import numpy as np
except ImportError:
    np = None

BARS = 72
RATE = 44100
CHUNK = 2048            # ~46 ms
SILENCE = 1e-4


class Visualizer(QObject):
    levelsChanged = Signal()
    activeChanged = Signal()
    enabledChanged = Signal()
    _frame = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._levels = [0.0] * BARS
        self._active = False
        cfg = config.load()
        self._can = np is not None and bool(shutil.which("parec"))
        self._enabled = bool(cfg.get("taskbarVisualizer", True)) and self._can
        self._opacity = float(cfg.get("visualizerOpacity", 0.1))
        # Änderungen aus der Systemsteuerung sofort übernehmen
        config.config_dir().mkdir(parents=True, exist_ok=True)
        self._cfg_watch = QFileSystemWatcher([str(config.config_dir())], self)
        self._cfg_watch.directoryChanged.connect(lambda *_: QTimer.singleShot(150, self._reload_config))
        self._proc = None
        self._stop = threading.Event()
        self._last_sound = 0.0
        self._frame.connect(self._apply)
        # Alle 2 s schauen, ob irgendetwas Ton abspielt
        self._watch = QTimer(self)
        self._watch.setInterval(2000)
        self._watch.timeout.connect(self._check_streams)
        if self._enabled:
            self._watch.start()
            QTimer.singleShot(1500, self._check_streams)

    # ---- Wird etwas abgespielt? ---------------------------------------------------------------
    def _check_streams(self):
        def work():
            playing = False
            try:
                r = subprocess.run(["pactl", "list", "sink-inputs", "short"], capture_output=True, text=True, timeout=3)
                # Spalte 5 ist bei neueren pactl-Versionen der Zustand (RUNNING/CORKED) – sonst reicht „vorhanden“
                for line in r.stdout.splitlines():
                    if line.strip() and "CORKED" not in line:
                        playing = True
                        break
            except (OSError, subprocess.SubprocessError):
                pass
            if playing and self._proc is None:
                self._start()
            elif not playing and self._proc is not None and time.monotonic() - self._last_sound > 3:
                self._stop_capture()
        threading.Thread(target=work, daemon=True).start()

    def _start(self):
        if self._proc is not None or not self._enabled:
            return
        try:
            self._proc = subprocess.Popen(
                ["parec", "--device=@DEFAULT_MONITOR@", f"--rate={RATE}", "--channels=1", "--format=float32le",
                 "--raw", "--latency-msec=30", "--client-name=Creative Visualizer", "--stream-name=Taskleiste"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError:
            self._proc = None
            return
        self._stop.clear()
        self._last_sound = time.monotonic()
        threading.Thread(target=self._loop, args=(self._proc,), daemon=True).start()

    def _stop_capture(self):
        proc, self._proc = self._proc, None
        self._stop.set()
        if proc:
            try:
                proc.terminate()
            except OSError:
                pass
        self._frame.emit(None)

    # ---- Rechnen ---------------------------------------------------------------------------------
    def _loop(self, proc):
        n = CHUNK
        window = np.hanning(n).astype(np.float32)
        freqs = np.fft.rfftfreq(n, 1 / RATE)
        # Logarithmisch verteilte Bänder von 40 Hz bis 16 kHz
        edges = np.geomspace(40, 16000, BARS + 1)
        idx = [(max(1, int(np.searchsorted(freqs, edges[i]))), max(2, int(np.searchsorted(freqs, edges[i + 1]))))
               for i in range(BARS)]
        smooth = np.zeros(BARS, dtype=np.float32)
        peak = 1e-3
        buf = b""
        need = n * 4
        while not self._stop.is_set():
            data = proc.stdout.read(need // 2)          # halbe Fenster → ~43 Bilder/s
            if not data:
                break
            buf = (buf + data)[-need:]
            if len(buf) < need:
                continue
            x = np.frombuffer(buf, dtype=np.float32)
            rms = float(np.sqrt(np.mean(x * x)))
            if rms > SILENCE:
                self._last_sound = time.monotonic()
            spec = np.abs(np.fft.rfft(x * window))
            bands = np.array([spec[a:max(b, a + 1)].mean() for a, b in idx], dtype=np.float32)
            bands *= np.linspace(1.0, 3.2, BARS, dtype=np.float32)     # Höhen etwas anheben
            bands = np.log1p(bands * 8)
            peak = max(peak * 0.995, float(bands.max()), 0.5)           # automatische Aussteuerung
            level = np.clip(bands / peak, 0, 1)
            # schnell hoch, langsam runter
            smooth = np.where(level > smooth, smooth * 0.35 + level * 0.65, smooth * 0.82 + level * 0.18)
            if rms <= SILENCE and time.monotonic() - self._last_sound > 1.5:
                smooth *= 0.8
            post(self._frame.emit, [round(float(v), 3) for v in smooth])
        post(self._frame.emit, None)

    def _apply(self, levels):
        if levels is None:
            self._levels = [0.0] * BARS
            if self._active:
                self._active = False
                self.activeChanged.emit()
        else:
            self._levels = levels
            loud = max(levels) > 0.04
            if loud != self._active:
                self._active = loud
                self.activeChanged.emit()
        self.levelsChanged.emit()

    def _reload_config(self):
        cfg = config.load()
        op = float(cfg.get("visualizerOpacity", 0.1))
        if abs(op - self._opacity) > 0.001:
            self._opacity = op
            self.enabledChanged.emit()
        on = bool(cfg.get("taskbarVisualizer", True)) and self._can
        if on != self._enabled:
            self._apply_enabled(on)

    @Slot(bool)
    def setEnabled(self, on):
        on = bool(on) and self._can
        if on == self._enabled:
            return
        config.set_value("taskbarVisualizer", on)
        self._apply_enabled(on)

    def _apply_enabled(self, on):
        self._enabled = on
        if on:
            self._watch.start()
            self._check_streams()
        else:
            self._watch.stop()
            self._stop_capture()
        self.enabledChanged.emit()

    levels = Property("QVariantList", lambda self: self._levels, notify=levelsChanged)
    active = Property(bool, lambda self: self._active, notify=activeChanged)
    enabled = Property(bool, lambda self: self._enabled, notify=enabledChanged)
    strength = Property(float, lambda self: self._opacity, notify=enabledChanged)
    bars = Property(int, lambda self: BARS, constant=True)
