"""Beleuchtung des Mikrofons (Systemsteuerung › Ton) – vorerst nur HyperX (QuadCast S, QuadCast 2 S, DuoCast).

Erkannt wird das Mikrofon am USB-Namen. Gesteuert wird es über QuadcastRGB (Ors1mer, GPL-2.0) – das
spricht QuadCast S/2/2 S und DuoCast direkt an und hält die Farbe (OpenRGB setzt sie nur kurz, danach
fällt das Mikrofon auf seine eigene Farbe zurück). Ohne QuadcastRGB: OpenRGB (Gerätetyp „Microphone“).
Die Wahl wird gespeichert und beim Anmelden wieder gesetzt
(python3 -m creative_settings.mikro_rgb --licht-wiederherstellen).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import threading
from pathlib import Path

from . import gpu

MODES = (("static", "Statisch"), ("breathing", "Atmen"), ("spectrum cycle", "Farbwechsel"),
         ("rainbow", "Regenbogen"), ("off", "Aus"))
COLORS = gpu.COLORS
AUTOSTART = gpu.AUTOSTART.replace("Grafikkarten-Beleuchtung", "Mikrofon-Beleuchtung").replace(
    "der Grafikkarte", "des Mikrofons").replace("creative_settings.gpu", "creative_settings.mikro_rgb")


def hyperx_mics(root="/sys/bus/usb/devices"):
    """Angeschlossene HyperX-Mikrofone (Name laut USB), z. B. ["HyperX QuadCast S"]."""
    fake = os.environ.get("CREATIVE_MIC_FAKE")        # nur für Vorschau-Fotos
    if fake:
        return [fake]
    found = []
    for dev in Path(root).glob("*"):
        try:
            product = (dev / "product").read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        try:
            maker = (dev / "manufacturer").read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            maker = ""
        text = f"{maker} {product}"
        if re.search(r"hyperx", text, re.I) and re.search(r"cast", product, re.I):
            name = product if product.lower().startswith("hyperx") else f"HyperX {product}"
            if name not in found:
                found.append(name)
    return found


# USB-Kennungen, die QuadcastRGB kennt (QuadCast S, QuadCast 2/2 S, DuoCast)
QC_IDS = {"0951:171f", "03f0:0f8b", "03f0:028c", "03f0:048c", "03f0:068c", "03f0:098c"}
QC_MODES = {"static": ["solid"], "breathing": ["pulse"], "spectrum cycle": ["cycle"],
            "rainbow": ["wave"], "off": ["solid", "0"]}
QC_DEV = {"index": -1, "name": "QuadcastRGB", "modes": [k for k, _ in MODES], "via": "quadcastrgb"}


def usb_ids(root="/sys/bus/usb/devices"):
    out = set()
    for dev in Path(root).glob("*"):
        try:
            out.add(f"{(dev / 'idVendor').read_text().strip().lower()}:{(dev / 'idProduct').read_text().strip().lower()}")
        except OSError:
            continue
    return out


def quadcast_ready(root="/sys/bus/usb/devices"):
    return bool(shutil.which("quadcastrgb")) and bool(usb_ids(root) & QC_IDS)


def quadcast_args(mode, color):
    args = list(QC_MODES.get(mode, ["solid"]))
    if args == ["solid"]:
        args.append((color or COLORS[0]).lstrip("#").lower())
    return ["-a", *args]


def quadcast_set(mode, color):
    """Alte Einstellung beenden und neu setzen – QuadcastRGB bleibt im Hintergrund und hält die Farbe."""
    exe = shutil.which("quadcastrgb")
    if not exe:
        return False, "QuadcastRGB fehlt"
    subprocess.run(["pkill", "-x", "quadcastrgb"], capture_output=True)
    for _ in range(30):   # warten, bis das Mikrofon frei ist – sonst „busy“
        if subprocess.run(["pgrep", "-x", "quadcastrgb"], capture_output=True).returncode:
            break
        time.sleep(0.1)
    with tempfile.TemporaryFile() as err:
        try:
            proc = subprocess.Popen([exe, *quadcast_args(mode, color)], stdout=subprocess.DEVNULL,
                                    stderr=err, start_new_session=True)
            code = proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            return True, ""
        except OSError as e:
            return False, str(e)
        err.seek(0)
        text = err.read().decode("utf-8", "replace").strip()[-300:]
    if code == 0:
        return True, ""
    if "busy" in text.lower():
        return False, "Das Mikrofon ist gerade von einem anderen Programm belegt."
    if "code 4" in text or "ermission" in text or "ccess" in text:
        return False, "Kein Zugriff auf das Mikrofon – einmal aus- und wieder einstecken."
    return False, text


def set_light(dev, mode, color):
    if dev and dev.get("via") == "quadcastrgb":
        return quadcast_set(mode, color)
    return gpu.openrgb_set(dev["index"], mode, color)


def is_hyperx(dev):
    return "hyperx" in dev["name"].lower() or "cast" in dev["name"].lower()


def _cfg_file():
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "creative-os" / "mikrofon-licht.json"


def load_light():
    try:
        return json.loads(_cfg_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_light(data):
    f = _cfg_file()
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data, indent=1), encoding="utf-8")
        auto = f.parent.parent / "autostart" / "gibeon-mikrofon-licht.desktop"
        auto.parent.mkdir(parents=True, exist_ok=True)
        if not auto.exists():
            auto.write_text(AUTOSTART, encoding="utf-8")
    except OSError:
        pass


def restore_light():
    data = load_light()
    if not data.get("mode") or not hyperx_mics():
        return
    if quadcast_ready():
        quadcast_set(data["mode"], data.get("color", COLORS[0]))
        return
    devs = [d for d in (gpu.openrgb_devices("microphone") or []) if is_hyperx(d)]
    if devs:
        gpu.openrgb_set(devs[0]["index"], data["mode"], data.get("color", COLORS[0]))


def modes_for(dev):
    have = set(dev["modes"]) if dev else set()
    out = []
    for k, label in MODES:
        if k in have:
            out.append({"key": k, "label": label})
        elif k == "static" and "direct" in have:
            out.append({"key": "direct", "label": label})
        elif k == "rainbow" and "rainbow wave" in have:
            out.append({"key": "rainbow wave", "label": label})
        elif k == "off" and have & {"direct", "static"}:
            out.append({"key": "off", "label": label})
    return out


try:
    from PySide6.QtCore import Property, QObject, Signal, Slot
except ImportError:
    QObject = None

if QObject is not None:
    class MicRgbModel(QObject):
        changed = Signal()
        _gotDevs = Signal(object)
        _applied = Signal(bool, str)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._mics = hyperx_mics()
            self._dev = None
            self._scanned = False
            self._note = ""
            self._busy = False
            saved = load_light()
            self._mode = saved.get("mode", "static")
            self._color = saved.get("color", COLORS[0])
            self._gotDevs.connect(self._set_devs)
            self._applied.connect(self._done)

        @Slot()
        def refresh(self):
            self._mics = hyperx_mics()
            self.changed.emit()

        @Slot()
        def scan(self):
            """Beim Aufklappen: Mikrofon in OpenRGB suchen."""
            if not self._mics:
                return
            if quadcast_ready():
                self._set_devs([QC_DEV])
                return
            self._note = "Mikrofon wird gesucht …"
            self.changed.emit()
            threading.Thread(target=lambda: self._gotDevs.emit(gpu.openrgb_devices("microphone")), daemon=True).start()

        def _set_devs(self, devs):
            self._scanned = True
            if devs is None:
                self._dev, self._note = None, "OpenRGB fehlt – die Beleuchtung lässt sich nicht steuern."
            else:
                mine = [d for d in devs if d.get("via") or is_hyperx(d)]
                self._dev = mine[0] if mine else None
                self._note = "" if self._dev else ("Das Mikrofon wurde gefunden, aber seine Beleuchtung lässt sich noch "
                                                   "nicht ansteuern. Kurz aus- und wieder einstecken und erneut versuchen.")
            self.changed.emit()

        @Slot(str)
        def setMode(self, mode):
            self._mode = mode
            self._apply()

        @Slot(str)
        def setColor(self, color):
            if re.fullmatch(r"#[0-9a-fA-F]{6}", color or ""):
                self._color = color.lower()
                if self._dev and self._dev.get("via"):
                    self._mode = "static"
                elif self._mode not in ("static", "direct", "breathing"):
                    keys = [m["key"] for m in modes_for(self._dev)]
                    self._mode = "static" if "static" in keys else ("direct" if "direct" in keys else self._mode)
                self._apply()

        def _apply(self):
            self.changed.emit()
            if not self._dev:
                return
            if self._busy:
                self._pending = True   # letzte Wahl gilt – wird gesetzt, sobald die vorige fertig ist
                return
            self._pending = False
            self._busy = True
            dev, mode, color = dict(self._dev), self._mode, self._color
            save_light({"mode": mode, "color": color})
            threading.Thread(target=lambda: self._applied.emit(*set_light(dev, mode, color)), daemon=True).start()

        def _done(self, ok, msg):
            self._busy = False
            if getattr(self, "_pending", False):
                self._apply()
                return
            self._note = "" if ok else ("Die Beleuchtung ließ sich nicht setzen. " + (msg or ""))
            self.changed.emit()

        startOpen = Property(bool, lambda self: bool(os.environ.get("CREATIVE_MIC_RGB_OPEN")), constant=True)
        present = Property(bool, lambda self: bool(self._mics), notify=changed)
        micName = Property(str, lambda self: self._mics[0] if self._mics else "", notify=changed)
        ready = Property(bool, lambda self: self._dev is not None, notify=changed)
        scanned = Property(bool, lambda self: self._scanned, notify=changed)
        note = Property(str, lambda self: self._note, notify=changed)
        modes = Property("QVariantList", lambda self: modes_for(self._dev), notify=changed)
        mode = Property(str, lambda self: self._mode, notify=changed)
        color = Property(str, lambda self: self._color, notify=changed)
        colors = Property("QVariantList", lambda self: list(COLORS), notify=changed)
        busy = Property(bool, lambda self: self._busy, notify=changed)


if __name__ == "__main__" and "--licht-wiederherstellen" in sys.argv:
    restore_light()
