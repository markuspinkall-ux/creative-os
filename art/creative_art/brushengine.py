"""Pinsel-Engine von Creative Art: Tupfer-Pinsel wie in Photoshop.

Ein Strich setzt Tupfer der Pinselspitze im eingestellten Abstand. Der
Farbauftrag („Fluss“) sammelt sich in einem Strichpuffer; dieser wird mit der
„Deckkraft“ als Obergrenze auf die Ebene gelegt. So verhalten sich Fluss und
Deckkraft wie in Photoshop.
"""

import math
import os
import random
import shutil
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, QStandardPaths, Qt
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter, QPainterPath

from . import brushes as B

FORMAT = QImage.Format.Format_ARGB32_Premultiplied


# ── Umwandlungen numpy ⇄ QImage ───────────────────────────────────────────

def tip_to_qimage(tip):
    tip = np.ascontiguousarray(tip, dtype=np.uint8)
    h, w = tip.shape
    return QImage(tip.tobytes(), w, h, w, QImage.Format.Format_Alpha8).copy()


def gray_to_qimage(tip):
    tip = np.ascontiguousarray(tip, dtype=np.uint8)
    h, w = tip.shape
    return QImage(tip.tobytes(), w, h, w, QImage.Format.Format_Grayscale8).copy()


def qimage_to_array(image, fmt=QImage.Format.Format_RGBA8888, channels=4):
    image = image.convertToFormat(fmt)
    w, h = image.width(), image.height()
    raw = np.frombuffer(image.constBits(), np.uint8, count=image.sizeInBytes())
    rows = raw.reshape(h, image.bytesPerLine())[:, :w * channels]
    return rows.reshape(h, w, channels).copy() if channels > 1 else rows.reshape(h, w).copy()


def colorize(tip, color):
    """Spitze (Alpha8) in der Farbe einfärben → ARGB-Bild."""
    out = QImage(tip.size(), FORMAT)
    out.fill(QColor(color))
    with QPainter(out) as painter:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, tip)
    return out


# ── Bibliothek ─────────────────────────────────────────────────────────────

def library_dir():
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation) \
        or os.path.expanduser("~/.local/share")
    return Path(base) / "creative-art" / "brushes"


class BrushLibrary:
    """Pinselvorgaben (JSON) und importierte Spitzen (PNG, Graustufen)."""

    def __init__(self, folder=None):
        self.folder = Path(folder) if folder else library_dir()
        self.presets = []
        self._tips = {}
        self.load()

    @property
    def file(self):
        return self.folder / "presets.json"

    def load(self):
        presets = []
        try:
            presets = B.load_library(self.file.read_text(encoding="utf-8"))
        except OSError:
            pass
        defaults = B.default_presets()
        known = {p.id for p in presets}
        # eingebaute Pinsel immer vorne, eigene Änderungen daran bleiben erhalten
        merged = [next((p for p in presets if p.id == d.id), d) for d in defaults]
        merged += [p for p in presets if p.id not in {d.id for d in defaults}
                   and (p.tip == "round" or p.tip.startswith("builtin:") or (self.folder / p.tip).exists())]
        self.presets = merged
        return known

    def save(self):
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            tmp = self.file.with_suffix(".tmp")
            tmp.write_text(B.dump_library(self.presets), encoding="utf-8")
            tmp.replace(self.file)
        except OSError:
            pass

    def is_builtin(self, preset):
        return preset.id in {d.id for d in B.default_presets()}

    def tip(self, preset):
        """Spitze als Alpha8-QImage (zwischengespeichert)."""
        key = f"round:{preset.hardness}" if preset.tip == "round" else preset.tip
        if key not in self._tips:
            if preset.tip == "round":
                arr = B.round_tip(256, preset.hardness)
            elif preset.tip in B.BUILTIN_TIPS:
                arr = B.BUILTIN_TIPS[preset.tip](192)
            else:
                image = QImage(str(self.folder / preset.tip))
                arr = qimage_to_array(image, QImage.Format.Format_Grayscale8, 1) if not image.isNull() \
                    else B.round_tip(64, 100)
            self._tips[key] = tip_to_qimage(arr)
            if len(self._tips) > 64:
                self._tips.pop(next(iter(self._tips)))
        return self._tips[key]

    def add_tip(self, name, arr, source="", size=None, spacing=25):
        arr = B.trim(np.asarray(arr, np.uint8))
        h, w = arr.shape
        if max(h, w) > B.MAX_TIP:
            scaled = gray_to_qimage(arr).scaled(QSize(B.MAX_TIP, B.MAX_TIP), Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation)
            arr = qimage_to_array(scaled, QImage.Format.Format_Grayscale8, 1)
            h, w = arr.shape
        preset = B.Preset(name=name or "Pinsel", source=source, size=int(size or min(max(h, w), 500)),
                          spacing=spacing)
        preset.tip = f"{preset.id}.png"
        self.folder.mkdir(parents=True, exist_ok=True)
        if not gray_to_qimage(arr).save(str(self.folder / preset.tip), "PNG"):
            raise OSError("Die Pinselspitze ließ sich nicht speichern.")
        self.presets.append(preset)
        return preset

    def import_file(self, path):
        """Importiert .abr/.gbr oder ein Bild. Gibt die neuen Vorgaben zurück."""
        path = Path(path)
        source = path.name
        if path.suffix.lower() in (".abr", ".gbr"):
            if path.stat().st_size > 400 * 1024 * 1024:
                raise B.BrushError("Die Pinseldatei ist zu groß (über 400 MB).")
            tips = B.parse_brush_file(path.name, path.read_bytes())
        else:
            reader = QImageReader(str(path))
            reader.setAutoTransform(True)
            image = reader.read()
            if image.isNull():
                raise B.BrushError(f"„{path.name}“ ist kein unterstütztes Bild: {reader.errorString()}")
            rgba = qimage_to_array(image)
            gray = (rgba[:, :, :3].astype(np.float32) @ np.array([.299, .587, .114], np.float32))
            tips = [(path.stem, B.image_to_tip(gray, rgba[:, :, 3]))]
        added = [self.add_tip(name, tip, source) for name, tip in tips[:500]]
        self.save()
        return added

    def remove(self, preset):
        if self.is_builtin(preset):
            return False
        self.presets = [p for p in self.presets if p.id != preset.id]
        if preset.tip not in ("round",) and not preset.tip.startswith("builtin:") \
                and not any(p.tip == preset.tip for p in self.presets):
            try:
                (self.folder / preset.tip).unlink()
            except OSError:
                pass
        self.save()
        return True

    def duplicate(self, preset, name):
        copy = preset.copy(name=name, id=B.Preset().id, source="")
        if copy.tip not in ("round",) and not copy.tip.startswith("builtin:"):
            target = f"{copy.id}.png"
            try:
                shutil.copyfile(self.folder / preset.tip, self.folder / target)
                copy.tip = target
            except OSError:
                pass
        self.presets.append(copy)
        self.save()
        return copy


# ── Strich ─────────────────────────────────────────────────────────────────

class Stroke:
    """Ein Pinselstrich auf `target` (QImage, wird direkt verändert).

    mode: "paint", "erase", "mask_show", "mask_hide" oder "smudge"
    """

    def __init__(self, target, preset, color, library, mode="paint", clip=None, opacity=None, seed=None):
        self.target = target
        self.preset = preset
        self.mode = mode
        self.clip = clip if clip is not None and not clip.isEmpty() else None
        self.opacity = (preset.opacity if opacity is None else opacity) / 100
        self.rng = random.Random(seed)
        tip = library.tip(preset)
        self.tip_size = QSize(tip.width(), tip.height())
        ink = QColor("white") if mode in ("mask_show", "mask_hide") else QColor(color)
        self.stamp = colorize(tip, ink)
        self.mask_tip = tip
        self.base = QImage(target)
        self.buffer = QImage(target.size(), FORMAT)
        self.buffer.fill(Qt.GlobalColor.transparent)
        self.bounds = QRect(QPoint(0, 0), target.size())
        self.last = None
        self.residual = 0.0
        self.direction = 0.0
        self.carry = None
        self.dirty_total = QRect()

    # Größe eines Tupfers in Pixeln
    def dab_size(self, pressure):
        size = self.preset.size * (max(.05, pressure) if self.preset.pressure_size else 1)
        if self.preset.size_jitter:
            size *= 1 - self.rng.random() * self.preset.size_jitter / 100
        return max(1.0, size)

    def add(self, point, pressure=1.0):
        """Strich bis `point` verlängern. Gibt das veränderte Rechteck zurück."""
        point = QPointF(point)
        dirty = QRect()
        with QPainter(self.buffer) as painter:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            if self.last is None:
                dirty |= self._dabs(painter, point, pressure)
                self.last = point
            else:
                dx, dy = point.x() - self.last.x(), point.y() - self.last.y()
                distance = math.hypot(dx, dy)
                if distance > 0:
                    self.direction = math.degrees(math.atan2(dy, dx))
                step = max(.5, self.preset.size * (max(.05, pressure) if self.preset.pressure_size else 1)
                           * self.preset.spacing / 100)
                if self.mode == "smudge":
                    step = max(.5, min(step, self.preset.size * .1))
                travelled = step - self.residual
                while travelled <= distance:
                    t = travelled / distance
                    dirty |= self._dabs(painter, QPointF(self.last.x() + dx * t, self.last.y() + dy * t), pressure)
                    travelled += step
                self.residual = distance - (travelled - step)
                self.last = point
        if not dirty.isEmpty() and self.mode != "smudge":
            self._composite(dirty)
        self.dirty_total |= dirty
        return dirty

    def _dabs(self, painter, center, pressure):
        p = self.preset
        dirty = QRect()
        for _ in range(p.count if self.mode != "smudge" else 1):
            size = self.dab_size(pressure)
            angle = p.angle + (self.direction if p.follow_stroke else 0)
            if p.angle_jitter:
                angle += (self.rng.random() * 2 - 1) * 180 * p.angle_jitter / 100
            roundness = p.roundness / 100
            if p.roundness_jitter:
                roundness *= 1 - self.rng.random() * p.roundness_jitter / 100 * .9
            pos = QPointF(center)
            if p.scatter:
                spread = size * p.scatter / 100
                pos += QPointF((self.rng.random() * 2 - 1) * spread, (self.rng.random() * 2 - 1) * spread)
            alpha = p.flow / 100
            if p.opacity_jitter:
                alpha *= 1 - self.rng.random() * p.opacity_jitter / 100
            if p.pressure_opacity:
                alpha *= max(.05, pressure)
            flip = p.flip_jitter and self.rng.random() < .5
            if self.mode == "smudge":
                dirty |= self._smudge(pos, size, max(.05, alpha))
            else:
                dirty |= self._stamp(painter, pos, size, angle, roundness, alpha, flip)
        return dirty

    def _transform(self, painter, pos, size, angle, roundness, flip):
        tw, th = self.tip_size.width(), self.tip_size.height()
        scale = size / max(tw, th)
        painter.translate(pos)
        painter.rotate(angle)
        painter.scale(scale * (-1 if flip else 1), scale * roundness)
        painter.translate(-tw / 2, -th / 2)

    def _stamp(self, painter, pos, size, angle, roundness, alpha, flip):
        painter.save()
        painter.setOpacity(alpha)
        self._transform(painter, pos, size, angle, roundness, flip)
        painter.drawImage(0, 0, self.stamp)
        painter.restore()
        r = math.ceil(size * .75) + 2                       # Diagonale der gedrehten Spitze
        return QRect(int(pos.x()) - r, int(pos.y()) - r, 2 * r, 2 * r) & self.bounds

    def _composite(self, rect):
        rect = rect.adjusted(-1, -1, 1, 1) & self.bounds
        with QPainter(self.target) as painter:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.drawImage(rect.topLeft(), self.base, rect)
            if self.clip is not None:
                painter.setClipPath(self.clip)
            painter.setOpacity(self.opacity)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_DestinationOut if self.mode in ("erase", "mask_hide")
                else QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.drawImage(rect.topLeft(), self.buffer, rect)

    def _smudge(self, pos, size, strength):
        d = max(2, int(round(size)))
        rect = QRect(int(round(pos.x() - d / 2)), int(round(pos.y() - d / 2)), d, d)
        if self.carry is None or self.carry.size() != rect.size():
            self.carry = self.target.copy(rect).convertToFormat(FORMAT)
            return QRect()
        stamp = QImage(self.carry)
        with QPainter(stamp) as painter:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            painter.drawImage(QRectF(0, 0, d, d), self.mask_tip)
        with QPainter(self.target) as painter:
            if self.clip is not None:
                painter.setClipPath(self.clip)
            painter.setOpacity(strength * self.opacity)
            painter.drawImage(rect.topLeft(), stamp)
        here = self.target.copy(rect).convertToFormat(FORMAT)
        with QPainter(self.carry) as painter:
            painter.setOpacity(1 - strength * .85)
            painter.drawImage(0, 0, here)
        return rect & self.bounds


# ── Fülleimer und Verlauf ─────────────────────────────────────────────────

def bucket_fill(target, x, y, color, tolerance=32, contiguous=True, opacity=1.0, clip=None):
    rgba = qimage_to_array(target)
    region = B.flood_region(rgba, int(x), int(y), int(tolerance), contiguous)
    if not region.any():
        return QRect()
    mask = tip_to_qimage(region.astype(np.uint8) * 255)
    fill = colorize(mask, color)
    with QPainter(target) as painter:
        if clip is not None and not clip.isEmpty():
            painter.setClipPath(clip)
        painter.setOpacity(opacity)
        painter.drawImage(0, 0, fill)
    ys, xs = np.nonzero(region)
    return QRect(int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))


def gradient_fill(target, start, end, color, kind="linear", end_color=None, opacity=1.0, clip=None):
    from PySide6.QtGui import QLinearGradient, QRadialGradient
    a = QColor(color)
    b = QColor(end_color) if end_color is not None else QColor(a.red(), a.green(), a.blue(), 0)
    if kind == "radial":
        radius = max(1.0, math.hypot(end.x() - start.x(), end.y() - start.y()))
        gradient = QRadialGradient(start, radius)
    else:
        gradient = QLinearGradient(start, end)
    gradient.setColorAt(0, a)
    gradient.setColorAt(1, b)
    with QPainter(target) as painter:
        if clip is not None and not clip.isEmpty():
            painter.setClipPath(clip)
        painter.setOpacity(opacity)
        painter.fillRect(target.rect(), gradient)
    return target.rect()


# ── Vorschau eines Pinsels (für die Bibliothek) ───────────────────────────

def preview(preset, library, size=QSize(132, 54), color="#dce6ff"):
    image = QImage(size, FORMAT)
    image.fill(Qt.GlobalColor.transparent)
    p = preset.copy(size=max(4, min(int(size.height() * .55), preset.size)), pressure_size=True)
    stroke = Stroke(image, p, color, library, seed=7)
    w, h = size.width(), size.height()
    steps = 40
    for i in range(steps + 1):
        t = i / steps
        x = 10 + t * (w - 20)
        y = h / 2 + math.sin(t * math.pi * 2) * h * .18
        stroke.add(QPointF(x, y), .35 + .65 * math.sin(t * math.pi))
    return image


def selection_tip(image, path):
    """„Pinsel festlegen“: Auswahl der Ebene als Spitze (dunkel = Farbe)."""
    rect = path.boundingRect().toAlignedRect() & image.rect()
    if rect.isEmpty():
        raise B.BrushError("Wähle zuerst einen Bereich aus.")
    part = QImage(rect.size(), FORMAT)
    part.fill(Qt.GlobalColor.transparent)
    with QPainter(part) as painter:
        clip = QPainterPath(path)
        clip.translate(-rect.x(), -rect.y())
        painter.setClipPath(clip)
        painter.drawImage(QPointF(0, 0), image, QRectF(rect))
    rgba = qimage_to_array(part)
    gray = rgba[:, :, :3].astype(np.float32) @ np.array([.299, .587, .114], np.float32)
    return B.image_to_tip(gray, rgba[:, :, 3])
