"""Grafikkarte (Systemsteuerung › Grafikkarte) – Daten der eingebauten Grafikkarte und ihre Beleuchtung.

Daten:
* NVIDIA: nvidia-smi (Name, Grafikspeicher, Treiber, Takt, Temperatur, Auslastung, Leistung, Lüfter, PCIe, BIOS)
* AMD/Intel: /sys/class/drm (Grafikspeicher, Auslastung, Temperatur, Takt) und lspci für den Namen

Beleuchtung: über OpenRGB (Kommandozeile), sofern die Karte RGB-Beleuchtung hat und OpenRGB sie
erkennt. Die gewählte Farbe wird gespeichert und beim Anmelden wieder gesetzt
(python3 -m creative_settings.gpu --licht-wiederherstellen).
"""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

NVSMI_FIELDS = ("name", "memory.total", "memory.used", "driver_version", "temperature.gpu", "utilization.gpu",
                "power.draw", "power.limit", "clocks.gr", "clocks.max.gr", "clocks.mem", "fan.speed",
                "pcie.link.gen.current", "pcie.link.width.current", "vbios_version")

# Modi, die wir anbieten (OpenRGB-Name → Anzeige). Es erscheinen nur die, die die Karte kann.
MODES = (("static", "Statisch"), ("breathing", "Atmen"), ("spectrum cycle", "Farbwechsel"),
         ("rainbow", "Regenbogen"), ("off", "Aus"))
COLORS = ("#3d7bff", "#00c2ff", "#30d158", "#ffd60a", "#ff9f0a", "#ff375f", "#bf5af2", "#ffffff")


def _cfg_file():
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "creative-os" / "grafikkarte.json"


def load_light():
    try:
        return json.loads(_cfg_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


AUTOSTART = """[Desktop Entry]
Type=Application
Name=Grafikkarten-Beleuchtung
Comment=Stellt beim Anmelden die gewählte Beleuchtung der Grafikkarte wieder her
Exec=sh -c 'PYTHONPATH=/usr/lib/creative-settings exec python3 -m creative_settings.gpu --licht-wiederherstellen'
NoDisplay=true
X-Gibeon-Autostart=true
"""


def save_light(data):
    f = _cfg_file()
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        tmp.replace(f)
        # beim Anmelden wiederherstellen (Gibeon startet ~/.config/autostart)
        auto = f.parent.parent / "autostart" / "gibeon-grafikkarte-licht.desktop"
        auto.parent.mkdir(parents=True, exist_ok=True)
        if not auto.exists():
            auto.write_text(AUTOSTART, encoding="utf-8")
    except OSError:
        pass


def _num(v):
    try:
        return float(str(v).strip().split()[0])
    except (ValueError, IndexError):
        return None


def parse_nvsmi(line):
    """Eine Zeile von nvidia-smi --format=csv,noheader,nounits → dict."""
    vals = [v.strip() for v in line.split(",")]
    if len(vals) < len(NVSMI_FIELDS):
        return None
    d = dict(zip(NVSMI_FIELDS, vals))
    return {
        "vendor": "nvidia",
        "name": d["name"],
        "vramMb": _num(d["memory.total"]), "vramUsedMb": _num(d["memory.used"]),
        "driver": d["driver_version"], "temp": _num(d["temperature.gpu"]), "load": _num(d["utilization.gpu"]),
        "power": _num(d["power.draw"]), "powerLimit": _num(d["power.limit"]),
        "clock": _num(d["clocks.gr"]), "clockMax": _num(d["clocks.max.gr"]), "memClock": _num(d["clocks.mem"]),
        "fan": _num(d["fan.speed"]), "pcie": (f"PCIe {d['pcie.link.gen.current']}.0 x{d['pcie.link.width.current']}"
                                             if _num(d["pcie.link.gen.current"]) else ""),
        "bios": d["vbios_version"] if d["vbios_version"] not in ("[N/A]", "N/A") else "",
    }


def series(name):
    """Baureihe und Modell für das Abzeichen: „GeForce RTX 3060“ → („GeForce RTX“, „3060“)."""
    n = re.sub(r"^NVIDIA\s+", "", name or "").strip()
    n = re.sub(r"^(AMD|Intel\(R\)|Intel)\s+", "", n)
    for pat in (r"(.*?\b(?:RTX|GTX|RX|Arc)\b(?:\s+PRO)?)\s+(.+)$", r"(.*?\b(?:Quadro|Radeon)\b)\s+(.+)$"):
        m = re.match(pat, n, re.I)
        if m:
            return m.group(1).strip(), m.group(2).strip()
    return "", n


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _lspci_name(slot):
    try:
        out = subprocess.run(["lspci", "-s", slot, "-mm"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    parts = re.findall(r'"([^"]*)"', out)
    if len(parts) >= 3:
        vendor, dev = parts[1], parts[2]
        m = re.search(r"\[([^\]]+)\]", dev)
        dev = m.group(1) if m else dev
        vendor = re.sub(r"\s*\[.*?\]|Corporation|Advanced Micro Devices, Inc\.|, Inc\.", "", vendor).strip(" ,")
        return f"{vendor} {dev}".strip()
    return ""


def sysfs_gpus(root="/sys/class/drm"):
    """AMD/Intel (und NVIDIA ohne nvidia-smi): Grunddaten aus sysfs."""
    gpus = []
    for card in sorted(Path(root).glob("card[0-9]")):
        dev = card / "device"
        vendor = _read(dev / "vendor")
        if vendor not in ("0x1002", "0x8086", "0x10de"):
            continue
        slot = os.path.basename(os.path.realpath(dev))
        g = {"vendor": {"0x1002": "amd", "0x8086": "intel", "0x10de": "nvidia"}[vendor],
             "name": _lspci_name(slot) or {"0x1002": "AMD Radeon", "0x8086": "Intel Grafik", "0x10de": "NVIDIA"}[vendor],
             "driver": os.path.basename(os.path.realpath(dev / "driver")) if (dev / "driver").exists() else ""}
        vram = _num(_read(dev / "mem_info_vram_total"))
        if vram:
            g["vramMb"] = vram / 1048576
            used = _num(_read(dev / "mem_info_vram_used"))
            g["vramUsedMb"] = used / 1048576 if used is not None else None
        g["load"] = _num(_read(dev / "gpu_busy_percent"))
        for hw in (dev / "hwmon").glob("hwmon*"):
            t = _num(_read(hw / "temp1_input"))
            if t is not None:
                g["temp"] = t / 1000
            p = _num(_read(hw / "power1_average"))
            if p is not None:
                g["power"] = p / 1e6
            f = _num(_read(hw / "freq1_input"))
            if f is not None:
                g["clock"] = f / 1e6
        gpus.append(g)
    # eigene Grafikkarte vor der im Prozessor
    gpus.sort(key=lambda g: (g["vendor"] == "intel", -(g.get("vramMb") or 0)))
    return gpus


def read_gpu():
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=" + ",".join(NVSMI_FIELDS),
                                  "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=6).stdout
            for line in out.splitlines():
                g = parse_nvsmi(line)
                if g:
                    return g
        except (OSError, subprocess.SubprocessError):
            pass
    gpus = sysfs_gpus()
    return gpus[0] if gpus else {}


# ---- Beleuchtung (OpenRGB) ----------------------------------------------------------------------
def parse_openrgb(text):
    """Ausgabe von „openrgb --list-devices“ → Grafikkarten [{index, name, modes}]."""
    devs, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^(\d+):\s*(.+)$", line.strip())
        if m:
            cur = {"index": int(m.group(1)), "name": m.group(2).strip(), "type": "", "modes": []}
            devs.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"^\s*Type:\s*(.+)$", line)
        if m:
            cur["type"] = m.group(1).strip()
        m = re.match(r"^\s*Modes:\s*(.+)$", line)
        if m:
            # z. B.  Modes: [Direct] Static Breathing 'Spectrum Cycle' Rainbow   ([…] = gerade aktiv)
            cur["modes"] = [(q or w).lower() for q, w in re.findall(r"'([^']+)'|\[?([^\s'\[\]]+)\]?", m.group(1))]
    return [d for d in devs if d["type"].lower() == "gpu"]


def openrgb_gpus(timeout=25):
    exe = shutil.which("openrgb")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--noautoconnect", "--list-devices"], capture_output=True, text=True,
                             timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_openrgb(out)


def openrgb_set(index, mode, color):
    exe = shutil.which("openrgb")
    if not exe:
        return False, "OpenRGB fehlt"
    if mode == "off":
        # „Aus“: schwarz setzen – das kann jede Karte (eigener Modus „Off“ nur bei manchen)
        args = [exe, "--noautoconnect", "-d", str(int(index)), "-m", "direct", "-c", "000000"]
    else:
        args = [exe, "--noautoconnect", "-d", str(int(index)), "-m", mode]
        if mode in ("static", "direct", "breathing"):
            args += ["-c", color.lstrip("#").upper()]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=25)
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    return r.returncode == 0, (r.stderr or r.stdout).strip()[-300:]


def restore_light():
    """Beim Anmelden: zuletzt gewählte Beleuchtung wieder setzen."""
    data = load_light()
    if not data.get("mode") or data.get("index") is None:
        return
    devs = openrgb_gpus() or []
    if any(d["index"] == data["index"] for d in devs):
        openrgb_set(data["index"], data["mode"], data.get("color", "#3d7bff"))


try:
    from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
except ImportError:
    QObject = None

if QObject is not None:
    class GpuModel(QObject):
        changed = Signal()
        _gotInfo = Signal(object)
        _gotLight = Signal(object)
        _applied = Signal(bool, str)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._info = {}
            self._light_devs = None          # None = wird gesucht, [] = keine steuerbare Beleuchtung
            self._light_note = ""
            saved = load_light()
            self._mode = saved.get("mode", "static")
            self._color = saved.get("color", COLORS[0])
            self._dev = saved.get("index")
            self._busy = False
            self._active = False
            self._gotInfo.connect(self._set_info)
            self._gotLight.connect(self._set_light)
            self._applied.connect(self._done)
            self._timer = QTimer(self)
            self._timer.setInterval(2000)
            self._timer.timeout.connect(self.refresh)

        @Slot(bool)
        def setActive(self, on):
            """Nur messen, solange die Seite offen ist."""
            self._active = bool(on)
            if on:
                self.refresh()
                self._timer.start()
                if self._light_devs is None:
                    self.scanLight()
            else:
                self._timer.stop()

        @Slot()
        def refresh(self):
            threading.Thread(target=lambda: self._gotInfo.emit(read_gpu()), daemon=True).start()

        def _set_info(self, info):
            self._info = info or {}
            self.changed.emit()

        @Slot()
        def scanLight(self):
            self._light_devs = None
            self._light_note = "Suche nach steuerbarer Beleuchtung …"
            self.changed.emit()
            threading.Thread(target=lambda: self._gotLight.emit(openrgb_gpus()), daemon=True).start()

        def _set_light(self, devs):
            if devs is None:
                self._light_devs = []
                self._light_note = "OpenRGB fehlt – die Beleuchtung lässt sich nicht steuern."
            else:
                self._light_devs = devs
                self._light_note = "" if devs else ("Bei deiner Grafikkarte wurde keine steuerbare Beleuchtung gefunden. "
                                                    "Viele Karten haben keine oder nur eine feste Beleuchtung.")
                if devs and not any(d["index"] == self._dev for d in devs):
                    self._dev = devs[0]["index"]
            self.changed.emit()

        def _device(self):
            return next((d for d in (self._light_devs or []) if d["index"] == self._dev), None)

        @Slot(str)
        def setMode(self, mode):
            self._mode = mode
            self._apply()

        @Slot(str)
        def setColor(self, color):
            if re.fullmatch(r"#[0-9a-fA-F]{6}", color or ""):
                self._color = color.lower()
                if self._mode not in ("static", "direct", "breathing"):
                    keys = [m["key"] for m in self._modes()]
                    self._mode = "static" if "static" in keys else ("direct" if "direct" in keys else self._mode)
                self._apply()

        def _apply(self):
            dev = self._device()
            self.changed.emit()
            if not dev or self._busy:
                return
            self._busy = True
            idx, mode, color = dev["index"], self._mode, self._color
            save_light({"index": idx, "mode": mode, "color": color})
            threading.Thread(target=lambda: self._applied.emit(*openrgb_set(idx, mode, color)), daemon=True).start()

        def _done(self, ok, msg):
            self._busy = False
            self._light_note = "" if ok else ("Die Beleuchtung ließ sich nicht setzen. " + (msg or ""))
            self.changed.emit()

        def _modes(self):
            dev = self._device()
            if not dev:
                return []
            have = set(dev["modes"])
            out = []
            for k, label in MODES:
                if k in have:
                    out.append({"key": k, "label": label})
                elif k == "static" and "direct" in have:
                    out.append({"key": "direct", "label": label})
                elif k == "rainbow" and "rainbow wave" in have:
                    out.append({"key": "rainbow wave", "label": label})
                elif k == "off" and ("direct" in have or "static" in have):
                    out.append({"key": "off", "label": label})
            return out

        info = Property("QVariantMap", lambda self: self._info, notify=changed)
        badge = Property("QVariantList", lambda self: list(series(self._info.get("name", ""))), notify=changed)
        lightReady = Property(bool, lambda self: self._light_devs is not None, notify=changed)
        lightAvailable = Property(bool, lambda self: bool(self._light_devs), notify=changed)
        lightName = Property(str, lambda self: (self._device() or {}).get("name", ""), notify=changed)
        lightNote = Property(str, lambda self: self._light_note, notify=changed)
        modes = Property("QVariantList", _modes, notify=changed)
        mode = Property(str, lambda self: self._mode, notify=changed)
        color = Property(str, lambda self: self._color, notify=changed)
        colors = Property("QVariantList", lambda self: list(COLORS), notify=changed)
        busy = Property(bool, lambda self: self._busy, notify=changed)


if __name__ == "__main__" and "--licht-wiederherstellen" in sys.argv:
    restore_light()
