"""Level-Editor für Jump'n'Run (2,5D): Seitenansicht mit Raster, Blöcke malen, Objekte setzen, 3D-Kulisse."""

import copy
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFormLayout, QGraphicsScene, QGraphicsView,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QScrollArea,
    QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

from . import icons, project as proj
from .style import C

TILE = 32
TILE_COLOR = {key: color for key, _name, color in proj.TILES}
TILE_COLOR["erde"] = "#7a5a3a"
ENTITY_NAME = {k: n for k, n, _d in proj.ENTITIES}


def draw_entity(p, kind, rect, data=None, faded=False):
    """Symbol eines Objekts im Raster (rect = eine Kachel)."""
    p.save()
    if faded:
        p.setOpacity(0.45)
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    c = rect.center()
    p.setPen(Qt.PenStyle.NoPen)
    if kind == "coin":
        p.setBrush(QColor("#ffd24a"))
        p.drawEllipse(c, w * 0.3, h * 0.3)
        p.setBrush(QColor("#ffb300"))
        p.drawEllipse(c, w * 0.14, h * 0.2)
    elif kind == "enemy":
        p.setBrush(QColor("#ff6b6b"))
        p.drawEllipse(QRectF(x + w * 0.12, y + h * 0.25, w * 0.76, h * 0.7))
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QPointF(x + w * 0.38, y + h * 0.5), w * 0.1, h * 0.1)
        p.drawEllipse(QPointF(x + w * 0.62, y + h * 0.5), w * 0.1, h * 0.1)
        rng = float((data or {}).get("range", 3))
        p.setPen(QPen(QColor(255, 107, 107, 140), 2, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(c.x() - rng * w, y + h - 2), QPointF(c.x() + rng * w, y + h - 2))
    elif kind == "spike":
        p.setBrush(QColor("#c9d1de"))
        for i in range(3):
            poly = QPolygonF([QPointF(x + i * w / 3, y + h), QPointF(x + (i + 0.5) * w / 3, y + h * 0.35),
                              QPointF(x + (i + 1) * w / 3, y + h)])
            p.drawPolygon(poly)
    elif kind == "goal":
        p.setBrush(QColor("#dce6ff"))
        p.drawRect(QRectF(c.x() - 2, y - h * 3, 4, h * 4))
        p.setBrush(QColor("#6fdcc0"))
        p.drawRect(QRectF(c.x() + 2, y - h * 3, w * 0.9, h * 0.6))
    elif kind == "start":
        p.setBrush(QColor("#8fb3ff"))
        p.drawRoundedRect(QRectF(x + w * 0.25, y - h * 0.5, w * 0.5, h * 1.5), w * 0.25, w * 0.25)
        p.setPen(QPen(QColor("#12151b"), 2))
        p.drawText(QRectF(x, y - h * 0.5, w, h), Qt.AlignmentFlag.AlignCenter, "S")
    elif kind == "checkpoint":
        p.setBrush(QColor("#c9d1de"))
        p.drawRect(QRectF(c.x() - 2, y - h * 0.4, 4, h * 1.4))
        p.setBrush(QColor("#ff8a8e"))
        p.drawEllipse(QPointF(c.x(), y - h * 0.4), w * 0.18, w * 0.18)
    elif kind == "spring":
        p.setBrush(QColor("#ff8a8e"))
        p.drawRoundedRect(QRectF(x + 2, y + h * 0.55, w - 4, h * 0.4), 4, 4)
        p.setPen(QPen(QColor("#dce6ff"), 2))
        for i in range(3):
            p.drawLine(QPointF(x + w * 0.25, y + h * (0.2 + i * 0.12)), QPointF(x + w * 0.75, y + h * (0.26 + i * 0.12)))
    elif kind == "npc":
        p.setBrush(QColor("#c3a6ff"))
        p.drawRoundedRect(QRectF(x + w * 0.25, y - h * 0.5, w * 0.5, h * 1.5), w * 0.25, w * 0.25)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(x + w * 0.6, y - h * 1.1, w * 0.9, h * 0.55), 5, 5)
        p.setPen(QColor("#12151b"))
        f = QFont()
        f.setPixelSize(int(h * 0.4))
        p.setFont(f)
        p.drawText(QRectF(x + w * 0.6, y - h * 1.1, w * 0.9, h * 0.55), Qt.AlignmentFlag.AlignCenter, "…")
    p.restore()


class LevelView(QGraphicsView):
    changed = Signal()
    selected = Signal(object)        # Objekt-dict, Kulisse-dict oder None
    status = Signal(str)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setMouseTracking(True)
        self.level = None
        self.tool = "paint"            # paint | erase | rect | select
        self.brush = ("tile", "gras")  # ("tile", art) | ("entity", art) | ("decor", modellpfad)
        self.hover = None
        self.drag_start = None
        self.dragging = None
        self.selection = None
        self.panning = None
        self.zoom = 1.0
        self.undo_stack = []
        self.redo_stack = []

    # ---- Daten ------------------------------------------------------------------------
    def set_level(self, level):
        self.level = level
        self.selection = None
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.resize_scene()
        self.centerOn(0, self.scene().sceneRect().bottom())

    def resize_scene(self):
        if not self.level:
            return
        w, h = self.level["width"] * TILE, self.level["height"] * TILE
        self.scene().setSceneRect(QRectF(-TILE * 2, -TILE * 3, w + TILE * 4, h + TILE * 5))
        self.viewport().update()

    def snapshot(self):
        self.undo_stack.append(copy.deepcopy(self.level))
        del self.undo_stack[:-60]
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(copy.deepcopy(self.level))
            self.restore(self.undo_stack.pop())

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(copy.deepcopy(self.level))
            self.restore(self.redo_stack.pop())

    def restore(self, state):
        self.level.clear()
        self.level.update(state)
        self.selection = None
        self.selected.emit(None)
        self.resize_scene()
        self.changed.emit()

    # ---- Koordinaten ------------------------------------------------------------------
    def cell(self, pos):
        sp = self.mapToScene(pos)
        x = int(sp.x() // TILE)
        y = int((self.level["height"] * TILE - sp.y()) // TILE)
        return x, y

    def cell_rect(self, x, y):
        return QRectF(x * TILE, (self.level["height"] - 1 - y) * TILE, TILE, TILE)

    def inside(self, x, y):
        return 0 <= x < self.level["width"] and 0 <= y < self.level["height"]

    # ---- Zeichnen ---------------------------------------------------------------------
    def drawBackground(self, p, rect):
        p.fillRect(rect, QColor(C["view"]))
        if not self.level:
            return
        W, H = self.level["width"], self.level["height"]
        area = QRectF(0, 0, W * TILE, H * TILE)
        sky = QColor(self.level.get("sky", "#8ec5ff"))
        p.fillRect(area, sky.darker(105) if C["light"] else sky.darker(135))
        # Kulisse (hinter der Spielebene)
        for d in self.level.get("decor", []):
            r = self.decor_rect(d)
            p.setPen(QPen(QColor(255, 255, 255, 120), 1.5, Qt.PenStyle.DashLine))
            p.setBrush(QColor(40, 60, 90, 70))
            p.drawRoundedRect(r, 8, 8)
            p.setPen(QColor(255, 255, 255, 200))
            f = QFont()
            f.setPixelSize(11)
            p.setFont(f)
            p.drawText(r.adjusted(4, 4, -4, -4), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                       Path(d.get("model", "")).stem or "3D")
        # Raster
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        for x in range(W + 1):
            p.drawLine(QPointF(x * TILE, 0), QPointF(x * TILE, H * TILE))
        for y in range(H + 1):
            p.drawLine(QPointF(0, y * TILE), QPointF(W * TILE, y * TILE))
        p.setPen(QPen(QColor(C["accent"]), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(area)
        # Blöcke
        tiles = self.level["tiles"]
        for key, kind in tiles.items():
            x, y = (int(v) for v in key.split(","))
            r = self.cell_rect(x, y)
            if not r.intersects(rect):
                continue
            color = QColor(TILE_COLOR.get(kind, "#8a93a3"))
            p.setPen(QPen(color.darker(130), 1))
            p.setBrush(color)
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 3, 3)
            if kind == "gras" and tiles.get(f"{x},{y + 1}") is None:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#5fb04a"))
                p.drawRoundedRect(QRectF(r.x(), r.y(), r.width(), r.height() * 0.32), 3, 3)
            elif kind == "ziegel":
                p.setPen(QPen(color.darker(150), 1))
                p.drawLine(QPointF(r.left(), r.center().y()), QPointF(r.right(), r.center().y()))

    def decor_rect(self, d):
        hgt = float(d.get("height", 3)) * TILE
        wid = hgt * 0.8
        cx = (float(d.get("x", 0)) + 0.5) * TILE
        bottom = (self.level["height"] - float(d.get("y", 0))) * TILE
        return QRectF(cx - wid / 2, bottom - hgt, wid, hgt)

    def drawForeground(self, p, rect):
        if not self.level:
            return
        for e in self.level["entities"]:
            r = self.cell_rect(int(e["x"]), int(e["y"]))
            draw_entity(p, e["kind"], r, e)
            if e is self.selection:
                p.setPen(QPen(QColor(C["accent"]), 2, Qt.PenStyle.DashLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(r.adjusted(-4, -4, 4, 4), 6, 6)
        for d in self.level.get("decor", []):
            if d is self.selection:
                p.setPen(QPen(QColor(C["accent"]), 2, Qt.PenStyle.DashLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(self.decor_rect(d).adjusted(-3, -3, 3, 3), 8, 8)
        # Vorschau unter dem Mauszeiger
        if self.hover and self.tool in ("paint", "rect", "erase") and self.inside(*self.hover):
            if self.drag_start and self.tool in ("rect",) or (self.drag_start and self.tool == "erase" and self.rect_erase):
                x0, y0 = self.drag_start
                x1, y1 = self.hover
                r = self.cell_rect(min(x0, x1), max(y0, y1)).united(self.cell_rect(max(x0, x1), min(y0, y1)))
            else:
                r = self.cell_rect(*self.hover)
            if self.tool == "erase":
                p.setPen(QPen(QColor(C["danger"]), 2))
                p.setBrush(QColor(255, 138, 142, 50))
                p.drawRect(r)
            elif self.brush[0] == "tile":
                c = QColor(TILE_COLOR.get(self.brush[1], "#8a93a3"))
                c.setAlpha(150)
                p.setPen(QPen(QColor(C["accent"]), 1.5))
                p.setBrush(c)
                p.drawRect(r)
            elif self.brush[0] == "entity":
                draw_entity(p, self.brush[1], r, None, faded=True)
            else:
                p.setPen(QPen(QColor(C["accent"]), 1.5, Qt.PenStyle.DashLine))
                p.setBrush(QColor(143, 179, 255, 40))
                p.drawRect(r)

    rect_erase = False

    # ---- Maus -------------------------------------------------------------------------
    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            new = max(0.3, min(3.0, self.zoom * factor))
            factor = new / self.zoom
            self.zoom = new
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            self.scale(factor, factor)
            return
        if not event.modifiers() & Qt.KeyboardModifier.ShiftModifier and abs(event.angleDelta().y()) > 0:
            # Mausrad blättert waagerecht (Levels sind breit)
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - event.angleDelta().y())
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event):
        if not self.level:
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            self.panning = event.position()
            return
        x, y = self.cell(event.position().toPoint())
        if event.button() == Qt.MouseButton.RightButton:
            self.snapshot()
            self.erase_at(x, y)
            self.drag_start = (x, y)
            self.dragging = "erase-right"
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.tool == "select":
            self.selection = self.pick(event.position().toPoint())
            self.selected.emit(self.selection)
            if self.selection is not None:
                self.snapshot()
                self.dragging = "move"
            self.viewport().update()
            return
        self.snapshot()
        self.drag_start = (x, y)
        self.rect_erase = self.tool == "erase" and bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if self.tool == "rect" or self.rect_erase:
            self.dragging = "rect"
        elif self.tool == "erase":
            self.erase_at(x, y)
            self.dragging = "erase"
        else:
            self.place(x, y)
            self.dragging = "paint" if self.brush[0] == "tile" else None

    def mouseMoveEvent(self, event):
        if not self.level:
            return
        if self.panning is not None:
            d = event.position() - self.panning
            self.panning = event.position()
            self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - d.x()))
            self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - d.y()))
            return
        cell = self.cell(event.position().toPoint())
        if cell != self.hover:
            self.hover = cell
            x, y = cell
            if self.inside(x, y):
                self.status.emit(f"Feld {x}, {y}")
            if self.dragging == "paint":
                self.place(x, y)
            elif self.dragging in ("erase", "erase-right"):
                self.erase_at(x, y)
            elif self.dragging == "move" and self.selection is not None and self.inside(x, y):
                self.selection["x"], self.selection["y"] = x, y
                self.changed.emit()
            self.viewport().update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.panning = None
            return
        if self.dragging == "rect" and self.drag_start and self.hover:
            x0, y0 = self.drag_start
            x1, y1 = self.hover
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    if self.rect_erase:
                        self.erase_at(x, y)
                    elif self.inside(x, y):
                        self.put_tile(x, y)
            self.changed.emit()
        if self.dragging == "move" and self.selection is not None:
            self.selected.emit(self.selection)
        self.dragging = None
        self.drag_start = None
        self.rect_erase = False
        self.viewport().update()

    def leaveEvent(self, event):
        self.hover = None
        self.viewport().update()

    # ---- Bearbeiten ---------------------------------------------------------------------
    def put_tile(self, x, y):
        kind = self.brush[1] if self.brush[0] == "tile" else "stein"
        self.level["tiles"][f"{x},{y}"] = kind

    def place(self, x, y):
        if not self.inside(x, y):
            return
        kind, what = self.brush
        if kind == "tile":
            self.put_tile(x, y)
        elif kind == "entity":
            ents = self.level["entities"]
            if any(e["x"] == x and e["y"] == y for e in ents):
                return
            if what in proj.SINGLE:
                ents[:] = [e for e in ents if e["kind"] != what]
            e = {"kind": what, "x": x, "y": y}
            if what == "enemy":
                e.update({"range": 3, "speed": 2.0, "model": ""})
            elif what == "npc":
                e.update({"model": "", "height": 1.7, "name": "", "mode": "gespraech", "seconds": 3.0,
                          "once": True, "dialog": [{"who": "npc", "text": "Hallo!"}]})
            ents.append(e)
            self.selection = e
            self.selected.emit(e)
        elif kind == "decor":
            d = {"model": what, "x": x, "y": y, "z": -4.0, "height": 3.0, "rot": 0}
            self.level["decor"].append(d)
            self.selection = d
            self.selected.emit(d)
        self.changed.emit()
        self.viewport().update()

    def erase_at(self, x, y):
        changed = self.level["tiles"].pop(f"{x},{y}", None) is not None
        before = len(self.level["entities"])
        self.level["entities"] = [e for e in self.level["entities"] if not (e["x"] == x and e["y"] == y)]
        changed |= len(self.level["entities"]) != before
        if not changed:
            hit = [d for d in self.level["decor"] if self.decor_rect(d).contains(self.cell_rect(x, y).center())]
            if hit:
                self.level["decor"].remove(hit[-1])
                changed = True
        if changed:
            if self.selection is not None and self.selection not in self.level["entities"] \
                    and self.selection not in self.level["decor"]:
                self.selection = None
                self.selected.emit(None)
            self.changed.emit()
            self.viewport().update()

    def pick(self, pos):
        x, y = self.cell(pos)
        for e in reversed(self.level["entities"]):
            if e["x"] == x and (e["y"] == y or (e["kind"] in ("goal", "npc", "start") and 0 <= y - e["y"] <= 3)):
                return e
        sp = self.mapToScene(pos)
        for d in reversed(self.level["decor"]):
            if self.decor_rect(d).contains(sp):
                return d
        return None

    def delete_selection(self):
        if self.selection is None:
            return
        self.snapshot()
        for lst in (self.level["entities"], self.level["decor"]):
            if self.selection in lst:
                lst.remove(self.selection)
        self.selection = None
        self.selected.emit(None)
        self.changed.emit()
        self.viewport().update()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selection()
            return
        super().keyPressEvent(event)


class DialogLines(QWidget):
    """Liste der Sprechblasen eines NPCs: wer spricht, was gesagt wird. Reihenfolge = Ablauf im Spiel."""

    def __init__(self, lines, changed):
        super().__init__()
        self.lines = lines
        self.changed = changed
        self.v = QVBoxLayout(self)
        self.v.setContentsMargins(0, 0, 0, 0)
        self.v.setSpacing(6)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(8)
        self.v.addLayout(self.rows)
        add = QHBoxLayout()
        for who, label in (("npc", "+ NPC sagt"), ("spieler", "+ Spieler sagt")):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, w=who: self.add(w))
            add.addWidget(b)
        self.v.addLayout(add)
        self.fill()

    def fill(self):
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, line in enumerate(self.lines):
            box = QWidget(objectName="panel")
            bv = QVBoxLayout(box)
            bv.setContentsMargins(8, 6, 8, 8)
            bv.setSpacing(4)
            top = QHBoxLayout()
            who = QComboBox()
            who.addItem("NPC sagt", "npc")
            who.addItem("Spieler sagt", "spieler")
            who.setCurrentIndex(max(0, who.findData(line.get("who", "npc"))))
            who.currentIndexChanged.connect(lambda _i, l=line, w=who: self.set(l, "who", w.currentData()))
            top.addWidget(who, 1)
            for icon, tip, func in (("up", "Nach oben", lambda _=False, n=i: self.move(n, -1)),
                                    ("trash", "Entfernen", lambda _=False, n=i: self.remove(n))):
                b = QToolButton()
                b.setIcon(icons.icon(icon, C["danger"] if icon == "trash" else C["text"]))
                b.setToolTip(tip)
                b.clicked.connect(func)
                b.setEnabled(icon == "trash" or i > 0)
                top.addWidget(b)
            bv.addLayout(top)
            text = QPlainTextEdit(line.get("text", ""))
            text.setFixedHeight(58)
            text.setPlaceholderText("Was wird gesagt?")
            text.textChanged.connect(lambda l=line, t=text: self.set(l, "text", t.toPlainText()))
            bv.addWidget(text)
            self.rows.addWidget(box)

    def set(self, line, key, value):
        line[key] = value
        self.changed()

    def add(self, who):
        self.lines.append({"who": who, "text": ""})
        self.fill()
        self.changed()

    def remove(self, i):
        del self.lines[i]
        self.fill()
        self.changed()

    def move(self, i, d):
        j = i + d
        if 0 <= j < len(self.lines):
            self.lines[i], self.lines[j] = self.lines[j], self.lines[i]
            self.fill()
            self.changed()


class LevelEditor(QWidget):
    changed = Signal()
    importModel = Signal()          # Bitte eine GLB ins Projekt holen (Rückgabe über add_model)

    def __init__(self, host):
        super().__init__()
        self.host = host
        self.level = None
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Palette links
        side = QWidget(objectName="side")
        side.setFixedWidth(262)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(12, 12, 12, 12)
        sv.setSpacing(8)
        tools = QHBoxLayout()
        self.tool_group = QButtonGroup(self)
        for key, icon, tip in (("paint", "pencil", "Malen / Setzen (B)"), ("rect", "rect", "Rechteck füllen (R)"),
                               ("erase", "eraser", "Radierer (E) – mit Umschalt als Rechteck"),
                               ("select", "cursor", "Auswählen und verschieben (V)")):
            b = QToolButton()
            b.setCheckable(True)
            b.setIcon(icons.icon(icon, C["text"], C["accent"]))
            b.setIconSize(b.iconSize() * 1.2)
            b.setToolTip(tip)
            b.setChecked(key == "paint")
            b.clicked.connect(lambda _=False, k=key: self.set_tool(k))
            self.tool_group.addButton(b)
            tools.addWidget(b)
        undo = QToolButton()
        undo.setIcon(icons.icon("undo", C["text"]))
        undo.setToolTip("Rückgängig (Strg+Z)")
        undo.clicked.connect(lambda: self.view.undo())
        tools.addStretch(1)
        tools.addWidget(undo)
        sv.addLayout(tools)
        self.tool_buttons = self.tool_group.buttons()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        holder = QWidget()
        pv = QVBoxLayout(holder)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(6)
        self.palette_group = QButtonGroup(self)
        self.palette_group.setExclusive(True)
        pv.addWidget(QLabel("BLÖCKE", objectName="section"))
        grid = QWidget()
        from PySide6.QtWidgets import QGridLayout
        gl = QGridLayout(grid)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(4)
        for i, (key, name, color) in enumerate(proj.TILES):
            b = self.palette_button(name, ("tile", key), swatch=color)
            gl.addWidget(b, i // 2, i % 2)
        pv.addWidget(grid)
        pv.addSpacing(6)
        pv.addWidget(QLabel("OBJEKTE", objectName="section"))
        grid2 = QWidget()
        gl2 = QGridLayout(grid2)
        gl2.setContentsMargins(0, 0, 0, 0)
        gl2.setSpacing(4)
        for i, (key, name, desc) in enumerate(proj.ENTITIES):
            b = self.palette_button(name, ("entity", key), tip=desc)
            gl2.addWidget(b, i // 2, i % 2)
        pv.addWidget(grid2)
        pv.addSpacing(6)
        pv.addWidget(QLabel("KULISSE (3D-MODELLE)", objectName="section"))
        hint = QLabel("GLB-Dateien hinter der Spielebene – Bäume, Häuser, Berge …")
        hint.setObjectName("sub")
        hint.setWordWrap(True)
        pv.addWidget(hint)
        self.models = QListWidget()
        self.models.setMinimumHeight(110)
        self.models.itemClicked.connect(self.model_clicked)
        pv.addWidget(self.models)
        add = QPushButton("+ GLB hinzufügen …")
        add.clicked.connect(self.importModel)
        pv.addWidget(add)
        pv.addStretch(1)
        scroll.setWidget(holder)
        sv.addWidget(scroll, 1)
        h.addWidget(side)

        self.view = LevelView()
        self.view.changed.connect(self.on_changed)
        self.view.selected.connect(self.show_props)
        h.addWidget(self.view, 1)

        # Eigenschaften rechts
        self.props = QScrollArea(objectName="props")
        self.props.setFixedWidth(300)
        self.props.setWidgetResizable(True)
        self.props.setFrameShape(QScrollArea.Shape.NoFrame)
        self.props.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self.props.setWidget(inner)
        self.pv = QVBoxLayout(inner)
        self.pv.setContentsMargins(14, 14, 14, 14)
        self.pv.setSpacing(10)
        h.addWidget(self.props)
        self.prop_body = None
        self.palette_group.buttons()[0].setChecked(True)

    def palette_button(self, name, brush, swatch=None, tip=None):
        b = QToolButton()
        b.setCheckable(True)
        b.setText(name)
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        b.setMinimumWidth(112)
        b.setToolTip(tip or name)
        from PySide6.QtGui import QIcon, QPixmap
        pm = QPixmap(36, 36)
        pm.fill(Qt.GlobalColor.transparent)
        pp = QPainter(pm)
        pp.setRenderHint(QPainter.RenderHint.Antialiasing)
        if swatch:
            pp.setPen(QPen(QColor(swatch).darker(130), 2))
            pp.setBrush(QColor(swatch))
            pp.drawRoundedRect(QRectF(4, 4, 28, 28), 6, 6)
        else:
            draw_entity(pp, brush[1], QRectF(6, 10, 24, 24), {"range": 0})
        pp.end()
        b.setIcon(QIcon(pm))
        b.clicked.connect(lambda: self.set_brush(brush))
        self.palette_group.addButton(b)
        return b

    def set_tool(self, key):
        self.view.tool = key
        for b, k in zip(self.tool_buttons, ("paint", "rect", "erase", "select")):
            b.setChecked(k == key)
        self.view.viewport().update()

    def set_brush(self, brush):
        self.view.brush = brush
        if self.view.tool in ("erase", "select"):
            self.set_tool("paint")
        if brush[0] == "entity" and self.view.tool == "rect":
            self.set_tool("paint")

    def model_clicked(self, item):
        self.palette_group.setExclusive(False)
        for b in self.palette_group.buttons():
            b.setChecked(False)
        self.palette_group.setExclusive(True)
        self.set_brush(("decor", item.data(Qt.ItemDataRole.UserRole)))

    def refresh_models(self, models):
        self.models.clear()
        for rel in models:
            item = QListWidgetItem(icons.icon("model", C["accent"]), Path(rel).stem)
            item.setData(Qt.ItemDataRole.UserRole, rel)
            self.models.addItem(item)

    def set_level(self, level):
        self.level = level
        self.view.set_level(level)
        self.show_props(None)

    def on_changed(self):
        self.changed.emit()

    def keyPressEvent(self, event):
        keys = {Qt.Key.Key_B: "paint", Qt.Key.Key_R: "rect", Qt.Key.Key_E: "erase", Qt.Key.Key_V: "select"}
        if event.key() in keys and not event.modifiers():
            self.set_tool(keys[event.key()])
            return
        super().keyPressEvent(event)

    # ---- Eigenschaften ------------------------------------------------------------------
    def clear_props(self):
        while self.pv.count():
            item = self.pv.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                self._drop_layout(item.layout())

    def _drop_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._drop_layout(item.layout())

    def color_button(self, value, setter):
        b = QPushButton(value)
        b.setStyleSheet(f"QPushButton{{background:{value};color:{'#12151b' if QColor(value).lightness() > 128 else '#ffffff'};}}")

        def pick():
            c = QColorDialog.getColor(QColor(b.text()), self, "Farbe wählen")
            if c.isValid():
                b.setText(c.name())
                b.setStyleSheet(f"QPushButton{{background:{c.name()};color:{'#12151b' if c.lightness() > 128 else '#ffffff'};}}")
                setter(c.name())
        b.clicked.connect(pick)
        return b

    def show_props(self, sel):
        self.clear_props()
        if not self.level:
            return
        if sel is None:
            title = QLabel("Level")
            title.setObjectName("heading")
            title.setStyleSheet("font-size:18px")
            self.pv.addWidget(title)
            form = QFormLayout()
            name = QLineEdit(self.level.get("name", ""))
            name.textEdited.connect(lambda t: self.set_value(self.level, "name", t))
            w = QSpinBox()
            w.setRange(20, 1000)
            w.setValue(self.level["width"])
            w.valueChanged.connect(lambda v: (self.set_value(self.level, "width", v), self.view.resize_scene()))
            hh = QSpinBox()
            hh.setRange(10, 80)
            hh.setValue(self.level["height"])
            hh.valueChanged.connect(lambda v: (self.set_value(self.level, "height", v), self.view.resize_scene()))
            form.addRow("Name", name)
            form.addRow("Breite", w)
            form.addRow("Höhe", hh)
            form.addRow("Himmel", self.color_button(self.level.get("sky", "#8ec5ff"),
                                                    lambda c: (self.set_value(self.level, "sky", c), self.view.viewport().update())))
            form.addRow("Boden hinten", self.color_button(self.level.get("ground", "#6f9e5c"),
                                                          lambda c: self.set_value(self.level, "ground", c)))
            self.pv.addLayout(form)
            tip = QLabel("<b>So geht's</b><br>Links einen Block oder ein Objekt wählen und ins Raster klicken. "
                         "Rechtsklick löscht. Mausrad blättert, Strg+Mausrad zoomt, mittlere Maustaste verschiebt.<br><br>"
                         "Jedes Level braucht einen <b>Spielerstart</b> und ein <b>Ziel</b>.")
            tip.setWordWrap(True)
            tip.setObjectName("sub")
            self.pv.addWidget(tip)
            self.pv.addStretch(1)
            return
        is_decor = "model" in sel and "kind" not in sel
        title = QLabel("Kulisse" if is_decor else ENTITY_NAME.get(sel.get("kind"), "Objekt"))
        title.setStyleSheet("font-size:18px;font-weight:700")
        self.pv.addWidget(title)
        form = QFormLayout()
        if is_decor:
            form.addRow("Modell", QLabel(Path(sel.get("model", "")).name))
            for key, label, lo, hi, step in (("height", "Höhe (Blöcke)", 0.2, 60, 0.5),
                                             ("z", "Tiefe (minus = hinten)", -60, 10, 0.5),
                                             ("rot", "Drehung (Grad)", -180, 180, 15)):
                s = QDoubleSpinBox()
                s.setRange(lo, hi)
                s.setSingleStep(step)
                s.setValue(float(sel.get(key, 0)))
                s.valueChanged.connect(lambda v, k=key: (self.set_value(sel, k, v), self.view.viewport().update()))
                form.addRow(label, s)
        else:
            kind = sel.get("kind")
            if kind == "enemy":
                r = QDoubleSpinBox()
                r.setRange(0.5, 40)
                r.setValue(float(sel.get("range", 3)))
                r.valueChanged.connect(lambda v: (self.set_value(sel, "range", v), self.view.viewport().update()))
                s = QDoubleSpinBox()
                s.setRange(0.5, 12)
                s.setValue(float(sel.get("speed", 2)))
                s.valueChanged.connect(lambda v: self.set_value(sel, "speed", v))
                form.addRow("Laufweg (Blöcke)", r)
                form.addRow("Tempo", s)
            if kind == "npc":
                proj.upgrade_npc(sel)
                name = QLineEdit(sel.get("name", ""))
                name.setPlaceholderText("z. B. Lotte (steht über der Blase)")
                name.textEdited.connect(lambda t: self.set_value(sel, "name", t))
                form.addRow("Name", name)
                mode = QComboBox()
                mode.addItem("Gespräch (Figur wartet)", "gespraech")
                mode.addItem("Nebenbei (läuft von selbst)", "nebenbei")
                mode.setCurrentIndex(max(0, mode.findData(sel.get("mode", "gespraech"))))
                mode.currentIndexChanged.connect(lambda _i: self.set_value(sel, "mode", mode.currentData()))
                mode.setToolTip("Gespräch: Die Spielfigur bleibt stehen, weiter mit Leertaste, Enter oder Klick.\n"
                                "Nebenbei: Die Blasen wechseln von selbst, man kann weiterlaufen.")
                form.addRow("Art", mode)
                secs = QDoubleSpinBox()
                secs.setRange(0.5, 30)
                secs.setSingleStep(0.5)
                secs.setSuffix(" s")
                secs.setValue(float(sel.get("seconds", 3.0)))
                secs.setToolTip("Wie lange jede Blase bei „Nebenbei“ stehen bleibt")
                secs.valueChanged.connect(lambda v: self.set_value(sel, "seconds", v))
                form.addRow("Je Blase", secs)
                once = QCheckBox("Nur beim ersten Vorbeikommen")
                once.setChecked(bool(sel.get("once", True)))
                once.toggled.connect(lambda v: self.set_value(sel, "once", v))
                form.addRow("", once)
            if kind in ("enemy", "npc"):
                model = QPushButton(Path(sel.get("model", "")).name or "Standardfigur")
                model.clicked.connect(lambda: self.host.choose_model_for(sel, model))
                form.addRow("3D-Figur", model)
        self.pv.addLayout(form)
        if not is_decor and sel.get("kind") == "npc":
            self.pv.addWidget(QLabel("DIALOG (SPRECHBLASEN)", objectName="section"))
            self.pv.addWidget(DialogLines(sel["dialog"], self.changed.emit))
        delete = QPushButton("Entfernen")
        delete.setIcon(icons.icon("trash", C["danger"]))
        delete.clicked.connect(self.view.delete_selection)
        self.pv.addWidget(delete)
        self.pv.addStretch(1)

    def set_value(self, target, key, value):
        target[key] = value
        self.changed.emit()
