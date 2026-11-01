"""Leistungsdaten des PCs: Prozessor, Arbeitsspeicher, Datenträger, Netzwerk, GPU.

Reines Python (psutil + /sys), damit es Schreibtisch-Anzeige und Taskmanager
gemeinsam nutzen können. sample() liefert bei jedem Aufruf die Werte seit
dem letzten Aufruf (Auslastung, Geschwindigkeiten).
"""

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

try:
    import psutil
except ImportError:          # ohne psutil gibt es eben nur leere Werte
    psutil = None

HISTORY = 60


def fmt_bytes(n, digits=1):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            if unit in ("B", "KB"):
                return f"{n:.0f} {unit}"
            return f"{n:.{digits}f} {unit}".replace(".", ",")
        n /= 1024
    return f"{n:.1f} TB"


def fmt_rate(n):
    """Bytes/s → „1,2 MB/s“ bzw. Netzwerk in Bit („12 Mbit/s“) über fmt_bits."""
    return fmt_bytes(n) + "/s"


def fmt_bits(bytes_per_s):
    b = float(bytes_per_s or 0) * 8
    for unit in ("bit/s", "Kbit/s", "Mbit/s", "Gbit/s"):
        if b < 1000 or unit == "Gbit/s":
            return (f"{b:.0f} {unit}" if unit in ("bit/s", "Kbit/s") else f"{b:.1f} {unit}").replace(".", ",")
        b /= 1000
    return f"{b:.1f} Gbit/s"


def fmt_uptime(seconds):
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{d}:{h:02d}:{m:02d}:{s:02d}"


def cpu_name():
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                name = line.split(":", 1)[1].strip()
                name = re.sub(r"\((R|TM)\)|CPU|Processor|\s+@.*", " ", name, flags=re.I)
                name = re.sub(r"\s+\d+-Core\s*", " ", name)
                return re.sub(r"\s+", " ", name).strip()
    except OSError:
        pass
    return "Prozessor"


def _disk_kind(name):
    if name.startswith("nvme"):
        return "M2"
    try:
        rot = Path(f"/sys/block/{name}/queue/rotational").read_text().strip()
        removable = Path(f"/sys/block/{name}/removable").read_text().strip() == "1"
    except OSError:
        return "Laufwerk"
    if removable:
        return "USB"
    return "Festplatte" if rot == "1" else "SSD"


def physical_disks():
    out = []
    try:
        for d in sorted(os.listdir("/sys/block")):
            if re.match(r"(loop|ram|zram|dm-|sr|fd|md)", d):
                continue
            try:
                if int(Path(f"/sys/block/{d}/size").read_text()) * 512 < 1 << 30:   # < 1 GB: Kartenleser o. Ä.
                    continue
            except (OSError, ValueError):
                continue
            out.append(d)
    except OSError:
        pass
    return out


def _system_disk():
    """Name der Platte, auf der das System liegt (für die Schreibtisch-Anzeige)."""
    try:
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            parts = line.split()
            if len(parts) > 4 and parts[4] in ("/sysroot", "/"):
                src = line.split(" - ", 1)[1].split()[1]
                dev = os.path.basename(os.path.realpath(src))
                for d in physical_disks():
                    if dev.startswith(d):
                        return d
    except (OSError, IndexError):
        pass
    disks = physical_disks()
    return disks[0] if disks else ""


class Gpu:
    """GPU-Auslastung: AMD über /sys, NVIDIA über nvidia-smi, Intel nur Name."""

    def __init__(self):
        self.kind, self.path, self.name = "", None, ""
        self._last_nv = 0.0
        self._nv = {}
        for card in sorted(Path("/sys/class/drm").glob("card[0-9]")):
            dev = card / "device"
            if (dev / "gpu_busy_percent").exists():
                self.kind, self.path = "amd", dev
                self.name = self._pci_name(dev) or "AMD Radeon"
                break
        if not self.kind and shutil.which("nvidia-smi"):
            self.kind = "nvidia"
            self._query_nvidia(force=True)
            self.name = self._nv.get("name") or "NVIDIA"
            if not self._nv:
                self.kind = ""

    @staticmethod
    def _pci_name(dev):
        try:
            slot = os.path.basename(os.path.realpath(dev))
            r = subprocess.run(["lspci", "-s", slot], capture_output=True, text=True, timeout=2)
            m = re.search(r"\[(Radeon[^\]]*)\]", r.stdout) or re.search(r": (.*)$", r.stdout.strip())
            return ("AMD " + m.group(1)) if m and "Radeon" in m.group(1) else (m.group(1) if m else "")
        except (OSError, subprocess.SubprocessError):
            return ""

    def _query_nvidia(self, force=False):
        now = time.monotonic()
        if not force and now - self._last_nv < 1.8:
            return
        self._last_nv = now
        try:
            r = subprocess.run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                                "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3)
            name, util, used, total, temp = [x.strip() for x in r.stdout.splitlines()[0].split(",")]
            self._nv = {"name": name, "util": float(util), "used": float(used) * 1024 * 1024,
                        "total": float(total) * 1024 * 1024, "temp": float(temp)}
        except (OSError, subprocess.SubprocessError, ValueError, IndexError):
            self._nv = {}

    def sample(self):
        if self.kind == "amd":
            def rd(name):
                try:
                    return float((self.path / name).read_text().strip())
                except (OSError, ValueError):
                    return None
            temp = None
            for h in (self.path / "hwmon").glob("hwmon*"):
                try:
                    temp = int((h / "temp1_input").read_text()) / 1000
                    break
                except (OSError, ValueError):
                    pass
            return {"util": rd("gpu_busy_percent") or 0.0, "used": rd("mem_info_vram_used"),
                    "total": rd("mem_info_vram_total"), "temp": temp}
        if self.kind == "nvidia":
            self._query_nvidia()
            return dict(self._nv) if self._nv else None
        return None


class Sampler:
    def __init__(self):
        self._t = time.monotonic()
        self._disk = psutil.disk_io_counters(perdisk=True) if psutil else {}
        self._net = psutil.net_io_counters(pernic=True) if psutil else {}
        self.gpu = Gpu()
        self.cpu_model = cpu_name()
        self.system_disk = _system_disk()
        if psutil:
            psutil.cpu_percent(percpu=True)
        self.hist = {"cpu": [], "mem": [], "gpu": [], "net": [], "disk": {}}

    @staticmethod
    def _push(lst, value):
        lst.append(value)
        if len(lst) > HISTORY:
            del lst[: len(lst) - HISTORY]

    def sample(self):
        now = time.monotonic()
        dt = max(0.2, now - self._t)
        self._t = now
        out = {"cpu": 0.0, "cores": [], "mem": {}, "disks": [], "net": {}, "gpu": None}
        if not psutil:
            return out

        cores = psutil.cpu_percent(percpu=True)
        cpu = sum(cores) / len(cores) if cores else 0.0
        freq = psutil.cpu_freq()
        temp = None
        try:
            temps = psutil.sensors_temperatures()
            for key in ("k10temp", "coretemp", "zenpower", "cpu_thermal", "acpitz"):
                if temps.get(key):
                    temp = temps[key][0].current
                    break
        except (AttributeError, OSError):
            pass
        self._push(self.hist["cpu"], cpu)
        out.update(cpu=cpu, cores=cores, freq=(freq.current if freq else 0.0), maxfreq=(freq.max if freq else 0.0),
                   temp=temp, logical=psutil.cpu_count() or 1, physical=psutil.cpu_count(logical=False) or 1,
                   uptime=time.time() - psutil.boot_time(), model=self.cpu_model)

        vm, sw = psutil.virtual_memory(), psutil.swap_memory()
        used = vm.total - vm.available
        self._push(self.hist["mem"], 100.0 * used / vm.total if vm.total else 0)
        out["mem"] = {"total": vm.total, "used": used, "available": vm.available,
                      "cached": getattr(vm, "cached", 0) + getattr(vm, "buffers", 0),
                      "percent": 100.0 * used / vm.total if vm.total else 0,
                      "swapTotal": sw.total, "swapUsed": sw.used}

        disks_now = psutil.disk_io_counters(perdisk=True) or {}
        for name in physical_disks():
            a, b = self._disk.get(name), disks_now.get(name)
            if not b:
                continue
            busy = rd = wr = 0.0
            if a:
                busy = min(100.0, 100.0 * (getattr(b, "busy_time", 0) - getattr(a, "busy_time", 0)) / (dt * 1000))
                rd = (b.read_bytes - a.read_bytes) / dt
                wr = (b.write_bytes - a.write_bytes) / dt
            h = self.hist["disk"].setdefault(name, [])
            self._push(h, max(0.0, busy))
            try:
                size = int(Path(f"/sys/block/{name}/size").read_text()) * 512
            except (OSError, ValueError):
                size = 0
            try:
                model = Path(f"/sys/block/{name}/device/model").read_text().strip()
            except OSError:
                model = ""
            out["disks"].append({"name": name, "kind": _disk_kind(name), "busy": max(0.0, busy), "read": max(0.0, rd),
                                 "write": max(0.0, wr), "size": size, "model": model,
                                 "system": name == self.system_disk, "history": list(h)})
        self._disk = disks_now

        net_now = psutil.net_io_counters(pernic=True) or {}
        stats = psutil.net_if_stats()
        best, best_total = None, -1
        for nic, b in net_now.items():
            if nic == "lo" or nic.startswith(("veth", "docker", "virbr", "br-", "tun", "podman")):
                continue
            st = stats.get(nic)
            if st and not st.isup:
                continue
            total = b.bytes_recv + b.bytes_sent
            if total > best_total:
                best, best_total = nic, total
        if best:
            a, b = self._net.get(best), net_now[best]
            up = (b.bytes_sent - a.bytes_sent) / dt if a else 0.0
            down = (b.bytes_recv - a.bytes_recv) / dt if a else 0.0
            wifi = best.startswith(("wl", "wifi", "ath"))
            self._push(self.hist["net"], max(0.0, up + down))
            out["net"] = {"name": best, "label": "WLAN" if wifi else "Ethernet", "up": max(0.0, up), "down": max(0.0, down),
                          "speed": (stats[best].speed if best in stats else 0)}
        self._net = net_now

        g = self.gpu.sample()
        if g is not None:
            self._push(self.hist["gpu"], g.get("util") or 0.0)
            g["name"] = self.gpu.name
            out["gpu"] = g
        return out

    # Netzwerk-Verlauf in Prozent des bisherigen Höchstwerts (für die Kurve)
    def net_history_percent(self):
        h = self.hist["net"]
        peak = max(h) if h else 0
        peak = max(peak, 128 * 1024)
        return [100.0 * v / peak for v in h]


# ---- Kacheln (gleich im Taskmanager und auf dem Schreibtisch) ------------------------------------
TILE_COLORS = {"cpu": "#8fb3ff", "mem": "#d7a8ff", "disk": "#6fdcc0", "net": "#ffb07a", "gpu": "#f2d58a"}


def _pct(v):
    return f"{v:.0f} %"


def tiles(s, sampler, all_disks=False):
    """Kurzfassung für die Leistungs-Kacheln: Titel, Wert, Zusatz, Verlauf (0–100)."""
    out = []
    if not s or "model" not in s:
        return out
    freq = s.get("freq") or 0
    out.append({"key": "cpu", "title": "CPU", "value": _pct(s["cpu"]),
                "sub": (f"{freq / 1000:.2f} GHz".replace(".", ",") if freq else s.get("model", "")),
                "history": list(sampler.hist["cpu"]), "color": TILE_COLORS["cpu"]})
    m = s["mem"]
    out.append({"key": "mem", "title": "Arbeitsspeicher", "value": _pct(m["percent"]),
                "sub": f"{fmt_bytes(m['used'])} / {fmt_bytes(m['total'])}",
                "history": list(sampler.hist["mem"]), "color": TILE_COLORS["mem"]})
    disks = s["disks"] if all_disks else [d for d in s["disks"] if d["system"]][:1] or s["disks"][:1]
    for i, d in enumerate(disks):
        label = "Creative OS" if d["system"] else d["kind"]
        out.append({"key": "disk:" + d["name"], "title": f"Datenträger {i}" if all_disks else "Datenträger",
                    "value": _pct(d["busy"]), "sub": f"{label} · {fmt_bytes(d['size'], 0)}",
                    "history": d["history"], "color": TILE_COLORS["disk"]})
    n = s.get("net") or {}
    if n:
        out.append({"key": "net", "title": n["label"], "value": "↓ " + fmt_bits(n["down"]),
                    "sub": "↑ " + fmt_bits(n["up"]), "history": sampler.net_history_percent(),
                    "color": TILE_COLORS["net"]})
    g = s.get("gpu")
    if g:
        out.append({"key": "gpu", "title": "GPU", "value": _pct(g.get("util") or 0),
                    "sub": g.get("name", "") + (f" · {g['temp']:.0f} °C" if g.get("temp") else ""),
                    "history": list(sampler.hist["gpu"]), "color": TILE_COLORS["gpu"]})
    return out
