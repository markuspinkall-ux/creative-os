"""Sektor-Editor für den Weltraum-Shooter: Karte von oben, Gegner, Planeten, Raumbasen und Asteroiden frei setzen.

Koordinaten in Metern wie im Spiel: x nach rechts, z nach unten auf der Karte (im Spiel „nach hinten“),
y ist die Höhe (wird rechts in den Eigenschaften eingestellt und auf der Karte angezeigt).
"""

import copy
import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

from . import icons, project as proj
from .style import C

ENEMY_COLOR = {"jaeger": "#d9534f", "kreuzer": "#8a4fd9", "geschuetz": "#e08a3c"}
ENEMY_HP = {"jaeger": 3, "kreuzer": 14, "geschuetz": 6}
ENEMY_NAME = {k: n for k, n, _d in proj.ENEMY_TYPES}
KIND_NAME = {"start": "Schiffsstart", "enemy": "Gegner", "planet": "Planet", "base": "Raumbasis",
             "asteroids": "Asteroidenfeld", "asteroid": "Asteroid"}
# Palette: (Pinsel, Anzeige, Hinweis)
BRUSHES = [
    (("start", None), "Schiffsstart", "Hier startet das eigene Raumschiff."),
    (("enemy", "jaeger"), "Jäger", "Schnell und wendig, schießt Laser."),
    (("enemy", "kreuzer"), "Kreuzer", "Groß und zäh, schießt Plasma."),
    (("enemy", "geschuetz"), "Geschütz", "Steht still und dreht sich mit."),
    (("planet", None), "Planet", "Zum Hinfliegen und Landen."),
    (("base", None), "Raumbasis", "Repariert das Schiff und füllt Raketen auf."),
    (("asteroids", None), "Asteroidenfeld", "Viele Felsbrocken auf einmal."),
    (("asteroid", None), "Asteroid", "Ein einzelner Felsbrocken, Größe frei wählbar."),
]
PLANET_PRESETS = [("#e0b070", "#b0703a", "#ffd9a0"), ("#bfe6ff", "#6f9ec4", "#bfe6ff"),
                  ("#3f8f4f", "#2f5fb3", "#7fc4ff"), ("#c8673a", "#7a3a22", "#ffb08a"), ("#9a7fd0", "#4a3a7a", "#c9b0ff")]


def new_object(brush, x, z, count):
    kind, sub = brush
    if kind == "enemy":
        return {"kind": "enemy", "type": sub, "x": x, "y": 0, "z": z, "dir": 180}
    if kind == "planet":
        a, b, atmo = PLANET_PRESETS[count % len(PLANET_PRESETS)]
        return {"kind": "planet", "name": f"Planet {count + 1}", "x": x, "y": 0, "z": z, "radius": 140, "color": a,
                "color2": b, "atmosphere": atmo, "ground": a, "landable": True, "ring": False, "bands": 0.0}
    if kind == "base":
        return {"kind": "base", "name": f"Station {count + 1}", "x": x, "y": 0, "z": z, "dir": 0, "repair": 25}
    if kind == "asteroids":
        return {"kind": "asteroids", "x": x, "y": 0, "z": z, "count": 30, "spread": 140, "size": 9, "color": "#6e6259"}
    if kind == "asteroid":
        return {"kind": "asteroid", "x": x, "y": 0, "z": z, "size": 18, "color": "#6e6259"}
    return {"kind": "start", "x": x, "y": 0, "z": z, "dir": 0}


def hit_radius(e):
    k = e["kind"]
    if k == "planet":
        return float(e.get("radius", 140))
    if k == "base":
        return 45.0
    if k == "asteroids":
        return float(e.get("spread", 140))
    if k == "asteroid":
        return max(12.0, float(e.get("size", 18)))
    return 22.0


class SectorView(QWidget):
    """Karte von oben: Mausrad zoomt, mittlere oder rechte Maustaste mit Ziehen verschiebt."""
    changed = Signal()
    selected = Signal(object)
    status = Signal(str)

    def __init__(self):
        super().__init__()
        self.level = None
        self.brush = None
        self.sel = None
        self.scale = 0.32               # Pixel pro Meter
        self.offset = QPointF(0, 0)     # Weltpunkt in der Mitte
        self.drag = None
        self.history = []
        self.future = []
        self.hover = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(400, 300)

    def set_level(self, level):
        self.level = level
        self.sel = None
        self.history.clear()
        self.future.clear()
        self.offset = QPointF(0, 0)
        self.update()

    # Umrechnung
    def to_screen(self, x, z):
        return QPointF(self.width() / 2 + (x - self.offset.x()) * self.scale,
                       self.height() / 2 + (z - self.offset.y()) * self.scale)

    def to_world(self, p):
        return ((p.x() - self.width() / 2) / self.scale + self.offset.x(),
                (p.y() - self.height() / 2) / self.scale + self.offset.y())

    # Rückgängig
    def snapshot(self):
        self.history.append(copy.deepcopy(self.level["entities"]))
        self.history = self.history[-80:]
        self.future.clear()

    def undo(self):
        if self.history:
            self.future.append(copy.deepcopy(self.level["entities"]))
            self.level["entities"][:] = self.history.pop()
            self.after_restore()

    def redo(self):
        if self.future:
            self.history.append(copy.deepcopy(self.level["entities"]))
            self.level["entities"][:] = self.future.pop()
            self.after_restore()

    def after_restore(self):
        self.sel = None
        self.selected.emit(None)
        self.changed.emit()
        self.update()

    def pick(self, pos):
        x, z = self.to_world(pos)
        best, best_d = None, 1e18
        for e in reversed(self.level["entities"]):
            d = math.hypot(e["x"] - x, e["z"] - z)
            r = max(hit_radius(e), 14 / self.scale)
            # kleine Objekte vor großen (Gegner vor dem Planeten dahinter)
            if d <= r and r < best_d:
                best, best_d = e, r
        return best

    def mousePressEvent(self, event):
        if not self.level:
            return
        pos = event.position()
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.RightButton
                                                              and event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.drag = ("pan", pos, QPointF(self.offset))
            return
        if event.button() == Qt.MouseButton.RightButton:
            e = self.pick(pos)
            if e is not None:
                self.snapshot()
                self.level["entities"].remove(e)
                if self.sel is e:
                    self.sel = None
                    self.selected.emit(None)
                self.changed.emit()
                self.update()
                self.status.emit(f"{KIND_NAME.get(e['kind'], 'Objekt')} gelöscht.")
            else:
                self.drag = ("pan", pos, QPointF(self.offset))
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        hit = self.pick(pos)
        if self.brush and not (hit is not None and event.modifiers() & Qt.KeyboardModifier.AltModifier):
            x, z = self.to_world(pos)
            x, z = round(x), round(z)
            self.snapshot()
            if self.brush[0] == "start":
                start = next((e for e in self.level["entities"] if e["kind"] == "start"), None)
                if start:
                    start["x"], start["z"] = x, z
                    obj = start
                else:
                    obj = new_object(self.brush, x, z, 0)
                    self.level["entities"].append(obj)
            else:
                count = sum(1 for e in self.level["entities"] if e["kind"] == self.brush[0])
                obj = new_object(self.brush, x, z, count)
                self.level["entities"].append(obj)
            self.sel = obj
            self.selected.emit(obj)
            self.changed.emit()
            self.drag = ("move", pos, (obj["x"], obj["z"]), False)
            self.update()
            return
        self.sel = hit
        self.selected.emit(hit)
        if hit is not None:
            self.drag = ("move", pos, (hit["x"], hit["z"]), True)
        else:
            self.drag = ("pan", pos, QPointF(self.offset))
        self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()
        x, z = self.to_world(pos)
        self.status.emit(f"x {x:.0f} m · z {z:.0f} m · Zoom {self.scale * 100:.0f} %")
        if not self.drag:
            return
        kind, start = self.drag[0], self.drag[1]
        if kind == "pan":
            d = pos - start
            self.offset = self.drag[2] - QPointF(d.x() / self.scale, d.y() / self.scale)
        elif kind == "move" and self.sel is not None:
            if self.drag[3]:
                self.snapshot()
                self.drag = (kind, start, self.drag[2], False)
            d = pos - start
            self.sel["x"] = round(self.drag[2][0] + d.x() / self.scale)
            self.sel["z"] = round(self.drag[2][1] + d.y() / self.scale)
            self.changed.emit()
        self.update()

    def mouseReleaseEvent(self, event):
        if self.drag and self.drag[0] == "move" and not self.drag[3]:
            self.selected.emit(self.sel)          # Werte rechts auffrischen
        self.drag = None

    def wheelEvent(self, event):
        before = self.to_world(event.position())
        factor = 1.18 if event.angleDelta().y() > 0 else 1 / 1.18
        self.scale = max(0.04, min(4.0, self.scale * factor))
        after = self.to_world(event.position())
        self.offset += QPointF(before[0] - after[0], before[1] - after[1])
        self.update()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.sel is not None:
            self.snapshot()
            self.level["entities"].remove(self.sel)
            self.sel = None
            self.selected.emit(None)
            self.changed.emit()
            self.update()
        elif event.key() == Qt.Key.Key_R and self.sel is not None and "dir" in self.sel:
            self.snapshot()
            self.sel["dir"] = (float(self.sel.get("dir", 0)) + 15) % 360
            self.selected.emit(self.sel)
            self.changed.emit()
            self.update()
        elif event.key() == Qt.Key.Key_Escape:
            self.sel = None
            self.selected.emit(None)
            self.update()
        else:
            super().keyPressEvent(event)

    # Zeichnen
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(self.level.get("sky", "#04060c") if self.level else "#04060c").lighter(130))
        if not self.level:
            return
        # Raster alle 100 m, Achsen
        step = 100 if self.scale > 0.15 else 500
        x0, z0 = self.to_world(QPointF(0, 0))
        x1, z1 = self.to_world(QPointF(self.width(), self.height()))
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        x = math.floor(x0 / step) * step
        while x <= x1:
            s = self.to_screen(x, 0)
            p.drawLine(QPointF(s.x(), 0), QPointF(s.x(), self.height()))
            x += step
        z = math.floor(z0 / step) * step
        while z <= z1:
            s = self.to_screen(0, z)
            p.drawLine(QPointF(0, s.y()), QPointF(self.width(), s.y()))
            z += step
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        o = self.to_screen(0, 0)
        p.drawLine(QPointF(o.x(), 0), QPointF(o.x(), self.height()))
        p.drawLine(QPointF(0, o.y()), QPointF(self.width(), o.y()))
        size = float(self.level.get("size", 1000))
        a, b = self.to_screen(-size, -size), self.to_screen(size, size)
        p.setPen(QPen(QColor(C["accent"]).darker(110), 1, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(a, b))
        order = {"planet": 0, "asteroids": 1, "asteroid": 2, "base": 3, "enemy": 4, "start": 5}
        for e in sorted(self.level["entities"], key=lambda e: order.get(e["kind"], 9)):
            self.draw_object(p, e)
        # Kompass
        p.setPen(QColor(255, 255, 255, 120))
        p.setFont(QFont(p.font().family(), 9))
        p.drawText(QRectF(10, 8, 400, 20), Qt.AlignmentFlag.AlignLeft,
                   "↑ vorne (Flugrichtung beim Start: Pfeil am Schiffsstart)  ·  Raster 100 m" if step == 100 else
                   "Raster 500 m")
        p.end()

    def draw_object(self, p, e):
        k = e["kind"]
        c = self.to_screen(e["x"], e["z"])
        sel = e is self.sel
        if k == "planet":
            r = float(e.get("radius", 140)) * self.scale
            if e.get("atmosphere"):
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(e["atmosphere"]).darker(150))
                p.drawEllipse(c, r * 1.08, r * 1.08)
            p.setBrush(QColor(e.get("color", "#c8673a")))
            p.setPen(QPen(QColor(e.get("color2", "#7a3a22")), max(2, r * 0.08)))
            p.drawEllipse(c, r, r)
            if e.get("ring"):
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(220, 200, 160, 160), max(1.5, r * 0.12)))
                p.drawEllipse(c, r * 1.7, r * 0.5)
            label = e.get("name", "Planet") + ("  ⤓ landbar" if e.get("landable", True) else "")
        elif k == "base":
            r = 45 * self.scale
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor("#6fdcc0"), 2, Qt.PenStyle.DashLine))
            p.drawEllipse(c, r, r)
            p.setPen(QPen(QColor("#c3cad6"), max(2, 4 * self.scale)))
            p.drawEllipse(c, 18 * self.scale + 3, 18 * self.scale + 3)
            p.setBrush(QColor("#9aa3b2"))
            p.drawEllipse(c, 5, 5)
            label = e.get("name", "Raumbasis") + "  ✚ Reparatur"
        elif k == "asteroids":
            r = float(e.get("spread", 140)) * self.scale
            p.setBrush(QColor(110, 98, 89, 40))
            p.setPen(QPen(QColor(e.get("color", "#6e6259")).lighter(140), 1, Qt.PenStyle.DashLine))
            p.drawEllipse(c, r, r * 0.4 if False else r)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(e.get("color", "#6e6259")).lighter(130))
            n = min(int(e.get("count", 30)), 40)
            for i in range(n):
                a = i * 2.399
                d = math.sqrt((i + 0.5) / n) * r
                p.drawEllipse(QPointF(c.x() + math.cos(a) * d, c.y() + math.sin(a) * d), 2.5, 2.5)
            label = f"Asteroiden ×{e.get('count', 30)}"
        elif k == "asteroid":
            r = max(4.0, float(e.get("size", 18)) * self.scale)
            p.setBrush(QColor(e.get("color", "#6e6259")).lighter(120))
            p.setPen(QPen(QColor(0, 0, 0, 120), 1))
            poly = QPolygonF([QPointF(c.x() + math.cos(i * 0.785) * r * (0.8 + 0.25 * ((i * 7) % 3) / 2),
                                      c.y() + math.sin(i * 0.785) * r * (0.8 + 0.25 * ((i * 5) % 3) / 2)) for i in range(8)])
            p.drawPolygon(poly)
            label = "Asteroid"
        else:
            color = QColor("#8fb3ff") if k == "start" else QColor(ENEMY_COLOR.get(e.get("type"), "#d9534f"))
            if k == "enemy" and e.get("color"):
                color = QColor(e["color"])
            size = {"kreuzer": 15, "geschuetz": 10}.get(e.get("type"), 11) if k == "enemy" else 13
            ang = math.radians(float(e.get("dir", 0)))
            # Blickrichtung: dir 0 = nach vorne (−z, auf der Karte nach oben)
            fx, fz = -math.sin(ang), -math.cos(ang)
            tip = QPointF(c.x() + fx * size * 1.4, c.y() + fz * size * 1.4)
            left = QPointF(c.x() + fz * size * 0.8 - fx * size * 0.7, c.y() - fx * size * 0.8 - fz * size * 0.7)
            right = QPointF(c.x() - fz * size * 0.8 - fx * size * 0.7, c.y() + fx * size * 0.8 - fz * size * 0.7)
            p.setBrush(color)
            p.setPen(QPen(color.darker(170), 1.5))
            if k == "enemy" and e.get("type") == "geschuetz":
                p.drawEllipse(c, size * 0.8, size * 0.8)
                p.setPen(QPen(color.lighter(130), 3))
                p.drawLine(c, tip)
            else:
                p.drawPolygon(QPolygonF([tip, left, c, right]))
            if k == "enemy":
                label = e.get("name") or ENEMY_NAME.get(e.get("type"), "Gegner")
            else:
                label = "Start"
            r = size * 1.4
        if sel:
            rr = (r if k not in ("start", "enemy") else r) + 6
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(C["accent"]), 2))
            p.drawEllipse(c, rr, rr)
        height = float(e.get("y", 0))
        if abs(height) >= 1:
            label += f"  ↕ {height:+.0f} m"
        p.setPen(QColor(255, 255, 255, 220 if sel else 150))
        p.setFont(QFont(p.font().family(), 9, QFont.Weight.Bold if sel else QFont.Weight.Normal))
        rr = r if isinstance(r, float) else float(r)
        p.drawText(QPointF(c.x() + min(rr, 400) * 0.72 + 8, c.y() - min(rr, 400) * 0.72 - 2), label)


class SpaceEditor(QWidget):
    changed = Signal()
    importModel = Signal()

    def __init__(self, host):
        super().__init__()
        self.host = host
        self.level = None
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QWidget(objectName="side")
        side.setFixedWidth(262)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(12, 12, 12, 12)
        sv.setSpacing(8)
        top = QHBoxLayout()
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        pick = QToolButton()
        pick.setCheckable(True)
        pick.setChecked(True)
        pick.setText("Auswählen")
        pick.setIcon(icons.icon("cursor", C["text"], C["accent"]))
        pick.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        pick.setToolTip("Auswählen und verschieben (Esc)")
        pick.clicked.connect(lambda: self.set_brush(None))
        self.group.addButton(pick)
        top.addWidget(pick, 1)
        undo = QToolButton()
        undo.setIcon(icons.icon("undo", C["text"]))
        undo.setToolTip("Rückgängig (Strg+Z)")
        undo.clicked.connect(lambda: self.view.undo())
        top.addWidget(undo)
        sv.addLayout(top)
        sv.addWidget(QLabel("OBJEKTE SETZEN", objectName="section"))
        grid = QGridLayout()
        grid.setSpacing(4)
        self.brush_buttons = {}
        for i, (brush, name, tip) in enumerate(BRUSHES):
            b = QToolButton()
            b.setCheckable(True)
            b.setText(name)
            b.setToolTip(tip)
            b.setMinimumWidth(112)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            b.clicked.connect(lambda _=False, br=brush: self.set_brush(br))
            self.group.addButton(b)
            self.brush_buttons[brush] = b
            grid.addWidget(b, i // 2, i % 2)
        sv.addLayout(grid)
        tip = QLabel("<b>So geht's</b><br>Objekt wählen und auf die Karte klicken – beliebig oft. Ziehen verschiebt, "
                     "Rechtsklick löscht, R dreht. Mausrad zoomt, mit rechter oder mittlerer Maustaste ins Leere "
                     "ziehen verschiebt die Karte. Höhe, Größe und Farben rechts einstellen.")
        tip.setWordWrap(True)
        tip.setObjectName("sub")
        sv.addWidget(tip)
        sv.addStretch(1)
        h.addWidget(side)
        self.view = SectorView()
        self.view.changed.connect(self.changed)
        self.view.selected.connect(self.show_props)
        h.addWidget(self.view, 1)
        self.props = QScrollArea(objectName="props")
        self.props.setFixedWidth(320)
        self.props.setWidgetResizable(True)
        self.props.setFrameShape(QScrollArea.Shape.NoFrame)
        self.props.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self.props.setWidget(inner)
        self.pv = QVBoxLayout(inner)
        self.pv.setContentsMargins(14, 14, 14, 14)
        self.pv.setSpacing(10)
        h.addWidget(self.props)

    def set_brush(self, brush):
        self.view.brush = brush
        if brush is None:
            self.group.buttons()[0].setChecked(True)
        else:
            self.brush_buttons[brush].setChecked(True)
            self.view.status.emit("Auf die Karte klicken, um das Objekt zu setzen (mehrfach möglich).")

    def set_level(self, level):
        self.level = level
        self.view.set_level(level)
        self.show_props(None)

    # Eigenschaften
    def clear_props(self):
        def drop(layout):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    drop(item.layout())
        drop(self.pv)

    def set_value(self, target, key, value, redraw=True):
        target[key] = value
        self.changed.emit()
        if redraw:
            self.view.update()

    def color_button(self, target, key, default):
        value = target.get(key) or default
        b = QPushButton(value)

        def paint(v):
            b.setText(v)
            b.setStyleSheet(f"QPushButton{{background:{v};color:{'#12151b' if QColor(v).lightness() > 128 else '#ffffff'};}}")

        def pick():
            c = QColorDialog.getColor(QColor(b.text()), self, "Farbe wählen")
            if c.isValid():
                paint(c.name())
                self.set_value(target, key, c.name())
        paint(value)
        b.clicked.connect(pick)
        return b

    def number(self, target, key, lo, hi, step, default, suffix="", decimals=0, redraw=True):
        s = QDoubleSpinBox()
        s.setDecimals(decimals)
        s.setRange(lo, hi)
        s.setSingleStep(step)
        s.setSuffix(suffix)
        s.setValue(float(target.get(key, default)))
        s.valueChanged.connect(lambda v: self.set_value(target, key, int(v) if decimals == 0 else v, redraw))
        return s

    def combo(self, target, key, items, default, after=None):
        cb = QComboBox()
        for k, label in items:
            cb.addItem(label, k)
        cb.setCurrentIndex(max(0, cb.findData(target.get(key, default))))

        def changed(_i):
            self.set_value(target, key, cb.currentData())
            if after:
                after()
        cb.currentIndexChanged.connect(changed)
        return cb

    def check(self, target, key, text, default):
        c = QCheckBox(text)
        c.setChecked(bool(target.get(key, default)))
        c.toggled.connect(lambda v: self.set_value(target, key, v))
        return c

    def heading(self, text):
        t = QLabel(text)
        t.setStyleSheet("font-size:18px;font-weight:700")
        self.pv.addWidget(t)

    def show_props(self, sel):
        self.clear_props()
        if not self.level:
            return
        lvl = self.level
        if sel is None:
            self.heading("Sektor")
            form = QFormLayout()
            name = QLineEdit(lvl.get("name", ""))
            name.textEdited.connect(lambda t: self.set_value(lvl, "name", t, False))
            form.addRow("Name", name)
            form.addRow("Ziel", self.combo(lvl, "goal", proj.GOALS, "gegner", lambda: self.show_props(None)))
            if lvl.get("goal") in ("landen", "basis"):
                kind = "planet" if lvl["goal"] == "landen" else "base"
                names = [e.get("name", "") for e in lvl["entities"] if e["kind"] == kind
                         and (kind != "planet" or e.get("landable", True))]
                form.addRow("Ziel-Ort", self.combo(lvl, "goalTarget", [("", "egal welcher")] + [(n, n) for n in names], ""))
            form.addRow("Kartengröße", self.number(lvl, "size", 300, 5000, 100, 1000, " m"))
            self.pv.addLayout(form)
            self.pv.addWidget(QLabel("HIMMEL", objectName="section"))
            form = QFormLayout()
            form.addRow("Grundfarbe", self.color_button(lvl, "sky", "#04060c"))
            form.addRow("Nebel", self.color_button(lvl, "nebula", "#3a2d6b"))
            form.addRow("Sterne", self.number(lvl, "stars", 0, 4, 0.25, 1.0, "", 2, False))
            form.addRow("Sonnenlicht", self.color_button(lvl, "sunColor", "#fff3e0"))
            img = QPushButton(lvl.get("skyImage", "").split("/")[-1] or "Eigenes Himmelsbild …")
            img.setToolTip("Panoramabild (2:1), z. B. ein Weltraum-Hintergrund. Leer = gezeichnete Sterne.")

            def pick_image():
                rel = self.host.import_file("Himmelsbild wählen", "Bilder (*.png *.jpg *.jpeg *.webp)")
                if rel:
                    self.set_value(lvl, "skyImage", rel, False)
                    self.show_props(None)
            img.clicked.connect(pick_image)
            row = QHBoxLayout()
            row.addWidget(img, 1)
            if lvl.get("skyImage"):
                x = QToolButton()
                x.setIcon(icons.icon("close", C["muted"]))
                x.setToolTip("Gezeichnete Sterne verwenden")
                x.clicked.connect(lambda: (self.set_value(lvl, "skyImage", "", False), self.show_props(None)))
                row.addWidget(x)
            form.addRow("Bild", row)
            self.pv.addLayout(form)
            hz = lvl.setdefault("horizon", {"on": False})
            self.pv.addWidget(QLabel("HORIZONT", objectName="section"))
            on = QCheckBox("Riesiger Planet am Rand der Welt")
            on.setChecked(bool(hz.get("on")))
            on.toggled.connect(lambda v: (self.set_value(hz, "on", v, False), self.show_props(None)))
            self.pv.addWidget(on)
            if hz.get("on"):
                form = QFormLayout()
                form.addRow("Seite", self.combo(hz, "side", proj.HORIZON_SIDES, "unten"))
                form.addRow("Farbe 1", self.color_button(hz, "color", "#2f5fb3"))
                form.addRow("Farbe 2", self.color_button(hz, "color2", "#3f8f4f"))
                form.addRow("Atmosphäre", self.color_button(hz, "atmosphere", "#7fc4ff"))
                form.addRow("Abstand", self.number(hz, "distance", 100, 5000, 50, 900, " m", 0, False))
                form.addRow("Streifen (Gasriese)", self.number(hz, "bands", 0, 1, 0.1, 0.0, "", 1, False))
                self.pv.addLayout(form)
            counts = {}
            for e in lvl["entities"]:
                counts[e["kind"]] = counts.get(e["kind"], 0) + 1
            info = QLabel(" · ".join(f"{KIND_NAME[k]} {n}" for k, n in counts.items() if k in KIND_NAME))
            info.setObjectName("sub")
            info.setWordWrap(True)
            self.pv.addWidget(info)
            self.pv.addStretch(1)
            return
        k = sel["kind"]
        self.heading(KIND_NAME.get(k, "Objekt") if k != "enemy" else f"Gegner · {ENEMY_NAME.get(sel.get('type'), '')}")
        form = QFormLayout()
        if k in ("planet", "base", "enemy"):
            name = QLineEdit(sel.get("name", ""))
            name.setPlaceholderText(ENEMY_NAME.get(sel.get("type"), "") if k == "enemy" else "")
            name.textEdited.connect(lambda t: self.set_value(sel, "name", t))
            form.addRow("Name", name)
        if k == "enemy":
            def retype():
                sel["hp"] = ENEMY_HP.get(sel["type"], 3)
                sel.pop("color", None)
                self.show_props(sel)
            form.addRow("Typ", self.combo(sel, "type", [(a, f"{n} – {d}") for a, n, d in proj.ENEMY_TYPES], "jaeger", retype))
            form.addRow("Treffer bis zerstört", self.number(sel, "hp", 1, 200, 1, ENEMY_HP.get(sel.get("type"), 3)))
            form.addRow("Waffe", self.combo(sel, "weapon", [("", "Standard")] + proj.WEAPON_TYPES, ""))
            if sel.get("type") != "geschuetz":
                form.addRow("Tempo", self.number(sel, "speed", 0, 200, 2, {"jaeger": 46, "kreuzer": 14}.get(sel.get("type"), 30), " m/s"))
            form.addRow("Farbe", self.color_button(sel, "color", ENEMY_COLOR.get(sel.get("type"), "#d9534f")))
            model = QPushButton(sel.get("model", "").split("/")[-1] or "Eingebautes Schiff")
            model.setIcon(icons.icon("model", C["accent"]))
            model.clicked.connect(lambda: self.host.choose_model_for(sel, model))
            form.addRow("3D-Modell (GLB)", model)
        elif k == "planet":
            form.addRow("Radius", self.number(sel, "radius", 20, 2000, 10, 140, " m"))
            form.addRow("Farbe 1", self.color_button(sel, "color", "#c8673a"))
            form.addRow("Farbe 2", self.color_button(sel, "color2", "#7a3a22"))
            form.addRow("Boden (gelandet)", self.color_button(sel, "ground", sel.get("color", "#c8673a")))
            atmo = QCheckBox("Atmosphäre (Leuchtrand)")
            atmo.setChecked(bool(sel.get("atmosphere")))
            atmo.toggled.connect(lambda v: (self.set_value(sel, "atmosphere", "#bfe6ff" if v else ""), self.show_props(sel)))
            form.addRow("", atmo)
            if sel.get("atmosphere"):
                form.addRow("Farbe Atmosphäre", self.color_button(sel, "atmosphere", "#bfe6ff"))
            form.addRow("", self.check(sel, "landable", "Landen möglich (L)", True))
            form.addRow("", self.check(sel, "ring", "Ring wie Saturn", False))
            form.addRow("Streifen (Gasriese)", self.number(sel, "bands", 0, 1, 0.1, 0.0, "", 1, False))
            form.addRow("Oberflächen-Detail", self.number(sel, "detail", 0.5, 12, 0.5, 3.0, "", 1, False))
        elif k == "base":
            form.addRow("Reparatur pro Sekunde", self.number(sel, "repair", 1, 200, 5, 25, " Punkte"))
            model = QPushButton(sel.get("model", "").split("/")[-1] or "Eingebaute Station")
            model.setIcon(icons.icon("model", C["accent"]))
            model.clicked.connect(lambda: self.host.choose_model_for(sel, model))
            form.addRow("3D-Modell (GLB)", model)
        elif k == "asteroids":
            form.addRow("Anzahl", self.number(sel, "count", 1, 400, 5, 30))
            form.addRow("Ausdehnung", self.number(sel, "spread", 20, 2000, 10, 140, " m"))
            form.addRow("Größte Brocken", self.number(sel, "size", 2, 80, 1, 9, " m"))
            form.addRow("Farbe", self.color_button(sel, "color", "#6e6259"))
        elif k == "asteroid":
            form.addRow("Größe", self.number(sel, "size", 2, 400, 2, 18, " m"))
            form.addRow("Farbe", self.color_button(sel, "color", "#6e6259"))
        form.addRow("x", self.number(sel, "x", -20000, 20000, 10, 0, " m"))
        form.addRow("z", self.number(sel, "z", -20000, 20000, 10, 0, " m"))
        form.addRow("Höhe (y)", self.number(sel, "y", -5000, 5000, 10, 0, " m"))
        if k in ("start", "enemy", "base"):
            form.addRow("Richtung", self.number(sel, "dir", -360, 360, 15, 0, "°"))
        self.pv.addLayout(form)
        delete = QPushButton("Löschen")
        delete.setIcon(icons.icon("trash", C["danger"]))

        def remove():
            self.view.snapshot()
            self.level["entities"].remove(sel)
            self.view.sel = None
            self.changed.emit()
            self.view.update()
            self.show_props(None)
        delete.clicked.connect(remove)
        if k != "start":
            self.pv.addWidget(delete)
        self.pv.addStretch(1)
