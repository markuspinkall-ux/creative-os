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


class UpdateProgress:
    """Wertet die Ausgabe von rpm-ostree aus und schätzt die Restzeit.

    feed(line)       – eine Zeile der Ausgabe
    sample(t, rx)    – Zeitpunkt (s) und empfangene Bytes der Netzwerkkarte(n)
    state()          – {"progress": 0–100 oder -1, "text": "…"}
    """

    DOWNLOAD_SHARE = 92          # Prozent des Balkens fürs Herunterladen, der Rest fürs Vorbereiten

    def __init__(self):
        self.totals = {}         # "ostree chunk" / "custom" → Bytes
        self.layers_needed = 0
        self.done_bytes = 0      # fertig geladene Schichten
        self.current = 0         # Größe der Schicht, die gerade lädt
        self.layers_done = 0
        self.phase = "wait"      # wait → download → stage → done
        self.rx_start = None
        self.rx_last = None
        self.received = 0        # laut Netzwerkkarte seit Beginn des Ladens
        self.speed = None        # Bytes/s, geglättet
        self.last_t = None
        self.no_update = False
        self._was_downloading = False

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
                self.phase = "download"
            if "done" in low:
                finished = parse_size(size.group(1), size.group(2)) if size else self.current
                self.done_bytes += finished
                self.layers_done += 1
                self.current = 0
            return
        if "staging deployment" in low or "writing objects" in low or "checking out" in low:
            self.phase = "stage"
        elif "no upgrade available" in low or "no updates available" in low:
            self.no_update = True
            self.phase = "done"

    # Messung an der Netzwerkkarte
    def sample(self, t, rx):
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
        self.rx_last, self.last_t = rx, t
        self._was_downloading = downloading

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

    def eta(self):
        if self.phase != "download" or not self.total or not self.speed or self.speed < 2e4:
            return None
        return (self.total - self.loaded) / self.speed

    def state(self):
        if self.phase == "done":
            return {"progress": 100, "text": "Kein neues Update." if self.no_update else "Fertig."}
        if self.phase == "stage":
            return {"progress": 96, "text": "Wird für den nächsten Neustart vorbereitet – dauert meist 1–3 Min. …"}
        if self.phase == "wait" or not self.total:
            return {"progress": -1, "text": "Update wird gesucht …" if self.phase == "wait" else "Update wird geladen …"}
        share = self.loaded / self.total
        progress = int(share * self.DOWNLOAD_SHARE)
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
