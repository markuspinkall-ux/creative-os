"""Zoomable image canvas and raster tools."""

import math

from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPolygonF, QTransform
from PySide6.QtWidgets import QWidget

from .brushengine import BrushLibrary, Stroke, bucket_fill, gradient_fill


class Canvas(QWidget):
    changed = Signal()
    hint = Signal(str)
    zoomChanged = Signal(float)
    colorChanged = Signal()
    tools_select = {"rectangle", "ellipse", "lasso", "crop"}
    tools_shape = {"line", "box", "oval"}
    tools_mask = {"mask_hide", "mask_show"}
    tools_brush = {"brush", "eraser", "smudge", "mask_hide", "mask_show"}
    presetChanged = Signal()

    def __init__(self, document, library=None):
        super().__init__()
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TabletTracking)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.tool = "brush"
        self.color = QColor("#293855")
        self.library = library or BrushLibrary()
        self.preset = self.library.presets[0]
        self.zoom = 1.0
        self.pressure = 1.0
        self.tablet = False
        self.hover = None
        self.active_stroke = None
        self.tolerance = 32
        self.contiguous = True
        self.gradient_kind = "linear"
        self.set_document(document)

    # Größe und Deckkraft gehören zum aktiven Pinsel (wie in Photoshop)
    @property
    def diameter(self):
        return self.preset.size

    @diameter.setter
    def diameter(self, value):
        self.preset.size = max(1, min(2500, int(value)))
        self.presetChanged.emit()
        self.update()

    @property
    def opacity(self):
        return self.preset.opacity

    @opacity.setter
    def opacity(self, value):
        self.preset.opacity = max(1, min(100, int(value)))
        self.presetChanged.emit()

    def set_preset(self, preset):
        self.preset = preset
        self.presetChanged.emit()
        self.update()

    def set_document(self, document):
        self.document = document
        self.origin = self.last = None
        self.clone_source = None
        self.clone_image = None
        self.outline = []
        self.preview = QPainterPath()
        self.move_offset = QPointF()
        self.set_zoom(self.zoom)

    def set_tool(self, tool):
        self.origin = self.last = self.clone_image = None
        self.preview = QPainterPath()
        self.move_offset = QPointF()
        self.outline.clear()
        self.active_stroke = None
        self.tool = tool
        self.setCursor(Qt.CursorShape.BlankCursor if tool in self.tools_brush else Qt.CursorShape.CrossCursor)
        self.changed.emit()
        self.update()

    def set_zoom(self, factor):
        self.zoom = max(.0625, min(8, factor))
        size = self.raster_size = self.document.size
        self.setFixedSize(max(1, math.ceil(size.width() * self.zoom)),
                          max(1, math.ceil(size.height() * self.zoom)))
        self.zoomChanged.emit(self.zoom)
        self.update()

    def paintEvent(self, event):
        with QPainter(self) as painter:
            painter.fillRect(event.rect(), QColor("#e3e7ed"))
            step = 12
            rect = event.rect()
            for y in range(rect.top() // step, rect.bottom() // step + 1):
                for x in range(rect.left() // step, rect.right() // step + 1):
                    if (x + y) % 2:
                        painter.fillRect(x * step, y * step, step, step, QColor("#b5bcc8"))
            painter.scale(self.zoom, self.zoom)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, self.zoom < 1)
            for layer in self.document.layers:
                if layer.visible:
                    painter.setOpacity(layer.opacity / 100)
                    offset = self.move_offset if layer is self.document.layer else QPointF()
                    painter.drawImage(offset, layer.rendered())
            painter.setOpacity(1)
            path = self.document.selection
            if not path.isEmpty():
                pen = QPen(Qt.GlobalColor.white)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.drawPath(path)
                pen.setColor(Qt.GlobalColor.black)
                pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawPath(path)
            if not self.preview.isEmpty():
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setPen(self.brush_pen(self.color))
                painter.drawPath(self.preview)
            if self.hover is not None and self.tool in self.tools_brush | {"clone"}:
                # Umriss der Pinselspitze statt Mauszeiger
                r = max(1.5 / self.zoom, self.diameter / 2)
                for color, width in (("#12151b", 3), ("#dce6ff", 1)):
                    pen = QPen(QColor(color), width)
                    pen.setCosmetic(True)
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawEllipse(self.hover, r, r)
                if r * self.zoom < 6:
                    painter.drawLine(self.hover - QPointF(5 / self.zoom, 0), self.hover + QPointF(5 / self.zoom, 0))
                    painter.drawLine(self.hover - QPointF(0, 5 / self.zoom), self.hover + QPointF(0, 5 / self.zoom))
            if self.tool == "clone" and self.clone_source is not None:
                pen = QPen(QColor("#68a0ff"))
                pen.setCosmetic(True)
                painter.setPen(pen)
                p = self.clone_source
                r = 6 / self.zoom
                painter.drawLine(p - QPointF(r, 0), p + QPointF(r, 0))
                painter.drawLine(p - QPointF(0, r), p + QPointF(0, r))

    def tabletEvent(self, event):
        # Druck merken; Qt erzeugt daraus anschließend die normalen Mausereignisse
        kind = event.type()
        if kind == QEvent.Type.TabletPress:
            self.tablet = True
        self.pressure = max(0.0, min(1.0, event.pressure())) if self.tablet else 1.0
        if kind == QEvent.Type.TabletRelease:
            self.tablet = False
        event.ignore()

    def leaveEvent(self, event):
        self._hover(None)
        super().leaveEvent(event)

    def _hover(self, point):
        old = self.hover
        self.hover = point
        r = (self.diameter / 2 + 4) * self.zoom + 8
        for p in (old, point):
            if p is not None:
                c = p * self.zoom
                self.update(QRect(int(c.x() - r), int(c.y() - r), int(2 * r), int(2 * r)))

    def current_pressure(self):
        return self.pressure if self.tablet else 1.0

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_zoom(self.zoom * (1.25 if event.angleDelta().y() > 0 else .8))
            event.accept()
        else:
            event.ignore()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = event.position() / self.zoom
        if self.tool == "clone" and event.modifiers() & (Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier):
            self.clone_source = point
            self.hint.emit("Kopierquelle gesetzt. Male über die Stelle, die du retuschieren willst.")
            self.update()
            return
        if self.tool in self.tools_select:
            self.origin = point
            self.outline = [point]
            self.update_selection(point)
            return
        if self.tool == "picker":
            x, y = math.floor(point.x()), math.floor(point.y())
            if self.document.layer.image.rect().contains(x, y):
                self.color = self.document.render(QRect(x, y, 1, 1)).pixelColor(0, 0)
                self.colorChanged.emit()
            return
        if not self.document.layer.visible:
            self.hint.emit("Blende die aktive Ebene ein, um darauf zu malen.")
            return
        if self.tool in self.tools_shape or self.tool in ("move", "gradient"):
            self.origin = point
            return
        if self.tool == "bucket":
            x, y = math.floor(point.x()), math.floor(point.y())
            if not self.document.layer.image.rect().contains(x, y):
                return
            self.document.checkpoint()
            bucket_fill(self.document.layer.image, x, y, self.color, self.tolerance, self.contiguous,
                        self.opacity / 100, self.document.selection)
            self.changed.emit()
            self.update()
            return
        if self.tool in self.tools_mask and self.document.layer.mask is None:
            self.hint.emit("Lege zuerst eine Ebenenmaske an.")
            return
        if self.tool == "clone":
            if self.clone_source is None:
                self.hint.emit("Mit Alt oder Umschalt + Klick zuerst eine Kopierquelle wählen.")
                return
            self.clone_image = QImage(self.document.layer.image)
            self.clone_offset = self.clone_source - point
        self.document.checkpoint()
        if self.tool in self.tools_brush:
            active = self.document.layer
            target = active.mask if self.tool in self.tools_mask else active.image
            mode = {"brush": "paint", "eraser": "erase", "smudge": "smudge"}.get(self.tool, self.tool)
            self.active_stroke = Stroke(target, self.preset, self.color, self.library, mode,
                                        self.document.selection)
        self.origin = self.last = point
        self.stroke(point)

    def mouseMoveEvent(self, event):
        point = event.position() / self.zoom
        if self.tool in self.tools_brush | {"clone"}:
            self._hover(point)
        if self.origin is None:
            return
        if self.tool in self.tools_select:
            self.update_selection(point)
        elif self.tool == "move":
            self.move_offset = QPointF((point - self.origin).toPoint())
            self.update()
        elif self.tool == "gradient":
            self.preview = QPainterPath(self.origin)
            self.preview.lineTo(point)
            self.update()
        elif self.tool in self.tools_shape:
            self.preview = self.shape(point)
            self.update()
        else:
            self.stroke(point)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.origin is None:
            return
        point = event.position() / self.zoom
        if self.tool in self.tools_select:
            self.update_selection(point)
        elif self.tool == "move":
            offset = (point - self.origin).toPoint()
            if not offset.isNull():
                moved = self.document.layer.transformed(QTransform.fromTranslate(offset.x(), offset.y()))
                self.document.checkpoint()
                self.document.layers[self.document.active] = moved
            self.move_offset = QPointF()
        elif self.tool == "gradient":
            self.preview = QPainterPath()
            if (point - self.origin).manhattanLength() >= 1:
                self.document.checkpoint()
                gradient_fill(self.document.layer.image, self.origin, point, self.color, self.gradient_kind,
                              opacity=self.opacity / 100, clip=self.document.selection)
        elif self.tool in self.tools_shape:
            path = self.shape(point)
            if not path.isEmpty():
                self.document.checkpoint()
                with QPainter(self.document.layer.image) as painter:
                    self.configure_brush(painter)
                    painter.setPen(self.brush_pen(self.color))
                    painter.drawPath(path)
            self.preview = QPainterPath()
        elif point != self.last:
            self.stroke(point)
        self.origin = self.last = self.clone_image = None
        self.active_stroke = None
        self.outline.clear()
        self.changed.emit()

    def update_selection(self, point):
        path = QPainterPath()
        box = QRectF(self.origin, point).normalized()
        if self.tool == "lasso":
            self.outline.append(point)
            if len(self.outline) > 2:
                path.addPolygon(QPolygonF(self.outline))
                path.closeSubpath()
        elif not box.isEmpty():
            if self.tool == "ellipse":
                path.addEllipse(box)
            else:
                path.addRect(box)
        self.document.selection = path
        self.update()

    def shape(self, point):
        path = QPainterPath()
        box = QRectF(self.origin, point).normalized()
        if self.tool == "line":
            path.moveTo(self.origin)
            path.lineTo(point)
        elif not box.isEmpty():
            if self.tool == "oval":
                path.addEllipse(box)
            else:
                path.addRect(box)
        return path

    def configure_brush(self, painter):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self.opacity / 100)
        if not self.document.selection.isEmpty():
            painter.setClipPath(self.document.selection)

    def brush_pen(self, color):
        return QPen(color, self.diameter, Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

    def stroke(self, point):
        if self.active_stroke is not None:
            dirty = self.active_stroke.add(point, self.current_pressure())
            self.last = point
            if not dirty.isEmpty():
                r = QRectF(dirty).adjusted(-2, -2, 2, 2)
                self.update(QRect(int(r.x() * self.zoom), int(r.y() * self.zoom),
                                  int(r.width() * self.zoom) + 2, int(r.height() * self.zoom) + 2))
            return
        active = self.document.layer
        layer = active.mask if self.tool in self.tools_mask else active.image
        with QPainter(layer) as painter:
            self.configure_brush(painter)
            if self.tool == "clone":
                distance = math.hypot(point.x() - self.last.x(), point.y() - self.last.y())
                steps = max(1, math.ceil(distance / max(1, self.diameter / 5)))
                painter.save()
                d = self.diameter
                offset = self.clone_offset
                for step in range(1, steps + 1):
                    center = self.last + (point - self.last) * (step / steps)
                    box = QRectF(center.x() - d / 2, center.y() - d / 2, d, d)
                    mask = QPainterPath()
                    mask.addEllipse(box)
                    painter.save()
                    painter.setClipPath(mask, Qt.ClipOperation.IntersectClip)
                    painter.drawImage(box, self.clone_image, box.translated(offset))
                    painter.restore()
                painter.restore()
            else:
                if self.tool in {"eraser", "mask_hide"}:
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
                color = (Qt.GlobalColor.white if self.tool in self.tools_mask else
                         Qt.GlobalColor.black if self.tool == "eraser" else self.color)
                painter.setPen(self.brush_pen(color))
                if self.last == point:
                    painter.drawPoint(point)
                else:
                    painter.drawLine(self.last, point)
        self.last = point
        self.update()
