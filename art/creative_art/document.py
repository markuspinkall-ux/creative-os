"""Layered raster documents and the Creative Art project format."""

import json
import os
import tempfile
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path

from PIL import Image, ImageFilter

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QPointF, QRect, QSaveFile, QSize, Qt
from PySide6.QtGui import QImage, QImageReader, QPainter, QPainterPath, QTransform

MAX_SIDE = 8192
MAX_LAYER_BYTES = 256 * 1024 * 1024
MAX_LAYERS = 32
HISTORY_BYTES = 128 * 1024 * 1024
FORMAT = QImage.Format.Format_ARGB32_Premultiplied


def check_size(size, count=1, max_layers=MAX_LAYERS):
    if (not 1 <= size.width() <= MAX_SIDE or not 1 <= size.height() <= MAX_SIDE
            or not 1 <= count <= max_layers
            or size.width() * size.height() * count * 4 > MAX_LAYER_BYTES):
        raise ValueError("Bild oder Ebenenstapel ist zu groß.")


def transparent(size):
    image = QImage(size, FORMAT)
    if image.isNull():
        raise ValueError("Bildspeicher konnte nicht angelegt werden.")
    image.fill(Qt.GlobalColor.transparent)
    return image


def read_image(reader):
    check_size(reader.size())
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        raise ValueError(reader.errorString())
    image.setDevicePixelRatio(1)
    return image.convertToFormat(FORMAT)


@dataclass
class Layer:
    name: str
    image: QImage
    visible: bool = True
    opacity: int = 100
    mask: QImage | None = None

    def rendered(self):
        if self.mask is None:
            return self.image
        result = self.image.copy()
        apply_alpha(result, self.mask)
        return result

    def transformed(self, matrix):
        def raster(source):
            result = transparent(source.size())
            with QPainter(result) as painter:
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                painter.setTransform(matrix)
                painter.drawImage(0, 0, source)
            return result

        return replace(self, image=raster(self.image), mask=raster(self.mask) if self.mask is not None else None)


def apply_alpha(image, mask, remove=False, offset=QPointF()):
    with QPainter(image) as painter:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut if remove
                                   else QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(offset, mask)


def layer_bounds(image):
    alpha = image.convertToFormat(QImage.Format.Format_Alpha8)
    values = Image.frombytes("L", (alpha.width(), alpha.height()), bytes(alpha.constBits()),
                             "raw", "L", alpha.bytesPerLine(), 1)
    box = values.getbbox()
    if box is None:
        return image.rect()
    x, y, right, bottom = box
    return QRect(x, y, right - x, bottom - y)


def layer_matrix(center, offset, width, height, angle, flip_x=False, flip_y=False):
    matrix = QTransform()
    matrix.translate(center.x() + offset.x(), center.y() + offset.y())
    matrix.rotate(angle)
    matrix.scale(-width if flip_x else width, -height if flip_y else height)
    matrix.translate(-center.x(), -center.y())
    return matrix


class Document:
    def __init__(self, image, name="Ebene 1"):
        check_size(image.size())
        self.layers = [Layer(name, image)]
        self.active = 0
        self.selection = QPainterPath()
        self.feather = 0
        self.undo = []
        self.redo = []
        self.version = self.saved_version = self.next_version = 0

    @property
    def size(self):
        return self.layers[0].image.size()

    @property
    def layer(self):
        return self.layers[self.active]

    @property
    def modified(self):
        return self.version != self.saved_version

    def snapshot(self):
        return ([replace(layer, image=QImage(layer.image),
                         mask=QImage(layer.mask) if layer.mask is not None else None) for layer in self.layers],
                self.active, QPainterPath(self.selection), self.version)

    def restore(self, state):
        self.layers, self.active, self.selection, self.version = state

    def checkpoint(self):
        self.undo.append(self.snapshot())
        self.redo.clear()
        self.next_version += 1
        self.version = self.next_version
        # Count each shared Qt raster only once across the retained snapshots.
        def retained_bytes():
            rasters = {image.cacheKey(): image.sizeInBytes()
                       for layers, *_ in self.undo for layer in layers
                       for image in (layer.image, layer.mask) if image is not None}
            return sum(rasters.values())

        while len(self.undo) > 1 and (len(self.undo) > 24 or retained_bytes() > HISTORY_BYTES):
            self.undo.pop(0)

    def step(self, backwards):
        source, target = (self.undo, self.redo) if backwards else (self.redo, self.undo)
        if source:
            target.append(self.snapshot())
            self.restore(source.pop())

    def render(self, bounds=None, selection=False):
        bounds = QRect(bounds) if bounds is not None else QRect(0, 0, self.size.width(), self.size.height())
        result = transparent(bounds.size())
        with QPainter(result) as painter:
            painter.translate(-bounds.x(), -bounds.y())
            for layer in self.layers:
                if layer.visible:
                    painter.setOpacity(layer.opacity / 100)
                    painter.drawImage(0, 0, layer.rendered())
        if selection and not self.selection.isEmpty():
            apply_alpha(result, self.selection_mask(bounds))
        return result

    def selection_bounds(self, feathered=False):
        canvas = self.layer.image.rect()
        if self.selection.isEmpty():
            return QRect()
        margin = 3 * self.feather if feathered else 0
        return self.selection.boundingRect().toAlignedRect().adjusted(
            -margin, -margin, margin, margin).intersected(canvas)

    def selection_mask(self, bounds):
        mask = transparent(bounds.size())
        if self.selection.isEmpty():
            mask.fill(Qt.GlobalColor.white)
            return mask
        with QPainter(mask) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.translate(-bounds.x(), -bounds.y())
            painter.fillPath(self.selection, Qt.GlobalColor.white)
        if not self.feather:
            return mask
        alpha = mask.convertToFormat(QImage.Format.Format_Alpha8)
        values = Image.frombytes("L", (alpha.width(), alpha.height()), bytes(alpha.constBits()),
                                 "raw", "L", alpha.bytesPerLine(), 1)
        data = values.filter(ImageFilter.GaussianBlur(self.feather)).tobytes()
        return QImage(data, alpha.width(), alpha.height(), alpha.width(),
                      QImage.Format.Format_Alpha8).convertToFormat(FORMAT)

    def add_mask(self):
        if self.layer.mask is not None:
            return False
        check_size(self.size, len(self.layers) + sum(layer.mask is not None for layer in self.layers) + 1,
                   max_layers=MAX_LAYERS * 2)
        mask = self.selection_mask(self.layer.image.rect())
        self.checkpoint()
        self.layer.mask = mask
        self.selection = QPainterPath()
        return True

    def remove_mask(self):
        if self.layer.mask is not None:
            self.checkpoint()
            self.layer.mask = None

    def clear_selection_pixels(self):
        bounds = self.selection_bounds(feathered=True)
        if bounds.isEmpty() or not self.layer.visible:
            return False
        mask = self.selection_mask(bounds)
        self.checkpoint()
        apply_alpha(self.layer.image, mask, remove=True, offset=QPointF(bounds.topLeft()))
        return True

    def crop(self):
        bounds = self.selection_bounds()
        if bounds.isEmpty() or bounds == self.layer.image.rect():
            return False
        self.checkpoint()
        self.layers = [replace(layer, image=layer.image.copy(bounds),
                               mask=layer.mask.copy(bounds) if layer.mask is not None else None)
                       for layer in self.layers]
        self.selection = QPainterPath()
        return True

    def add_layer(self, name, image=None):
        check_size(self.size, len(self.layers) + 1)
        check_size(self.size, len(self.layers) + 1 + sum(layer.mask is not None for layer in self.layers),
                   max_layers=MAX_LAYERS * 2)
        layer_image = transparent(self.size)
        if image is not None:
            with QPainter(layer_image) as painter:
                painter.drawImage(0, 0, image)
        self.checkpoint()
        self.active += 1
        self.layers.insert(self.active, Layer(name, layer_image))

    def export_png(self, path):
        target = QSaveFile(str(path))
        if not target.open(QIODevice.OpenModeFlag.WriteOnly):
            raise OSError(target.errorString())
        if not self.render().save(target, "PNG") or not target.commit():
            raise OSError("PNG konnte nicht gespeichert werden.")

    def save_project(self, path):
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".creative-art-", delete=False) as handle:
            temporary = Path(handle.name)
        try:
            with zipfile.ZipFile(temporary, "w") as archive:
                archive.writestr("project.json", json.dumps({
                    "version": 2, "width": self.size.width(), "height": self.size.height(),
                    "active": self.active, "layers": [
                        {"name": layer.name, "visible": layer.visible, "opacity": layer.opacity,
                         "mask": layer.mask is not None}
                        for layer in self.layers
                    ],
                }, ensure_ascii=False))
                for index, layer in enumerate(self.layers):
                    for folder, image in (("layers", layer.image), ("masks", layer.mask)):
                        if image is None:
                            continue
                        data = QByteArray()
                        buffer = QBuffer(data)
                        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly) or not image.save(buffer, "PNG"):
                            raise OSError("Eine Ebene oder Maske konnte nicht gespeichert werden.")
                        buffer.close()
                        archive.writestr(f"{folder}/{index}.png", bytes(data))
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        self.saved_version = self.version

    @classmethod
    def open_project(cls, path):
        try:
            with zipfile.ZipFile(path) as archive:
                if archive.getinfo("project.json").file_size > 64 * 1024:
                    raise ValueError("Projektinformationen sind zu groß.")
                meta = json.loads(archive.read("project.json"))
                if meta["version"] not in (1, 2):
                    raise ValueError("Unbekannte Creative-Art-Projektversion.")
                size = QSize(meta["width"], meta["height"])
                check_size(size, len(meta["layers"]))
                check_size(size, len(meta["layers"]) + sum(
                    meta["version"] == 2 and entry.get("mask") is True for entry in meta["layers"]
                ), max_layers=MAX_LAYERS * 2)

                def read_raster(filename):
                    if archive.getinfo(filename).file_size > size.width() * size.height() * 5 + 1024 * 1024:
                        raise ValueError("Ebenendatei ist zu groß.")
                    data = QByteArray(archive.read(filename))
                    buffer = QBuffer(data)
                    if not buffer.open(QIODevice.OpenModeFlag.ReadOnly):
                        raise ValueError("Eine Ebene konnte nicht gelesen werden.")
                    reader = QImageReader(buffer, b"png")
                    if reader.size() != size:
                        raise ValueError("Eine Ebene hat ungültige Abmessungen.")
                    image = read_image(reader)
                    if image.size() != size:
                        raise ValueError("Eine Ebene hat ungültige Abmessungen.")
                    buffer.close()
                    return image

                layers = []
                for index, entry in enumerate(meta["layers"]):
                    image = read_raster(f"layers/{index}.png")
                    mask = (read_raster(f"masks/{index}.png")
                            if meta["version"] == 2 and entry.get("mask") is True else None)
                    layers.append(Layer(str(entry["name"])[:120], image, bool(entry["visible"]),
                                        min(100, max(0, int(entry["opacity"]))), mask))
                document = cls(layers[0].image)
                document.layers = layers
                document.active = min(len(layers) - 1, max(0, int(meta["active"])))
                return document
        except (AttributeError, KeyError, TypeError, OverflowError, zipfile.BadZipFile) as error:
            raise ValueError("Ungültiges Creative-Art-Projekt.") from error
