"""Thumbnail Studio – Zeichnen und Vorlagen.

Ein Thumbnail ist eine einfache Beschreibung (dict, als JSON gespeichert): Hintergrund,
Bilder, Texte, Rahmen und Sticker. render() zeichnet daraus ein 1280 × 720-Bild (YouTube).
Vorlagen liegen in ~/.local/share/gibeon-thumbnail/vorlagen/<id>/ – mit vorlage.json,
vorschau.png und den benutzten Bildern (kopiert, damit die Vorlage auch dann
funktioniert, wenn die Originale verschoben werden).
"""

import copy
import json
import math
import os
import re
import shutil
import time
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
)

W, H = 1280, 720

BACKGROUNDS = [("farbe", "Einfarbig"), ("verlauf", "Farbverlauf"), ("bild", "Eigenes Bild")]
FRAMES = [("kein", "Kein Rahmen"), ("schlicht", "Schlicht"), ("abgerundet", "Abgerundet"),
          ("neon", "Neon-Leuchten"), ("comic", "Comic-Kante"), ("doppelt", "Doppelte Linie")]
STICKERS = [("neu", "NEU", "#e5484d"), ("live", "LIVE", "#e5484d"), ("teil", "TEIL 2", "#3d6fe0"),
            ("exklusiv", "EXKLUSIV", "#d9a400"), ("tipp", "TIPP", "#1f9e7f"), ("pfeil", "Pfeil", "#ffd400"),
            ("kreis", "Kreis", "#ffd400")]
# Farbvorschläge (kräftig, wie auf YouTube üblich)
SWATCHES = ["#ffffff", "#111111", "#e5484d", "#ffd400", "#2ecc71", "#3d9bff", "#8e44ad", "#ff7a00",
            "#ff3fa4", "#00d1d1"]


def new_design():
    return {
        "version": 1,
        "background": {"type": "verlauf", "color1": "#1d2b64", "color2": "#f8cdda", "angle": 135,
                       "image": "", "blur": 0, "dim": 0},
        "images": [],
        "texts": [],
        "frame": {"style": "kein", "color": "#ffffff", "width": 14},
        "stickers": [],
    }


def new_text(text="DEIN TITEL"):
    return {"text": text, "font": "DejaVu Sans", "size": 110, "color": "#ffffff", "bold": True, "italic": False,
            "outline": 10, "outlineColor": "#111111", "shadow": True, "glow": False, "glowColor": "#ffd400",
            "box": False, "boxColor": "#e5484d", "x": W / 2, "y": H / 2, "rotation": 0, "align": "mitte"}


def new_image(path):
    return {"path": str(path), "x": W * 0.72, "y": H * 0.55, "scale": 1.0, "rotation": 0,
            "outline": False, "outlineColor": "#ffffff", "outlineWidth": 10, "mirror": False}


def new_sticker(kind):
    return {"kind": kind, "x": W * 0.15, "y": H * 0.2, "scale": 1.0, "rotation": -8 if kind != "kreis" else 0}


def sticker_info(kind):
    for k, label, color in STICKERS:
        if k == kind:
            return label, color
    return kind.upper(), "#e5484d"


# ---- Hilfen -------------------------------------------------------------------------
_IMAGE_CACHE = {}


def load_image(path):
    """Bild laden (zwischengespeichert, bei Änderung der Datei neu)."""
    try:
        stamp = os.stat(path).st_mtime
    except OSError:
        return QImage()
    key = (str(path), stamp)
    if key not in _IMAGE_CACHE:
        if len(_IMAGE_CACHE) > 24:
            _IMAGE_CACHE.clear()
        _IMAGE_CACHE[key] = QImage(str(path)).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    return _IMAGE_CACHE[key]


def soften(image, amount):
    """Einfaches Weichzeichnen: verkleinern und wieder vergrößern (schnell, ohne Zusatzpakete)."""
    if amount <= 0 or image.isNull():
        return image
    factor = max(2, int(amount))
    small = image.scaled(max(1, image.width() // factor), max(1, image.height() // factor),
                         Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return small.scaled(image.width(), image.height(), Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)


def cover(image, w, h):
    """Bild füllend zuschneiden (wie „cover“)."""
    scaled = image.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    return scaled.copy((scaled.width() - w) // 2, (scaled.height() - h) // 2, w, h)


def text_font(t):
    font = QFont(t.get("font") or "DejaVu Sans")
    font.setPixelSize(max(8, int(t.get("size", 100))))
    font.setBold(bool(t.get("bold")))
    font.setItalic(bool(t.get("italic")))
    return font


def text_path(t):
    """Textumriss als Pfad, mehrzeilig, um (0, 0) zentriert."""
    font = text_font(t)
    fm = QFontMetricsF(font)
    lines = (t.get("text") or "").split("\n")
    widths = [fm.horizontalAdvance(line) for line in lines]
    width = max(widths or [0])
    line_h = fm.height() * 0.95
    total = line_h * len(lines)
    path = QPainterPath()
    for i, line in enumerate(lines):
        align = t.get("align", "mitte")
        x = {"links": -width / 2, "rechts": width / 2 - widths[i]}.get(align, -widths[i] / 2)
        y = -total / 2 + i * line_h + fm.ascent()
        path.addText(QPointF(x, y), font, line)
    return path


def layer_rect(kind, item):
    """Ungefähre Fläche einer Ebene (für Anklicken/Ziehen in der Vorschau), gedreht nicht berücksichtigt."""
    if kind == "texts":
        r = text_path(item).boundingRect().adjusted(-20, -20, 20, 20)
    elif kind == "images":
        img = load_image(item.get("path", ""))
        w, h = (img.width(), img.height()) if not img.isNull() else (400, 400)
        s = image_scale(img, item)
        r = QRectF(-w * s / 2, -h * s / 2, w * s, h * s)
    else:
        s = 180 * item.get("scale", 1.0)
        r = QRectF(-s, -s * 0.5, 2 * s, s)
    return r.translated(item.get("x", W / 2), item.get("y", H / 2))


def image_scale(img, item):
    if img.isNull():
        return item.get("scale", 1.0)
    base = min(W * 0.6 / img.width(), H * 0.85 / img.height())   # Grundgröße: passt bequem ins Bild
    return base * item.get("scale", 1.0)


# ---- Zeichnen -----------------------------------------------------------------------
_BG_CACHE = {}


def draw_background(p, bg):
    kind = bg.get("type", "farbe")
    if kind == "bild" and bg.get("image"):
        img = load_image(bg["image"])
        if not img.isNull():
            key = (bg["image"], img.cacheKey(), bg.get("blur", 0))
            if key not in _BG_CACHE:                     # Zuschneiden/Weichzeichnen nur bei Änderung
                _BG_CACHE.clear()
                _BG_CACHE[key] = soften(cover(img, W, H), bg.get("blur", 0))
            p.drawImage(0, 0, _BG_CACHE[key])
        else:
            p.fillRect(0, 0, W, H, QColor("#222222"))
    elif kind == "verlauf":
        angle = math.radians(bg.get("angle", 135))
        dx, dy = math.cos(angle) * W / 2, math.sin(angle) * H / 2
        grad = QLinearGradient(W / 2 - dx, H / 2 - dy, W / 2 + dx, H / 2 + dy)
        grad.setColorAt(0, QColor(bg.get("color1", "#000000")))
        grad.setColorAt(1, QColor(bg.get("color2", "#ffffff")))
        p.fillRect(0, 0, W, H, QBrush(grad))
    else:
        p.fillRect(0, 0, W, H, QColor(bg.get("color1", "#1d2b64")))
    dim = max(0, min(90, bg.get("dim", 0)))
    if dim:
        p.fillRect(0, 0, W, H, QColor(0, 0, 0, int(255 * dim / 100)))


def draw_image(p, item):
    img = load_image(item.get("path", ""))
    if img.isNull():
        return
    s = image_scale(img, item)
    w, h = img.width() * s, img.height() * s
    p.save()
    p.translate(item.get("x", W / 2), item.get("y", H / 2))
    p.rotate(item.get("rotation", 0))
    if item.get("mirror"):
        p.scale(-1, 1)
    target = QRectF(-w / 2, -h / 2, w, h)
    if item.get("outline"):
        # Umriss: das Motiv einfarbig in alle Richtungen versetzt darunter (wirkt bei freigestellten PNGs)
        mask = img.scaled(int(w), int(h), Qt.AspectRatioMode.IgnoreAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
        solid = QImage(mask.size(), QImage.Format.Format_ARGB32_Premultiplied)
        solid.fill(QColor(item.get("outlineColor", "#ffffff")))
        mp = QPainter(solid)
        mp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        mp.drawImage(0, 0, mask)
        mp.end()
        width = item.get("outlineWidth", 10)
        for k in range(16):
            a = 2 * math.pi * k / 16
            p.drawImage(QPointF(-w / 2 + math.cos(a) * width, -h / 2 + math.sin(a) * width), solid)
    p.drawImage(target, img)
    p.restore()


def draw_text(p, t):
    path = text_path(t)
    if path.isEmpty():
        return
    p.save()
    p.translate(t.get("x", W / 2), t.get("y", H / 2))
    p.rotate(t.get("rotation", 0))
    rect = path.boundingRect()
    if t.get("box"):
        pad = max(14, t.get("size", 100) * 0.18)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.get("boxColor", "#e5484d")))
        p.drawRoundedRect(rect.adjusted(-pad, -pad * 0.6, pad, pad * 0.6), pad * 0.5, pad * 0.5)
    if t.get("shadow"):
        shadow = QColor(0, 0, 0, 150)
        off = max(4, t.get("size", 100) * 0.06)
        p.setPen(QPen(shadow, max(1, t.get("outline", 0)) * 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                      Qt.PenJoinStyle.RoundJoin))
        p.setBrush(shadow)
        p.drawPath(path.translated(off, off))
    if t.get("glow"):
        glow = QColor(t.get("glowColor", "#ffd400"))
        for width, alpha in ((44, 30), (30, 50), (18, 90)):
            glow.setAlpha(alpha)
            p.setPen(QPen(glow, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
    if t.get("outline", 0) > 0:
        p.setPen(QPen(QColor(t.get("outlineColor", "#111111")), t["outline"] * 2, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(t.get("color", "#ffffff")))
    p.drawPath(path)
    p.restore()


def draw_sticker(p, st):
    label, color = sticker_info(st.get("kind", "neu"))
    p.save()
    p.translate(st.get("x", W / 2), st.get("y", H / 2))
    p.rotate(st.get("rotation", 0))
    s = st.get("scale", 1.0)
    p.scale(s, s)
    col = QColor(st.get("color") or color)
    if st.get("kind") == "pfeil":
        path = QPainterPath()
        path.moveTo(-150, -30)
        path.lineTo(40, -30)
        path.lineTo(40, -80)
        path.lineTo(150, 0)
        path.lineTo(40, 80)
        path.lineTo(40, 30)
        path.lineTo(-150, 30)
        path.closeSubpath()
        p.setPen(QPen(QColor("#111111"), 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(col)
        p.drawPath(path)
    elif st.get("kind") == "kreis":
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#111111"), 26))
        p.drawEllipse(QRectF(-170, -110, 340, 220))
        p.setPen(QPen(col, 14))
        p.drawEllipse(QRectF(-170, -110, 340, 220))
    else:
        font = QFont("DejaVu Sans")
        font.setPixelSize(64)
        font.setBold(True)
        fm = QFontMetricsF(font)
        tw = fm.horizontalAdvance(label)
        rect = QRectF(-tw / 2 - 30, -50, tw + 60, 100)
        p.setPen(QPen(QColor("#ffffff"), 8))
        p.setBrush(col)
        p.drawRoundedRect(rect, 22, 22)
        path = QPainterPath()
        path.addText(QPointF(-tw / 2, fm.ascent() / 2 - 6), font, label)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawPath(path)
    p.restore()


def draw_frame(p, fr):
    style = fr.get("style", "kein")
    if style == "kein":
        return
    col = QColor(fr.get("color", "#ffffff"))
    w = max(2, fr.get("width", 14))
    p.setBrush(Qt.BrushStyle.NoBrush)
    if style == "schlicht":
        p.setPen(QPen(col, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
        p.drawRect(QRectF(w / 2, w / 2, W - w, H - w))
    elif style == "abgerundet":
        # Ecken außen in Rahmenfarbe füllen, innen runde Kante
        outer = QPainterPath()
        outer.addRect(QRectF(0, 0, W, H))
        inner = QPainterPath()
        inner.addRoundedRect(QRectF(w, w, W - 2 * w, H - 2 * w), 46, 46)
        p.fillPath(outer.subtracted(inner), col)
    elif style == "neon":
        for width, alpha in ((w * 4, 30), (w * 2.5, 60), (w * 1.4, 120)):
            c = QColor(col)
            c.setAlpha(alpha)
            p.setPen(QPen(c, width))
            p.drawRoundedRect(QRectF(w * 1.6, w * 1.6, W - w * 3.2, H - w * 3.2), 30, 30)
        p.setPen(QPen(QColor(255, 255, 255, 230), max(2, w * 0.35)))
        p.drawRoundedRect(QRectF(w * 1.6, w * 1.6, W - w * 3.2, H - w * 3.2), 30, 30)
    elif style == "comic":
        p.setPen(QPen(QColor("#111111"), w * 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
        p.drawRect(QRectF(w * 0.9, w * 0.9, W - w * 1.8, H - w * 1.8))
        p.setPen(QPen(col, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
        p.drawRect(QRectF(w * 0.5, w * 0.5, W - w, H - w))
    elif style == "doppelt":
        p.setPen(QPen(col, max(2, w * 0.5)))
        p.drawRect(QRectF(w * 0.5, w * 0.5, W - w, H - w))
        p.drawRect(QRectF(w * 1.8, w * 1.8, W - w * 3.6, H - w * 3.6))


def render(design, size=None):
    """Zeichnet das Thumbnail (1280 × 720) und gibt ein QImage zurück; size verkleinert danach."""
    image = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#000000"))
    p = QPainter(image)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
                     | QPainter.RenderHint.TextAntialiasing)
    draw_background(p, design.get("background", {}))
    for item in design.get("images", []):
        draw_image(p, item)
    for st in design.get("stickers", []):
        draw_sticker(p, st)
    for t in design.get("texts", []):
        draw_text(p, t)
    draw_frame(p, design.get("frame", {}))
    p.end()
    if size:
        return image.scaled(size[0], size[1], Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
    return image


# ---- Vorlagen -----------------------------------------------------------------------
def templates_dir():
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "gibeon-thumbnail" / "vorlagen"


def _slug(name):
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().replace("ä", "ae").replace("ö", "oe")
                  .replace("ü", "ue").replace("ß", "ss")).strip("-")
    return slug[:40] or "vorlage"


def list_templates():
    """Eigene Vorlagen, neueste zuerst: [{id, name, dir, preview, changed}]."""
    out = []
    root = templates_dir()
    if not root.is_dir():
        return out
    for d in root.iterdir():
        f = d / "vorlage.json"
        if not f.is_file():
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({"id": d.name, "name": data.get("name") or d.name, "dir": str(d),
                    "preview": str(d / "vorschau.png"), "changed": data.get("changed", f.stat().st_mtime)})
    out.sort(key=lambda t: t["changed"], reverse=True)
    return out


def save_template(design, name, template_id=None):
    """Speichert das Design als Vorlage (benutzte Bilder werden mitkopiert). Gibt die ID zurück."""
    root = templates_dir()
    root.mkdir(parents=True, exist_ok=True)
    tid = template_id or f"{_slug(name)}-{int(time.time())}"
    folder = root / tid
    folder.mkdir(parents=True, exist_ok=True)
    data = copy.deepcopy(design)
    keep = set()

    def own(path):
        if not path:
            return path
        src = Path(path)
        if src.parent == folder:
            keep.add(src.name)
            return src.name
        if not src.is_file():
            return path
        n = len(keep) + 1
        target = folder / f"bild-{n}{src.suffix.lower() or '.png'}"
        while target.name in keep or target.exists():
            n += 1
            target = folder / f"bild-{n}{src.suffix.lower() or '.png'}"
        shutil.copyfile(src, target)
        keep.add(target.name)
        return target.name

    data["background"]["image"] = own(data["background"].get("image", ""))
    for item in data.get("images", []):
        item["path"] = own(item.get("path", ""))
    data["name"] = name.strip() or "Vorlage"
    data["changed"] = time.time()
    tmp = folder / "vorlage.json.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(folder / "vorlage.json")
    render(load_template(tid), (640, 360)).save(str(folder / "vorschau.png"))
    for old in folder.glob("bild-*"):                   # nicht mehr benutzte Bilder entfernen
        if old.name not in keep:
            old.unlink(missing_ok=True)
    return tid


def load_template(template_id):
    """Vorlage laden; Bildpfade zeigen dann wieder auf die Dateien im Vorlagenordner."""
    folder = templates_dir() / template_id
    data = json.loads((folder / "vorlage.json").read_text(encoding="utf-8"))
    base = new_design()
    for key in base:
        data.setdefault(key, base[key])

    def full(path):
        return str(folder / path) if path and not os.path.isabs(path) else (path or "")

    data["background"]["image"] = full(data["background"].get("image", ""))
    for item in data.get("images", []):
        item["path"] = full(item.get("path", ""))
    return data


def delete_template(template_id):
    folder = templates_dir() / template_id
    if folder.parent == templates_dir() and folder.is_dir():
        shutil.rmtree(folder)


def rename_template(template_id, name):
    f = templates_dir() / template_id / "vorlage.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    data["name"] = name.strip() or data.get("name", "Vorlage")
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
