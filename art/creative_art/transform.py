"""Interactive layer transform, committed as a single undo step."""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
    QLabel, QVBoxLayout, QWidget,
)

from .document import layer_bounds, layer_matrix

try:  # Design (Graphit/Porzellan) und Akzentfarbe von Creative OS
    from creative_look import themed as T
except ImportError:
    def T(value):
        return value



class TransformPreview(QWidget):
    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
        self.setMinimumSize(520, 345)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.drag = None
        self.rasters = [layer.rendered() if layer.visible else None for layer in dialog.document.layers]

    def layout_frame(self):
        size = self.dialog.document.size
        zoom = min((self.width() - 32) / size.width(), (self.height() - 32) / size.height())
        origin = QPointF((self.width() - size.width() * zoom) / 2,
                         (self.height() - size.height() * zoom) / 2)
        return zoom, origin

    def paintEvent(self, _event):
        zoom, origin = self.layout_frame()
        document = self.dialog.document
        transform = self.dialog.matrix()
        with QPainter(self) as painter:
            painter.fillRect(self.rect(), QColor(T("#101218")))
            painter.translate(origin)
            painter.scale(zoom, zoom)
            frame = QRectF(0, 0, document.size.width(), document.size.height())
            painter.fillRect(frame, QColor(T("#5a6171")))
            painter.setClipRect(frame)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            for index, layer in enumerate(document.layers):
                image = self.rasters[index]
                if image is None:
                    continue
                painter.save()
                painter.setOpacity(layer.opacity / 100)
                if index == document.active:
                    painter.setTransform(transform, True)
                painter.drawImage(0, 0, image)
                painter.restore()
            painter.setClipping(False)
            pen = QPen(QColor(T("#9cbcff")))
            pen.setCosmetic(True)
            painter.setPen(pen)
            outline = [transform.map(corner) for corner in self.dialog.corners]
            for i, corner in enumerate(outline):
                painter.drawLine(corner, outline[(i + 1) % 4])
                radius = 4 / zoom
                painter.fillRect(QRectF(corner.x() - radius, corner.y() - radius,
                                        radius * 2, radius * 2), QColor(T("#9cbcff")))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        zoom, origin = self.layout_frame()
        start = (event.position() - origin) / zoom
        matrix = self.dialog.matrix()
        handle = next((corner for corner in self.dialog.corners
                       if (matrix.map(corner) - start).manhattanLength() * zoom <= 13), None)
        self.drag = start, handle, self.dialog.offset, self.dialog.width_scale.value(), self.dialog.height_scale.value()

    def mouseMoveEvent(self, event):
        if self.drag is None:
            return
        zoom, origin = self.layout_frame()
        start, handle, offset, width, height = self.drag
        point = (event.position() - origin) / zoom
        delta = point - start
        if handle is None:
            self.dialog.offset = offset + delta
        else:
            angle = math.radians(self.dialog.angle.value())
            dx = math.cos(angle) * delta.x() + math.sin(angle) * delta.y()
            dy = -math.sin(angle) * delta.x() + math.cos(angle) * delta.y()
            corner = handle - self.dialog.center
            x = -corner.x() if self.dialog.flip_x.isChecked() else corner.x()
            y = -corner.y() if self.dialog.flip_y.isChecked() else corner.y()
            self.dialog.width_scale.setValue(width + 100 * dx / x)
            self.dialog.height_scale.setValue(height + 100 * dy / y)
        self.update()

    def mouseReleaseEvent(self, _event):
        self.drag = None


class TransformDialog(QDialog):
    def __init__(self, parent, document):
        super().__init__(parent)
        self.setWindowTitle("Ebene frei transformieren")
        self.document = document
        bounds = QRectF(layer_bounds(document.layer.image))
        self.center = bounds.center()
        self.corners = (bounds.topLeft(), bounds.topRight(), bounds.bottomRight(), bounds.bottomLeft())
        self.offset = QPointF()
        self.width_scale = QDoubleSpinBox(minimum=1, maximum=800, value=100, suffix=" %")
        self.height_scale = QDoubleSpinBox(minimum=1, maximum=800, value=100, suffix=" %")
        self.angle = QDoubleSpinBox(minimum=-180, maximum=180, suffix="°")
        self.flip_x = QCheckBox("Horizontal spiegeln")
        self.flip_y = QCheckBox("Vertikal spiegeln")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Ziehe an einer Ecke zum Skalieren oder im Bild zum Verschieben."))
        self.preview = TransformPreview(self)
        layout.addWidget(self.preview)
        form = QFormLayout()
        for label, widget in (("Breite", self.width_scale), ("Höhe", self.height_scale), ("Drehung", self.angle)):
            form.addRow(label, widget)
            widget.valueChanged.connect(self.preview.update)
        layout.addLayout(form)
        flips = QHBoxLayout()
        for widget in (self.flip_x, self.flip_y):
            flips.addWidget(widget)
            widget.toggled.connect(self.preview.update)
        layout.addLayout(flips)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def matrix(self):
        return layer_matrix(self.center, self.offset, self.width_scale.value() / 100,
                            self.height_scale.value() / 100, self.angle.value(),
                            self.flip_x.isChecked(), self.flip_y.isChecked())
