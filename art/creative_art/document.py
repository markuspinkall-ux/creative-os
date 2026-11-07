"""Layered raster documents and the Creative Art project format."""

import json
import os
import tempfile
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRect, QSaveFile, QSize, Qt
from PySide6.QtGui import QImage, QImageReader, QPainter, QPainterPath

MAX_SIDE = 8192
MAX_LAYER_BYTES = 256 * 1024 * 1024
MAX_LAYERS = 32
HISTORY_BYTES = 128 * 1024 * 1024
FORMAT = QImage.Format.Format_ARGB32_Premultiplied


def check_size(size, count=1):
    if (not 1 <= size.width() <= MAX_SIDE or not 1 <= size.height() <= MAX_SIDE
            or not 1 <= count <= MAX_LAYERS
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


class Document:
    def __init__(self, image, name="Ebene 1"):
        check_size(image.size())
        self.layers = [Layer(name, image)]
        self.active = 0
        self.selection = QPainterPath()
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
        return ([replace(layer, image=QImage(layer.image)) for layer in self.layers],
                self.active, QPainterPath(self.selection), self.version)

    def restore(self, state):
        self.layers, self.active, self.selection, self.version = state

    def checkpoint(self):
        self.undo.append(self.snapshot())
        self.redo.clear()
        self.next_version += 1
        self.version = self.next_version
        # Count each shared Qt raster only once across the retained snapshots.
        images = {}
        for layers, *_ in reversed(self.undo):
            for layer in layers:
                images[layer.image.cacheKey()] = layer.image.sizeInBytes()
        while len(self.undo) > 1 and (len(self.undo) > 24 or sum(images.values()) > HISTORY_BYTES):
            self.undo.pop(0)
            retained = {layer.image.cacheKey() for layers, *_ in self.undo for layer in layers}
            images = {key: size for key, size in images.items() if key in retained}

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
            if selection and not self.selection.isEmpty():
                painter.setClipPath(self.selection)
            for layer in self.layers:
                if layer.visible:
                    painter.setOpacity(layer.opacity / 100)
                    painter.drawImage(0, 0, layer.image)
        return result

    def selection_bounds(self):
        canvas = QRect(0, 0, self.size.width(), self.size.height())
        return self.selection.boundingRect().toAlignedRect().intersected(canvas)

    def clear_selection_pixels(self):
        if self.selection_bounds().isEmpty() or not self.layer.visible:
            return False
        self.checkpoint()
        with QPainter(self.layer.image) as painter:
            painter.setClipPath(self.selection)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(self.layer.image.rect(), Qt.GlobalColor.black)
        return True

    def crop(self):
        bounds = self.selection_bounds()
        if bounds.isEmpty() or bounds == self.layer.image.rect():
            return False
        self.checkpoint()
        self.layers = [replace(layer, image=layer.image.copy(bounds)) for layer in self.layers]
        self.selection = QPainterPath()
        return True

    def add_layer(self, name, image=None):
        check_size(self.size, len(self.layers) + 1)
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
                    "version": 1, "width": self.size.width(), "height": self.size.height(),
                    "active": self.active, "layers": [
                        {"name": layer.name, "visible": layer.visible, "opacity": layer.opacity}
                        for layer in self.layers
                    ],
                }, ensure_ascii=False))
                for index, layer in enumerate(self.layers):
                    data = QByteArray()
                    buffer = QBuffer(data)
                    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly) or not layer.image.save(buffer, "PNG"):
                        raise OSError("Eine Ebene konnte nicht gespeichert werden.")
                    buffer.close()
                    archive.writestr(f"layers/{index}.png", bytes(data))
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
                if meta["version"] != 1:
                    raise ValueError("Unbekannte Creative-Art-Projektversion.")
                size = QSize(meta["width"], meta["height"])
                check_size(size, len(meta["layers"]))
                layers = []
                for index, entry in enumerate(meta["layers"]):
                    filename = f"layers/{index}.png"
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
                    layers.append(Layer(str(entry["name"])[:120], image, bool(entry["visible"]),
                                        min(100, max(0, int(entry["opacity"])))))
                document = cls(layers[0].image)
                document.layers = layers
                document.active = min(len(layers) - 1, max(0, int(meta["active"])))
                return document
        except (KeyError, TypeError, OverflowError, zipfile.BadZipFile) as error:
            raise ValueError("Ungültiges Creative-Art-Projekt.") from error
