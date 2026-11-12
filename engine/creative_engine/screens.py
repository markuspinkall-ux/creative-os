"""Editoren für Splash, Zwischentext und Menü: 16:9-Vorschau wie im Spiel, Menü-Elemente per Maus verschieben."""

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from . import icons, project as proj
from .style import C

BASE_W, BASE_H = 1280, 720


class Screen(QWidget):
    """Zeichnet einen Bildschirm so, wie ihn das Spiel zeigt (Maßstab 1280×720)."""
    selected = Signal(object)
    changed = Signal()

    def __init__(self, host):
        super().__init__()
        self.host = host
        self.step = None
        self.selection = None
        self.drag = None
        self.setMinimumSize(480, 270)
        self.setMouseTracking(True)
        self._pix = {}

    def set_step(self, step):
        self.step = step
        self.selection = None
        self.update()

    def pixmap(self, rel):
        if not rel:
            return None
        path = Path(self.host.folder) / rel if self.host.folder else Path(rel)
        key = (str(path), path.stat().st_mtime if path.exists() else 0)
        if key not in self._pix:
            pm = QPixmap(str(path))
            self._pix[key] = pm if not pm.isNull() else None
        return self._pix[key]

    def frame(self):
        r = QRectF(self.rect()).adjusted(24, 24, -24, -24)
        scale = min(r.width() / BASE_W, r.height() / BASE_H)
        w, h = BASE_W * scale, BASE_H * scale
        return QRectF(r.center().x() - w / 2, r.center().y() - h / 2, w, h), scale

    def element_rect(self, e, frame):
        f, _s = frame
        w, h = float(e.get("w", 0.3)) * f.width(), float(e.get("h", 0.1)) * f.height()
        cx, cy = f.x() + float(e.get("x", 0.5)) * f.width(), f.y() + float(e.get("y", 0.5)) * f.height()
        return QRectF(cx - w / 2, cy - h / 2, w, h)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
                         | QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(C["view"]))
        if not self.step:
            return
        fr = self.frame()
        f, scale = fr
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawRoundedRect(f.translated(0, 6), 10, 10)
        p.save()
        p.setClipRect(f)
        p.fillRect(f, QColor(self.step.get("bg", "#000000")))
        bg = self.pixmap(self.step.get("bgImage", ""))
        if bg:
            scaled = bg.scaled(f.size().toSize(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int(f.center().x() - scaled.width() / 2), int(f.center().y() - scaled.height() / 2), scaled)
        kind = self.step["type"]
        if kind == "splash":
            self.paint_splash(p, f, scale)
        elif kind == "text":
            self.paint_text(p, f, scale)
        elif kind == "menu":
            for e in self.step.get("elements", []):
                self.paint_element(p, e, self.element_rect(e, fr), scale)
        p.restore()
        p.setPen(QPen(QColor(C["line"]), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(f)
        if kind == "menu" and self.selection is not None:
            r = self.element_rect(self.selection, fr)
            p.setPen(QPen(QColor(C["accent"]), 2, Qt.PenStyle.DashLine))
            p.drawRoundedRect(r.adjusted(-4, -4, 4, 4), 6, 6)
            p.setBrush(QColor(C["accent"]))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(r.bottomRight() + QPointF(4, 4), 6, 6)

    def font(self, size, scale, bold=False):
        f = QFont()
        f.setPixelSize(max(6, int(size * scale)))
        f.setBold(bold)
        return f

    def paint_splash(self, p, f, scale):
        s = self.step
        logo = self.pixmap(s.get("logo", ""))
        text = s.get("text", "")
        logo_h = f.height() * float(s.get("logoSize", 0.35)) if logo else 0
        text_h = float(s.get("textSize", 26)) * scale * 1.6 if text else 0
        gap = 16 * scale if logo and text else 0
        top = f.center().y() - (logo_h + gap + text_h) / 2
        if logo:
            pm = logo.scaledToHeight(max(1, int(logo_h)), Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int(f.center().x() - pm.width() / 2), int(top), pm)
        elif not text:
            p.setPen(QColor(255, 255, 255, 90))
            p.setFont(self.font(22, scale))
            p.drawText(f, Qt.AlignmentFlag.AlignCenter, "Logo oder Text hinzufügen →")
        if text:
            p.setPen(QColor(s.get("textColor", "#ffffff")))
            p.setFont(self.font(float(s.get("textSize", 26)), scale))
            p.drawText(QRectF(f.x(), top + logo_h + gap, f.width(), text_h), Qt.AlignmentFlag.AlignCenter, text)

    def paint_text(self, p, f, scale):
        s = self.step
        color = QColor(s.get("textColor", "#ffffff"))
        p.setPen(color)
        p.setFont(self.font(float(s.get("textSize", 34)), scale))
        p.drawText(f.adjusted(60 * scale, 0, -60 * scale, 0),
                   Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, s.get("text", ""))
        color.setAlpha(130)
        p.setPen(color)
        p.setFont(self.font(16, scale))
        p.drawText(f.adjusted(0, 0, 0, -30 * scale), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                   "Weiter mit Leertaste oder Klick")

    def paint_element(self, p, e, r, scale):
        kind = e.get("kind")
        if kind == "button":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(e.get("color", "#8fb3ff")))
            rad = float(e.get("radius", 14)) * scale
            p.drawRoundedRect(r, rad, rad)
            p.setPen(QColor(e.get("textColor", "#12151b")))
            p.setFont(self.font(float(e.get("size", 28)), scale))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, e.get("text", "Knopf"))
        elif kind == "image":
            pm = self.pixmap(e.get("image", ""))
            if pm:
                scaled = pm.scaled(r.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
                p.drawPixmap(int(r.center().x() - scaled.width() / 2), int(r.center().y() - scaled.height() / 2), scaled)
            else:
                p.setPen(QPen(QColor(255, 255, 255, 120), 1, Qt.PenStyle.DashLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(r)
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, "Bild")
        else:
            p.setPen(QColor(e.get("color", "#ffffff")))
            p.setFont(self.font(float(e.get("size", 48)), scale, bool(e.get("bold"))))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, e.get("text", ""))

    # ---- Maus (nur Menü) ---------------------------------------------------------------
    def hit(self, pos):
        fr = self.frame()
        if self.selection is not None:
            r = self.element_rect(self.selection, fr)
            if QRectF(r.bottomRight() + QPointF(-4, -4), r.bottomRight() + QPointF(12, 12)).contains(pos):
                return self.selection, "size"
        for e in reversed(self.step.get("elements", [])):
            if self.element_rect(e, fr).contains(pos):
                return e, "move"
        return None, None

    def mousePressEvent(self, event):
        if not self.step or self.step["type"] != "menu":
            return
        pos = event.position()
        e, mode = self.hit(pos)
        self.selection = e
        self.selected.emit(e)
        if e is not None:
            self.drag = (mode, pos, dict(e))
        self.update()

    def mouseMoveEvent(self, event):
        if not self.step or self.step["type"] != "menu":
            return
        pos = event.position()
        if self.drag is None:
            _e, mode = self.hit(pos)
            self.setCursor(Qt.CursorShape.SizeFDiagCursor if mode == "size" else
                           Qt.CursorShape.OpenHandCursor if mode == "move" else Qt.CursorShape.ArrowCursor)
            return
        mode, start, orig = self.drag
        f, _s = self.frame()
        dx, dy = (pos.x() - start.x()) / f.width(), (pos.y() - start.y()) / f.height()
        e = self.selection
        if mode == "move":
            e["x"] = round(min(1.0, max(0.0, orig["x"] + dx)), 3)
            e["y"] = round(min(1.0, max(0.0, orig["y"] + dy)), 3)
            # Einrasten an der Mitte
            if abs(e["x"] - 0.5) < 0.012:
                e["x"] = 0.5
        else:
            e["w"] = round(max(0.03, orig["w"] + dx * 2), 3)
            e["h"] = round(max(0.03, orig["h"] + dy * 2), 3)
        self.changed.emit()
        self.update()

    def mouseReleaseEvent(self, event):
        if self.drag is not None:
            self.drag = None
            self.selected.emit(self.selection)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.selection is not None:
            self.step["elements"].remove(self.selection)
            self.selection = None
            self.selected.emit(None)
            self.changed.emit()
            self.update()
            return
        super().keyPressEvent(event)


class ScreenEditor(QWidget):
    changed = Signal()

    def __init__(self, host):
        super().__init__()
        self.host = host
        self.step = None
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.screen = Screen(host)
        self.screen.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.screen.changed.connect(self.changed)
        self.screen.selected.connect(self.show_element)
        h.addWidget(self.screen, 1)
        self.props = QWidget(objectName="props")
        self.props.setFixedWidth(300)
        self.pv = QVBoxLayout(self.props)
        self.pv.setContentsMargins(16, 16, 16, 16)
        self.pv.setSpacing(10)
        h.addWidget(self.props)

    # ---- Bausteine ---------------------------------------------------------------------
    def clear(self):
        def drop(layout):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    drop(item.layout())
        drop(self.pv)

    def set(self, target, key, value):
        target[key] = value
        self.screen.update()
        self.changed.emit()

    def color(self, target, key, default):
        b = QPushButton()

        def paint(value):
            light = QColor(value).lightness() > 128
            b.setText(value)
            b.setStyleSheet(f"QPushButton{{background:{value};color:{'#12151b' if light else '#ffffff'};}}")
        paint(target.get(key, default))

        def pick():
            c = QColorDialog.getColor(QColor(target.get(key, default)), self, "Farbe wählen")
            if c.isValid():
                paint(c.name())
                self.set(target, key, c.name())
        b.clicked.connect(pick)
        return b

    def number(self, target, key, default, lo, hi, step=1.0, decimals=1):
        if decimals == 0:
            s = QSpinBox()
            s.setRange(int(lo), int(hi))
            s.setValue(int(target.get(key, default)))
        else:
            s = QDoubleSpinBox()
            s.setDecimals(decimals)
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setValue(float(target.get(key, default)))
        s.valueChanged.connect(lambda v: self.set(target, key, v))
        return s

    def line(self, target, key):
        e = QLineEdit(str(target.get(key, "")))
        e.textEdited.connect(lambda t: self.set(target, key, t))
        return e

    def image(self, target, key, label="Bild wählen …"):
        row = QHBoxLayout()
        b = QPushButton(Path(target.get(key, "")).name or label)
        b.setIcon(icons.icon("image", C["text"]))

        def pick():
            rel = self.host.import_file("Bild wählen", "Bilder (*.png *.jpg *.jpeg *.webp)")
            if rel:
                b.setText(Path(rel).name)
                self.set(target, key, rel)
        b.clicked.connect(pick)
        x = QPushButton()
        x.setObjectName("ghost")
        x.setIcon(icons.icon("close", C["muted"]))
        x.setToolTip("Bild entfernen")
        x.clicked.connect(lambda: (b.setText(label), self.set(target, key, "")))
        row.addWidget(b, 1)
        row.addWidget(x)
        return row

    def heading(self, text):
        l = QLabel(text)
        l.setStyleSheet("font-size:18px;font-weight:700")
        return l

    # ---- Schritt anzeigen ---------------------------------------------------------------
    def set_step(self, step):
        self.step = step
        self.screen.set_step(step)
        self.show_element(None)

    def show_element(self, element):
        self.clear()
        s = self.step
        if s is None:
            return
        kind = s["type"]
        if kind == "menu" and element is not None:
            self.show_menu_element(element)
            return
        self.pv.addWidget(self.heading({"splash": "Splash", "text": "Zwischentext", "menu": "Menü"}[kind]))
        form = QFormLayout()
        form.addRow("Name", self.line(s, "name"))
        form.addRow("Hintergrund", self.color(s, "bg", "#000000"))
        if kind == "splash":
            form.addRow("Logo", self.image(s, "logo", "Logo wählen …"))
            form.addRow("Logogröße", self.number(s, "logoSize", 0.35, 0.05, 0.9, 0.05, 2))
            form.addRow("Text", self.line(s, "text"))
            form.addRow("Textfarbe", self.color(s, "textColor", "#ffffff"))
            form.addRow("Textgröße", self.number(s, "textSize", 26, 8, 160, decimals=0))
            form.addRow("Dauer (s)", self.number(s, "duration", 2.0, 0.5, 15, 0.5))
            form.addRow("Einblenden (s)", self.number(s, "fade", 0.6, 0, 3, 0.1))
        elif kind == "text":
            t = QPlainTextEdit(s.get("text", ""))
            t.setFixedHeight(120)
            t.textChanged.connect(lambda: self.set(s, "text", t.toPlainText()))
            form.addRow("Text", t)
            form.addRow("Textfarbe", self.color(s, "textColor", "#ffffff"))
            form.addRow("Textgröße", self.number(s, "textSize", 40, 8, 160, decimals=0))
            d = self.number(s, "duration", 0, 0, 30, 0.5)
            d.setSpecialValueText("bis Tastendruck")
            form.addRow("Dauer (s)", d)
        else:
            form.addRow("Bild", self.image(s, "bgImage"))
        self.pv.addLayout(form)
        if kind == "menu":
            self.pv.addSpacing(6)
            self.pv.addWidget(QLabel("HINZUFÜGEN", objectName="section"))
            row = QHBoxLayout()
            for label, icon, el in (
                    ("Knopf", "menu", {"kind": "button", "text": "Knopf", "action": "start", "x": 0.5, "y": 0.8,
                                       "w": 0.24, "h": 0.09, "size": 30, "color": C["accent"],
                                       "textColor": "#12151b", "radius": 16}),
                    ("Text", "text", {"kind": "text", "text": "Überschrift", "x": 0.5, "y": 0.2, "w": 0.6,
                                      "h": 0.12, "size": 56, "color": "#ffffff", "bold": True}),
                    ("Bild", "image", {"kind": "image", "image": "", "x": 0.5, "y": 0.4, "w": 0.3, "h": 0.3})):
                b = QPushButton(label)
                b.setIcon(icons.icon(icon, C["text"], C["accent"]))
                b.clicked.connect(lambda _=False, el=el: self.add_element(dict(el)))
                row.addWidget(b)
            self.pv.addLayout(row)
            tip = QLabel("Elemente in der Vorschau anklicken und verschieben, am Punkt unten rechts die Größe ändern. "
                         "Entf löscht.")
            tip.setWordWrap(True)
            tip.setObjectName("sub")
            self.pv.addWidget(tip)
        self.pv.addStretch(1)

    def add_element(self, el):
        self.step.setdefault("elements", []).append(el)
        self.screen.selection = el
        self.screen.update()
        self.changed.emit()
        self.show_element(el)

    def show_menu_element(self, e):
        kind = e.get("kind")
        self.pv.addWidget(self.heading({"button": "Knopf", "image": "Bild"}.get(kind, "Text")))
        form = QFormLayout()
        if kind in ("button", "text"):
            form.addRow("Beschriftung", self.line(e, "text"))
            form.addRow("Schriftgröße", self.number(e, "size", 30, 8, 200, decimals=0))
        if kind == "button":
            form.addRow("Farbe", self.color(e, "color", "#8fb3ff"))
            form.addRow("Textfarbe", self.color(e, "textColor", "#12151b"))
            form.addRow("Rundung", self.number(e, "radius", 16, 0, 60, decimals=0))
            action = QComboBox()
            choices = list(proj.ACTIONS)
            for st in self.host.project["flow"]:
                if st is not self.step:
                    choices.append((f"goto:{st['id']}", f"Springe zu: {st.get('name', st['type'])}"))
            for key, name in choices:
                action.addItem(name, key)
            idx = action.findData(e.get("action", "start"))
            action.setCurrentIndex(max(0, idx))
            action.currentIndexChanged.connect(lambda _i: self.set(e, "action", action.currentData()))
            form.addRow("Beim Klick", action)
        elif kind == "text":
            form.addRow("Farbe", self.color(e, "color", "#ffffff"))
            bold = QCheckBox("Fett")
            bold.setChecked(bool(e.get("bold")))
            bold.toggled.connect(lambda v: self.set(e, "bold", v))
            form.addRow("", bold)
        else:
            form.addRow("Bild", self.image(e, "image"))
        self.pv.addLayout(form)
        row = QHBoxLayout()
        back = QPushButton("Fertig")
        back.clicked.connect(lambda: (setattr(self.screen, "selection", None), self.screen.update(), self.show_element(None)))
        delete = QPushButton("Entfernen")
        delete.setIcon(icons.icon("trash", C["danger"]))

        def remove():
            self.step["elements"].remove(e)
            self.screen.selection = None
            self.screen.update()
            self.changed.emit()
            self.show_element(None)
        delete.clicked.connect(remove)
        row.addWidget(back)
        row.addWidget(delete)
        self.pv.addLayout(row)
        self.pv.addStretch(1)
