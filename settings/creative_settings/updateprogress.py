"""Fortschritt und Restzeit beim Laden eines Creative-OS-Updates.

rpm-ostree meldet nur grob, was es tut:
    ostree chunk layers needed: 52 (2.4 GB)
    custom layers needed: 3 (1.9 GB)
    Fetching ostree chunk sha256:2a3f… (47.1 MB)... done
    Fetching layer sha256:91bc… (1.8 GB)...
Byte-genauen Fortschritt innerhalb einer Schicht gibt es nicht. Deshalb wird
zusätzlich gemessen, wie viele Bytes die Netzwerkkarte gerade empfängt; daraus
ergeben sich ein gleichmäßiger Balken, die Geschwindigkeit und die Restzeit.
"""

import re

UNITS = {"b": 1, "bytes": 1, "byte": 1, "kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12,
         "kib": 1024, "mib": 1024 ** 2, "gib": 1024 ** 3, "tib": 1024 ** 4}
SIZE = re.compile(r"\(\s*([\d.,]+)\s*([kmgt]?i?b|bytes?)\s*\)", re.I)
NEEDED = re.compile(r"layers needed:\s*(\d+)\s*\(\s*([\d.,]+)\s*([kmgt]?i?b|bytes?)\s*\)", re.I)


def parse_size(number, unit):
    try:
        value = float(number.replace(",", "."))
    except ValueError:
        return 0
    return int(value * UNITS.get(unit.lower(), 1))


def human_bytes(n):
    n = max(0, float(n))
    if n >= 1e9:
        text = f"{n / 1e9:.1f} GB"
    elif n >= 1e6:
        text = f"{n / 1e6:.0f} MB"
    else:
        text = f"{n / 1e3:.0f} KB"
    return text.replace(".", ",")


def human_eta(seconds):
    if seconds is None:
        return ""
    seconds = int(round(seconds))
    if seconds < 45:
        return "noch wenige Sekunden"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"noch etwa {max(1, minutes)} Min."
    hours, rest = divmod(minutes, 60)
    return f"noch etwa {hours} Std. {rest} Min." if rest else f"noch etwa {hours} Std."


def human_duration(seconds):
    seconds = int(max(0, seconds))
    if seconds < 60:
        return f"{seconds} s"
    return f"{seconds // 60}:{seconds % 60:02d} Min."


class UpdateProgress:
    """Wertet die Ausgabe von rpm-ostree aus und schätzt die Restzeit.

    feed(line)            – eine Zeile der Ausgabe
    sample(t, rx, wx)     – Zeitpunkt (s), empfangene Bytes der Netzwerkkarte(n), geschriebene Bytes der Platten
    state()               – {"progress": 0–100 oder -1, "text": "…"}
    finish(t) / history() – gemessene Zeiten fürs nächste Update merken

    Nach dem Herunterladen einer Schicht entpackt rpm-ostree sie noch und schreibt sie
    auf die Platte – bei großen Schichten dauert das Minuten, obwohl das Netz schon still ist.
    Dafür wird die Verarbeitungsgeschwindigkeit gemessen (und für das nächste Update gemerkt).
    """

    DOWNLOAD_SHARE = 92          # Prozent des Balkens für Laden + Entpacken, der Rest fürs Vorbereiten
    DEFAULT_PROC_RATE = 60e6     # Bytes/s beim Entpacken, bis es gemessen ist
    DEFAULT_STAGE_SECS = 90

    def __init__(self, history=None):
        history = history or {}
        self.totals = {}         # "ostree chunk" / "custom" → Bytes
        self.layers_needed = 0
        self.done_bytes = 0      # fertig geladene und entpackte Schichten
        self.current = 0         # Größe der Schicht, die gerade lädt/entpackt wird
        self.layers_done = 0
        self.phase = "wait"      # wait → download → stage → done
        self.rx_start = None
        self.rx_last = None
        self.received = 0        # laut Netzwerkkarte seit Beginn des Ladens
        self.speed = None        # Bytes/s, geglättet
        self.last_t = None
        self.no_update = False
        self._was_downloading = False
        self.proc_rate = float(history.get("proc_rate") or self.DEFAULT_PROC_RATE)
        self.stage_secs = float(history.get("stage_secs") or self.DEFAULT_STAGE_SECS)
        self.net_done_t = None   # wann die laufende Schicht komplett übers Netz da war
        self.stage_t = None
        self.measured_stage = None
        self.wx_last = None
        self.write_speed = None

    # Ausgabe von rpm-ostree
    def feed(self, line):
        low = line.lower()
        m = NEEDED.search(line)
        if m:
            kind = "custom" if "custom" in low else "chunk"
            self.totals[kind] = parse_size(m.group(2), m.group(3))
            self.layers_needed += int(m.group(1))
            self.phase = "download"
            return
        if "fetching" in low:
            size = SIZE.search(line)
            if size and "done" not in low:
                self.current = parse_size(size.group(1), size.group(2))
                self.net_done_t = None
                self.phase = "download"
            if "done" in low:
                finished = parse_size(size.group(1), size.group(2)) if size else self.current
                if self.net_done_t is not None and self.last_t is not None and finished >= 50e6:
                    took = self.last_t - self.net_done_t
                    if took > 2:
                        measured = finished / took
                        self.proc_rate += (measured - self.proc_rate) * 0.6
                self.done_bytes += finished
                self.layers_done += 1
                self.current = 0
                self.net_done_t = None
            return
        if "staging deployment" in low or "writing objects" in low or "checking out" in low:
            if self.phase != "stage":
                self.stage_t = self.last_t
            self.phase = "stage"
        elif "no upgrade available" in low or "no updates available" in low:
            self.no_update = True
            self.phase = "done"

    # Messung an Netzwerkkarte und Platten
    def sample(self, t, rx, wx=None):
        if self.rx_last is not None and rx < self.rx_last:      # Zähler zurückgesetzt (Karte neu)
            self.rx_start = rx - self.received
        if self.phase in ("wait", "download") and self.rx_start is None:
            self.rx_start = rx
        if self.rx_start is not None:
            self.received = max(0, rx - self.rx_start)
        downloading = self.phase == "download"
        if (downloading and self._was_downloading and self.last_t is not None and self.rx_last is not None
                and t > self.last_t):
            momentary = max(0.0, (rx - self.rx_last) / (t - self.last_t))
            # gleitender Mittelwert über ~8 s: Restzeit springt nicht
            weight = min(1.0, (t - self.last_t) / 8)
            self.speed = momentary if self.speed is None else self.speed + (momentary - self.speed) * weight
        if wx is not None and self.wx_last is not None and self.last_t is not None and t > self.last_t:
            momentary = max(0.0, (wx - self.wx_last) / (t - self.last_t))
            weight = min(1.0, (t - self.last_t) / 5)
            self.write_speed = momentary if self.write_speed is None else \
                self.write_speed + (momentary - self.write_speed) * weight
        if wx is not None:
            self.wx_last = wx
        # laufende Schicht ganz übers Netz da? Dann wird sie jetzt entpackt
        if (downloading and self.current and self.net_done_t is None
                and self.received >= self.done_bytes + self.current):
            self.net_done_t = t
        if self.phase == "stage" and self.stage_t is None:
            self.stage_t = t
        self.rx_last, self.last_t = rx, t
        self._was_downloading = downloading

    def finish(self, t):
        if self.stage_t is not None:
            self.measured_stage = max(1.0, t - self.stage_t)
        self.phase = "done"

    def history(self):
        data = {"proc_rate": round(self.proc_rate)}
        data["stage_secs"] = round(self.measured_stage if self.measured_stage else self.stage_secs)
        return data

    @property
    def total(self):
        return sum(self.totals.values())

    @property
    def loaded(self):
        """Geladene Bytes: fertige Schichten plus laufende Schicht laut Netzwerkkarte."""
        if not self.total:
            return 0
        guess = max(self.done_bytes, min(self.received, self.done_bytes + self.current))
        if not self.current:
            guess = max(self.done_bytes, min(self.received, self.total))
        return min(self.total, guess)

    @property
    def processed(self):
        """Entpackte Bytes: fertige Schichten plus geschätzter Teil der laufenden."""
        part = 0
        if self.current and self.net_done_t is not None and self.last_t is not None:
            part = min(self.current * 0.97, (self.last_t - self.net_done_t) * self.proc_rate)
        return min(self.total, self.done_bytes + part)

    @property
    def unpacking(self):
        return self.phase == "download" and self.net_done_t is not None

    def eta(self):
        if self.phase != "download" or not self.total:
            return None
        backlog = max(0, self.loaded - self.processed)
        if self.unpacking:
            return (self.total - self.processed) / self.proc_rate
        if not self.speed or self.speed < 2e4:
            return None
        # Rest herunterladen, danach die letzte Schicht noch entpacken
        return (self.total - self.loaded) / self.speed + max(backlog, self.current or 0) / self.proc_rate

    def state(self):
        if self.phase == "done":
            return {"progress": 100, "text": "Kein neues Update." if self.no_update else "Fertig."}
        if self.phase == "stage":
            elapsed = (self.last_t or 0) - (self.stage_t if self.stage_t is not None else (self.last_t or 0))
            share = min(1.0, elapsed / max(10.0, self.stage_secs))
            parts = ["Wird für den nächsten Neustart eingerichtet", f"läuft seit {human_duration(elapsed)}"]
            rest = self.stage_secs - elapsed
            parts.append(human_eta(rest) if rest > 0 else "dauert etwas länger als sonst – bitte warten")
            if self.write_speed and self.write_speed > 1e6:
                parts.append(f"schreibt {human_bytes(self.write_speed)}/s")
            return {"progress": self.DOWNLOAD_SHARE + int(share * (99 - self.DOWNLOAD_SHARE)),
                    "text": "  ·  ".join(parts)}
        if self.phase == "wait" or not self.total:
            return {"progress": -1, "text": "Update wird gesucht …" if self.phase == "wait" else "Update wird geladen …"}
        share = (self.loaded + self.processed) / 2 / self.total
        progress = min(self.DOWNLOAD_SHARE - 1, int(share * self.DOWNLOAD_SHARE))
        if self.unpacking:
            n = self.layers_done + 1
            parts = [f"Wird entpackt und gespeichert – Teil {n} von {self.layers_needed}" if self.layers_needed
                     else "Wird entpackt und gespeichert"]
            if self.write_speed and self.write_speed > 1e6:
                parts.append(f"schreibt {human_bytes(self.write_speed)}/s")
            parts.append(human_eta(self.eta()))
            return {"progress": progress, "text": "  ·  ".join(p for p in parts if p)}
        parts = [f"{human_bytes(self.loaded)} von {human_bytes(self.total)}"]
        if self.speed and self.speed >= 2e4:
            parts.append(f"{human_bytes(self.speed)}/s")
            parts.append(human_eta(self.eta()))
        else:
            parts.append("Restzeit wird berechnet …")
        return {"progress": progress, "text": "  ·  ".join(p for p in parts if p)}


def read_rx_bytes(root="/sys/class/net"):
    """Empfangene Bytes aller echten Netzwerkkarten zusammen (ohne lo, Brücken, VPN-Tunnel)."""
    import os
    total = 0
    try:
        names = os.listdir(root)
    except OSError:
        return 0
    for name in names:
        if name == "lo" or name.startswith(("docker", "veth", "br-", "virbr", "tun", "tap", "wg")):
            continue
        try:
            with open(os.path.join(root, name, "statistics", "rx_bytes")) as f:
                total += int(f.read().strip() or 0)
        except (OSError, ValueError):
            continue
    return total


DISK = __import__("re").compile(r"^(sd[a-z]+|vd[a-z]+|xvd[a-z]+|nvme\d+n\d+|mmcblk\d+)$")


def read_wx_bytes(path="/proc/diskstats"):
    """Auf alle Festplatten geschriebene Bytes (ganze Platten, ohne Partitionen)."""
    total = 0
    try:
        with open(path) as f:
            for line in f:
                cols = line.split()
                if len(cols) > 9 and DISK.match(cols[2]):
                    total += int(cols[9]) * 512
    except (OSError, ValueError):
        return None
    return total
