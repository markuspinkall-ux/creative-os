"""Pinselspitzen für Creative Art – ohne Qt, damit es sich überall testen lässt.

- Photoshop-Pinsel (.abr, Version 1, 2 und 6–10, „sampled brushes“)
- GIMP-Pinsel (.gbr, Version 1 und 2)
- eingebaute Spitzen (rund, weich, Kreide, Kohle, Spritzer, Borsten …)
- Fülleimer (zusammenhängende Fläche mit Toleranz)

Eine Spitze ist ein numpy-Array (Höhe × Breite, uint8): 255 = volle Farbe.
"""

import json
import math
import struct
import uuid
import zlib
from dataclasses import asdict, dataclass, field, fields

import numpy as np

MAX_TIP = 2500          # größere Spitzen werden beim Import verkleinert (in der Qt-Schicht)


class BrushError(ValueError):
    pass


# ── Einstellungen eines Pinsels ────────────────────────────────────────────

@dataclass
class Preset:
    name: str = "Rund hart"
    tip: str = "round"          # "round" (berechnet) oder Dateiname der Spitze in der Bibliothek
    size: int = 24              # Durchmesser in Pixeln
    hardness: int = 100         # nur für runde Spitzen, 0–100
    opacity: int = 100          # Höchstdeckkraft pro Strich, 0–100
    flow: int = 100             # Farbauftrag pro Tupfer, 0–100
    spacing: int = 10           # Abstand der Tupfer in % der Größe, 1–1000
    angle: int = 0              # Grad
    roundness: int = 100        # 1–100 (100 = nicht gestaucht)
    size_jitter: int = 0        # 0–100 %
    angle_jitter: int = 0       # 0–100 % (100 = ±180°)
    roundness_jitter: int = 0   # 0–100 %
    scatter: int = 0            # 0–1000 % der Größe
    count: int = 1              # Tupfer pro Schritt, 1–16
    opacity_jitter: int = 0     # 0–100 %
    pressure_size: bool = True  # Stiftdruck steuert Größe
    pressure_opacity: bool = False
    follow_stroke: bool = False  # Spitze dreht sich mit der Strichrichtung
    flip_jitter: bool = False
    source: str = ""            # Herkunft, z. B. „meine.abr“
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @classmethod
    def from_dict(cls, data):
        known = {f.name for f in fields(cls)}
        values = {k: v for k, v in dict(data).items() if k in known}
        preset = cls(**values)
        preset.clamp()
        return preset

    def to_dict(self):
        return asdict(self)

    def clamp(self):
        def lim(value, low, high, kind=int):
            try:
                return max(low, min(high, kind(value)))
            except (TypeError, ValueError):
                return low
        self.size = lim(self.size, 1, 2500)
        self.hardness = lim(self.hardness, 0, 100)
        self.opacity = lim(self.opacity, 1, 100)
        self.flow = lim(self.flow, 1, 100)
        self.spacing = lim(self.spacing, 1, 1000)
        self.angle = lim(self.angle, -360, 360)
        self.roundness = lim(self.roundness, 1, 100)
        self.size_jitter = lim(self.size_jitter, 0, 100)
        self.angle_jitter = lim(self.angle_jitter, 0, 100)
        self.roundness_jitter = lim(self.roundness_jitter, 0, 100)
        self.scatter = lim(self.scatter, 0, 1000)
        self.count = lim(self.count, 1, 16)
        self.opacity_jitter = lim(self.opacity_jitter, 0, 100)
        for key in ("pressure_size", "pressure_opacity", "follow_stroke", "flip_jitter"):
            setattr(self, key, bool(getattr(self, key)))
        self.name = str(self.name or "Pinsel")[:80]
        self.tip = str(self.tip or "round")
        return self

    def copy(self, **changes):
        data = self.to_dict()
        data.update(changes)
        return Preset.from_dict(data)


# ── eingebaute Spitzen ─────────────────────────────────────────────────────

def round_tip(diameter=128, hardness=100):
    """Runde Spitze; Härte 100 = scharfe Kante, 0 = ganz weich."""
    d = max(2, int(diameter))
    r = d / 2
    y, x = np.mgrid[0:d, 0:d]
    dist = np.hypot(x + .5 - r, y + .5 - r) / r            # 0 Mitte … 1 Rand
    h = max(0.0, min(1.0, hardness / 100))
    if h >= .999:
        alpha = np.clip((1 - dist) * r, 0, 1)                # 1 px Kantenglättung
    else:
        inner = h
        t = np.clip((dist - inner) / max(1e-6, 1 - inner), 0, 1)
        alpha = np.where(dist <= inner, 1.0, (1 + np.cos(t * math.pi)) / 2)
        alpha = np.where(dist >= 1, 0, alpha)
    return (alpha * 255).astype(np.uint8)


def _noise(shape, seed):
    return np.random.default_rng(seed).random(shape)


def chalk_tip(d=128, seed=3):
    base = round_tip(d, 60).astype(float) / 255
    grain = _noise((d, d), seed)
    return (np.clip(base * (grain > .45) * (.6 + .4 * grain), 0, 1) * 255).astype(np.uint8)


def charcoal_tip(d=128, seed=5):
    y, x = np.mgrid[0:d, 0:d]
    ellipse = ((x - d / 2) / (d / 2)) ** 2 + ((y - d / 2) / (d / 5)) ** 2
    base = np.clip(1 - ellipse, 0, 1) ** .6
    streaks = _noise((d, 1), seed) * np.ones((1, d))
    grain = _noise((d, d), seed + 1)
    return (np.clip(base * (.35 + .65 * streaks) * (grain > .3), 0, 1) * 255).astype(np.uint8)


def splatter_tip(d=128, seed=7, dots=38):
    rng = np.random.default_rng(seed)
    out = np.zeros((d, d), float)
    y, x = np.mgrid[0:d, 0:d]
    for _ in range(dots):
        angle, dist = rng.random() * 2 * math.pi, (rng.random() ** .7) * d * .45
        cx, cy = d / 2 + math.cos(angle) * dist, d / 2 + math.sin(angle) * dist
        rr = max(1.2, rng.random() * d * .09 * (1 - dist / d))
        out = np.maximum(out, np.clip(rr - np.hypot(x - cx, y - cy), 0, 1))
    return (out * 255).astype(np.uint8)


def bristle_tip(d=128, seed=11, hairs=26):
    rng = np.random.default_rng(seed)
    out = np.zeros((d, d), float)
    y, x = np.mgrid[0:d, 0:d]
    for _ in range(hairs):
        cx, cy = d / 2 + (rng.random() - .5) * d * .8, d / 2 + (rng.random() - .5) * d * .25
        rr = d * (.025 + rng.random() * .03)
        out = np.maximum(out, np.clip(rr - np.hypot(x - cx, y - cy), 0, 1) * (.5 + .5 * rng.random()))
    return (out * 255).astype(np.uint8)


def leaf_tip(d=128):
    y, x = np.mgrid[0:d, 0:d]
    u, v = (x - d / 2) / (d / 2), (y - d / 2) / (d / 2)
    shape = (u ** 2) / .16 + (v ** 2) / .9 <= 1 - .15 * v
    vein = np.abs(u) < .03
    return ((shape & ~vein) * 255).astype(np.uint8)


def star_tip(d=128):
    y, x = np.mgrid[0:d, 0:d]
    u, v = (x - d / 2) / (d / 2), (y - d / 2) / (d / 2)
    angle = np.arctan2(v, u)
    radius = np.hypot(u, v)
    edge = .45 + .5 * (np.cos(5 * angle) + 1) / 2
    return (np.clip((edge - radius) * d / 2, 0, 1) * 255).astype(np.uint8)


BUILTIN_TIPS = {
    "builtin:chalk": chalk_tip, "builtin:charcoal": charcoal_tip, "builtin:splatter": splatter_tip,
    "builtin:bristle": bristle_tip, "builtin:leaf": leaf_tip, "builtin:star": star_tip,
}


def default_presets():
    P = Preset
    return [
        P(name="Rund hart", tip="round", size=24, hardness=100, spacing=8, id="rund-hart"),
        P(name="Rund weich", tip="round", size=60, hardness=0, spacing=8, id="rund-weich"),
        P(name="Airbrush", tip="round", size=120, hardness=0, flow=8, spacing=5, id="airbrush"),
        P(name="Tinte", tip="round", size=10, hardness=100, spacing=4, pressure_size=True, id="tinte"),
        P(name="Bleistift", tip="round", size=4, hardness=90, opacity=85, spacing=10, id="bleistift"),
        P(name="Kreide", tip="builtin:chalk", size=50, spacing=18, angle_jitter=100, opacity=90, id="kreide"),
        P(name="Kohle", tip="builtin:charcoal", size=40, spacing=12, follow_stroke=True, flow=70, id="kohle"),
        P(name="Borsten", tip="builtin:bristle", size=56, spacing=6, follow_stroke=True, flow=60, id="borsten"),
        P(name="Spritzer", tip="builtin:splatter", size=120, spacing=60, angle_jitter=100, size_jitter=40,
          scatter=60, id="spritzer"),
        P(name="Laub", tip="builtin:leaf", size=48, spacing=55, angle_jitter=100, size_jitter=50, scatter=120,
          count=2, roundness_jitter=40, opacity_jitter=30, id="laub"),
        P(name="Sterne", tip="builtin:star", size=36, spacing=90, size_jitter=70, scatter=200, angle_jitter=40,
          opacity_jitter=50, id="sterne"),
    ]


# ── Photoshop .abr ─────────────────────────────────────────────────────────

class _Reader:
    def __init__(self, data, pos=0):
        self.data, self.pos = data, pos

    def take(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise BrushError("Die Pinseldatei ist unvollständig.")
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def u8(self):
        return self.take(1)[0]

    def u16(self):
        return struct.unpack(">H", self.take(2))[0]

    def s16(self):
        return struct.unpack(">h", self.take(2))[0]

    def u32(self):
        return struct.unpack(">I", self.take(4))[0]

    def s32(self):
        return struct.unpack(">i", self.take(4))[0]

    def skip(self, n):
        self.take(n)


def _packbits(reader, height, row_bytes):
    """PackBits mit vorangestellten Zeilenlängen (wie in PSD/ABR)."""
    lengths = [reader.u16() for _ in range(height)]
    out = bytearray()
    for length in lengths:
        row = reader.take(length)
        line = bytearray()
        i = 0
        while i < len(row) and len(line) < row_bytes:
            n = row[i] - 256 if row[i] > 127 else row[i]
            i += 1
            if n == -128:
                continue
            if n < 0:
                if i >= len(row):
                    break
                line.extend(bytes([row[i]]) * (1 - n))
                i += 1
            else:
                line.extend(row[i:i + n + 1])
                i += n + 1
        line = line[:row_bytes]
        line.extend(b"\0" * (row_bytes - len(line)))
        out.extend(line)
    return bytes(out)


def _sampled(reader, name):
    top, left, bottom, right = reader.s32(), reader.s32(), reader.s32(), reader.s32()
    depth = reader.u16()
    compressed = reader.u8()
    width, height = right - left, bottom - top
    if not (0 < width <= 30000 and 0 < height <= 30000) or depth not in (8, 16):
        raise BrushError("Unbekanntes Pinselformat in der Datei.")
    bpp = depth // 8
    row_bytes = width * bpp
    raw = _packbits(reader, height, row_bytes) if compressed else reader.take(row_bytes * height)
    data = np.frombuffer(raw, np.uint8 if bpp == 1 else ">u2").reshape(height, width)
    if bpp == 2:
        data = (data >> 8).astype(np.uint8)
    return name, np.ascontiguousarray(data, dtype=np.uint8)


def _ucs2(reader):
    count = reader.u32()
    if count > 4096:
        raise BrushError("Ungültiger Pinselname.")
    return reader.take(count * 2).decode("utf-16-be", "replace").rstrip("\0")


def _abr_v12(reader, version, stem):
    count = reader.u16()
    tips = []
    for index in range(count):
        kind = reader.u16()
        size = reader.u32()
        end = reader.pos + size
        if kind == 2:
            reader.skip(6)                           # Diverses + Abstand
            name = _ucs2(reader) if version == 2 else ""
            reader.skip(9)                           # Glättung + kurze Grenzen
            tips.append(_sampled(reader, name or f"{stem} {index + 1}"))
        reader.pos = end                             # berechnete Pinsel (1) überspringen
    return tips


def _abr_sections(data, start):
    """8BIM-Abschnitte ab start: {Schlüssel: (Anfang, Ende)}"""
    sections, pos = {}, start
    while pos + 12 <= len(data):
        if data[pos:pos + 4] != b"8BIM":
            break
        key = data[pos + 4:pos + 8].decode("latin-1")
        size = struct.unpack(">I", data[pos + 8:pos + 12])[0]
        sections.setdefault(key, (pos + 12, min(len(data), pos + 12 + size)))
        pos += 12 + size
    return sections


def _abr_names(data, start, end):
    """Namen der Pinselvorgaben aus dem Beschreibungsblock: {UUID: Name}"""
    names, block = {}, data[start:end]
    marks = []
    pos = block.find(b"Nm  TEXT")
    while pos >= 0:
        marks.append(pos)
        pos = block.find(b"Nm  TEXT", pos + 8)
    for i, mark in enumerate(marks):
        try:
            r = _Reader(block, mark + 8)
            name = _ucs2(r)
        except BrushError:
            continue
        stop = marks[i + 1] if i + 1 < len(marks) else len(block)
        link = block.find(b"sampledDataTEXT", mark, stop)
        if link >= 0:
            try:
                uid = _ucs2(_Reader(block, link + 15))
            except BrushError:
                continue
            names.setdefault(uid, name)
    return names


def _abr_v6(data, subversion, stem):
    sections = _abr_sections(data, 4)
    if "samp" not in sections:
        raise BrushError("Diese .abr-Datei enthält keine Bild-Pinsel (nur berechnete Spitzen).")
    names = _abr_names(data, *sections["desc"]) if "desc" in sections else {}
    start, end = sections["samp"]
    reader = _Reader(data, start)
    tips = []
    while reader.pos + 4 <= end:
        size = reader.u32()
        next_brush = reader.pos + size + (-size % 4)
        if size == 0:
            break
        try:
            key_len = data[reader.pos]
            uid = data[reader.pos + 1:reader.pos + 1 + key_len].decode("latin-1", "replace")
            reader.skip(47 if subversion == 1 else 301)
            tips.append(_sampled(reader, names.get(uid) or f"{stem} {len(tips) + 1}"))
        except (BrushError, struct.error):
            pass                                     # einzelner kaputter Pinsel: weitermachen
        reader.pos = next_brush
    return tips


def parse_abr(data, stem="Pinsel"):
    """Gibt [(Name, Spitze)] zurück. Spitze: uint8-Array, 255 = Farbe."""
    if len(data) < 4:
        raise BrushError("Das ist keine Photoshop-Pinseldatei.")
    version, sub = struct.unpack(">HH", data[:4])
    if version in (1, 2):
        tips = _abr_v12(_Reader(data, 2), version, stem)
    elif 6 <= version <= 10:
        tips = _abr_v6(data, sub, stem)
    else:
        raise BrushError(f"Photoshop-Pinsel der Version {version} werden nicht unterstützt.")
    tips = [(name, tip) for name, tip in tips if tip.size and tip.max() > 0]
    if not tips:
        raise BrushError("In der Datei wurden keine verwendbaren Pinsel gefunden.")
    return tips


# ── GIMP .gbr ──────────────────────────────────────────────────────────────

def parse_gbr(data, stem="Pinsel"):
    if len(data) < 28:
        raise BrushError("Das ist keine GIMP-Pinseldatei.")
    header_size, version, width, height, depth = struct.unpack(">IIIII", data[:20])
    if version not in (1, 2) or depth not in (1, 4) or not (0 < width <= 30000 and 0 < height <= 30000):
        raise BrushError("Unbekanntes GIMP-Pinselformat.")
    if version == 2 and data[20:24] != b"GIMP":
        raise BrushError("Unbekanntes GIMP-Pinselformat.")
    name_start = 28 if version == 2 else 20
    name = data[name_start:header_size].split(b"\0")[0].decode("utf-8", "replace").strip() or stem
    body = data[header_size:header_size + width * height * depth]
    if len(body) < width * height * depth:
        raise BrushError("Die Pinseldatei ist unvollständig.")
    pixels = np.frombuffer(body, np.uint8).reshape(height, width, depth)
    tip = pixels[:, :, 0] if depth == 1 else pixels[:, :, 3]
    return [(name, np.ascontiguousarray(tip))]


def parse_brush_file(name, data):
    stem = name.rsplit("/", 1)[-1].rsplit(".", 1)[0] or "Pinsel"
    lower = name.lower()
    if lower.endswith(".abr"):
        return parse_abr(data, stem)
    if lower.endswith(".gbr"):
        return parse_gbr(data, stem)
    raise BrushError("Unterstützt werden Photoshop (.abr), GIMP (.gbr) und Bilder (.png, .jpg).")


def image_to_tip(gray, alpha):
    """Bild als Spitze: dunkel = Farbe, durchsichtig = nichts (wie in Photoshop „Pinsel festlegen“)."""
    gray = np.asarray(gray, np.float32)
    alpha = np.asarray(alpha, np.float32) / 255
    tip = (255 - gray) * alpha
    if tip.max() < 8 and alpha.min() < .99:          # weiße Form auf Transparenz: Alphakanal nehmen
        tip = alpha * 255
    return np.clip(tip, 0, 255).astype(np.uint8)


def trim(tip, pad=2):
    """Leeren Rand abschneiden."""
    rows, cols = np.nonzero(tip.max(axis=1) > 0)[0], np.nonzero(tip.max(axis=0) > 0)[0]
    if not len(rows) or not len(cols):
        return tip
    top, bottom = max(0, rows[0] - pad), min(tip.shape[0], rows[-1] + 1 + pad)
    left, right = max(0, cols[0] - pad), min(tip.shape[1], cols[-1] + 1 + pad)
    return np.ascontiguousarray(tip[top:bottom, left:right])


# ── Bibliothek (Einstellungen als JSON) ────────────────────────────────────

def load_library(text):
    try:
        data = json.loads(text)
        items = data.get("presets", []) if isinstance(data, dict) else []
        presets = [Preset.from_dict(item) for item in items if isinstance(item, dict)]
    except (ValueError, TypeError):
        presets = []
    return presets


def dump_library(presets):
    return json.dumps({"version": 1, "presets": [p.to_dict() for p in presets]}, ensure_ascii=False, indent=1)


# ── Fülleimer ──────────────────────────────────────────────────────────────

def flood_region(rgba, x, y, tolerance=32, contiguous=True):
    """Bool-Maske der Fläche um (x, y), deren Farbe höchstens `tolerance` (0–255) abweicht."""
    h, w = rgba.shape[:2]
    if not (0 <= x < w and 0 <= y < h):
        return np.zeros((h, w), bool)
    pix = rgba.astype(np.int16)
    diff = np.abs(pix - pix[y, x]).max(axis=2)
    similar = diff <= tolerance
    if not contiguous:
        return similar
    out = np.zeros((h, w), bool)
    stack = [(x, y)]
    while stack:
        sx, sy = stack.pop()
        if out[sy, sx] or not similar[sy, sx]:
            continue
        row = similar[sy]
        left = sx
        while left > 0 and row[left - 1]:
            left -= 1
        right = sx
        while right < w - 1 and row[right + 1]:
            right += 1
        out[sy, left:right + 1] = True
        for ny in (sy - 1, sy + 1):
            if 0 <= ny < h:
                seg = similar[ny, left:right + 1] & ~out[ny, left:right + 1]
                if seg.any():
                    # Anfang jedes zusammenhängenden Stücks in der Nachbarzeile
                    idx = np.flatnonzero(seg)
                    starts = idx[np.concatenate(([True], np.diff(idx) > 1))]
                    stack.extend((left + int(s), ny) for s in starts)
    return out


# ── Hilfen für Tests: eine minimale .abr schreiben ────────────────────────

def _packbits_encode(row):
    out, i, n = bytearray(), 0, len(row)
    while i < n:
        j = i
        while j + 1 < n and row[j + 1] == row[i] and j - i < 127:
            j += 1
        if j > i:
            out += bytes([(257 - (j - i + 1)) & 0xFF, row[i]])
            i = j + 1
        else:
            start = i
            i += 1
            while i < n and i - start < 128 and not (i + 1 < n and row[i + 1] == row[i]):
                i += 1
            out += bytes([i - start - 1]) + bytes(row[start:i])
    return bytes(out)


def _sampled_bytes(tip, compress):
    h, w = tip.shape
    head = struct.pack(">iiiiHB", 0, 0, h, w, 8, 1 if compress else 0)
    if not compress:
        return head + tip.tobytes()
    rows = [_packbits_encode(bytes(r)) for r in tip]
    return head + b"".join(struct.pack(">H", len(r)) for r in rows) + b"".join(rows)


def write_test_abr(tips, version=6, names=None, compress=True):
    """Schreibt eine einfache .abr (nur für Tests)."""
    names = names or [f"Test {i + 1}" for i in range(len(tips))]
    if version in (1, 2):
        out = bytearray(struct.pack(">HH", version, len(tips)))
        for name, tip in zip(names, tips):
            body = b"\0" * 6
            if version == 2:
                text = (name + "\0").encode("utf-16-be")
                body += struct.pack(">I", len(text) // 2) + text
            body += b"\0" * 9 + _sampled_bytes(tip, compress)
            out += struct.pack(">HI", 2, len(body)) + body
        return bytes(out)
    samp, desc = bytearray(), bytearray()
    for name, tip in zip(names, tips):
        uid = "$" + str(uuid.uuid4())[:35]
        body = bytes([36]) + uid.encode().ljust(36, b"0")[:36] + b"\0" * (301 - 37) + _sampled_bytes(tip, compress)
        samp += struct.pack(">I", len(body)) + body + b"\0" * (-len(body) % 4)
        text = (name + "\0").encode("utf-16-be")
        link = (uid + "\0").encode("utf-16-be")
        desc += (b"\0\0\0\0Nm  TEXT" + struct.pack(">I", len(text) // 2) + text
                 + struct.pack(">I", 11) + b"sampledDataTEXT" + struct.pack(">I", len(link) // 2) + link)
    out = bytearray(struct.pack(">HH", version, 2))
    out += b"8BIMsamp" + struct.pack(">I", len(samp)) + samp
    out += b"8BIMdesc" + struct.pack(">I", len(desc)) + desc
    return bytes(out)


def write_test_gbr(tip, name="Test"):
    h, w = tip.shape
    text = name.encode() + b"\0"
    header = struct.pack(">IIIII", 28 + len(text), 2, w, h, 1) + b"GIMP" + struct.pack(">I", 25)
    return header + text + tip.tobytes()


def checksum(tip):
    return zlib.crc32(np.ascontiguousarray(tip).tobytes())
