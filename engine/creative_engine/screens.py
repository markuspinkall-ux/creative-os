"""Editoren für Splash, Zwischentext und Menü: 16:9-Vorschau wie im Spiel, Menü-Elemente per Maus verschieben."""

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from . import icons, media, project as proj
from .style import C

BASE_W, BASE_H = 1280, 720


TAILS = [("unten-links", "unten links"), ("unten-mitte", "unten Mitte"), ("unten-rechts", "unten rechts"),
         ("oben-links", "oben links"), ("oben-rechts", "oben rechts"), ("keine", "ohne Spitze")]


def paint_bubble(p, r, e, scale):
    """Sprechblase wie im Spiel (bubble.gd): Fläche, Spitze, Name, Text."""
    tail = e.get("tail", "unten-links")
    t = 22 * scale
    body = QRectF(r)
    if tail.startswith("unten"):
        body.setHeight(r.height() - t)
    elif tail.startswith("oben"):
        body.setTop(r.top() + t)
    fill = QColor(e.get("color", "#ffffff"))
    text = QColor(e.get("textColor", "#1c2433"))
    line = text.darker(120) if text.lightness() < 128 else fill.darker(220)
    pen = QPen(line, max(1.0, 3 * scale))
    p.setPen(pen)
    p.setBrush(fill)
    rad = min(26 * scale, body.height() * 0.45)
    p.drawRoundedRect(body, rad, rad)
    if tail != "keine":
        fx = {"links": 0.22, "rechts": 0.78}.get(tail.split("-")[1], 0.5)
        x = body.x() + body.width() * fx
        if tail.startswith("oben"):
            a, b, tip = QPointF(x - 14 * scale, body.top() + 2), QPointF(x + 14 * scale, body.top() + 2), \
                QPointF(x - 6 * scale, r.top())
        else:
            a, b, tip = QPointF(x - 14 * scale, body.bottom() - 2), QPointF(x + 14 * scale, body.bottom() - 2), \
                QPointF(x - 6 * scale, r.bottom())
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF([a, b, tip]))
        p.setPen(pen)
        p.drawLine(a, tip)
        p.drawLine(b, tip)
    inner = body.adjusted(14 * scale, 10 * scale, -14 * scale, -10 * scale)
    size = float(e.get("size", 30))
    if e.get("speaker"):
        f = QFont()
        f.setPixelSize(max(6, int(size * 0.62 * scale)))
        f.setBold(True)
        p.setFont(f)
        c = QColor(text)
        c.setAlpha(170)
        p.setPen(c)
        p.drawText(inner, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, e["speaker"])
        inner.setTop(inner.top() + size * 0.62 * scale + 4)
    f = QFont()
    f.setPixelSize(max(6, int(size * scale)))
    p.setFont(f)
    p.setPen(text)
    p.drawText(inner, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, e.get("text", ""))


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
        cover = self.step.get("bgFit", "cover") == "cover"
        self.paint_media(p, f, self.pixmap(self.step.get("bgImage", "")), cover)
        if self.step.get("bgVideo"):
            self.paint_media(p, f, self.pixmap(media.poster_of(self.step["bgVideo"])), cover, video=True)
        kind = self.step["type"]
        if kind == "splash":
            self.paint_splash(p, f, scale)
        elif kind == "text":
            self.paint_text(p, f, scale)
        elif kind in ("menu", "seite"):
            for e in self.step.get("elements", []):
                self.paint_element(p, e, self.element_rect(e, fr), scale)
        p.restore()
        p.setPen(QPen(QColor(C["line"]), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(f)
        if kind in ("menu", "seite") and self.selection is not None:
            r = self.element_rect(self.selection, fr)
            p.setPen(QPen(QColor(C["accent"]), 2, Qt.PenStyle.DashLine))
            p.drawRoundedRect(r.adjusted(-4, -4, 4, 4), 6, 6)
            p.setBrush(QColor(C["accent"]))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(r.bottomRight() + QPointF(4, 4), 6, 6)

    def paint_media(self, p, r, pm, cover, video=False):
        """Bild/Video-Vorschaubild in r: cover = randlos füllen, sonst ganz zeigen."""
        p.save()
        p.setClipRect(r)
        if pm:
            mode = Qt.AspectRatioMode.KeepAspectRatioByExpanding if cover else Qt.AspectRatioMode.KeepAspectRatio
            scaled = pm.scaled(r.size().toSize(), mode, Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int(r.center().x() - scaled.width() / 2), int(r.center().y() - scaled.height() / 2), scaled)
        elif video:
            p.fillRect(r, QColor(20, 24, 32))
        if video:
            c = r.center()
            rad = max(10.0, min(r.width(), r.height()) * 0.09)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 140))
            p.drawEllipse(c, rad, rad)
            p.setBrush(QColor(255, 255, 255, 230))
            p.drawPolygon(QPolygonF([QPointF(c.x() - rad * 0.35, c.y() - rad * 0.5),
                                     QPointF(c.x() - rad * 0.35, c.y() + rad * 0.5), QPointF(c.x() + rad * 0.55, c.y())]))
        p.restore()

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
        elif kind == "bubble":
            paint_bubble(p, r, e, scale)
        elif kind == "video":
            self.paint_media(p, r, self.pixmap(media.poster_of(e.get("video", ""))), e.get("fit") == "cover", video=True)
        elif kind == "image" and e.get("fit") == "cover":
            self.paint_media(p, r, self.pixmap(e.get("image", "")), True)
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
        if not self.step or self.step["type"] not in ("menu", "seite"):
            return
        pos = event.position()
        e, mode = self.hit(pos)
        self.selection = e
        self.selected.emit(e)
        if e is not None:
            self.drag = (mode, pos, dict(e))
        self.update()

    def mouseMoveEvent(self, event):
        if not self.step or self.step["type"] not in ("menu", "seite"):
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
        self.props = QScrollArea(objectName="props")
        self.props.setFixedWidth(310)
        self.props.setWidgetResizable(True)
        self.props.setFrameShape(QScrollArea.Shape.NoFrame)
        self.props.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self.props.setWidget(inner)
        self.pv = QVBoxLayout(inner)
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

    def video(self, target, key, ratio_key, label="Video wählen …"):
        row = QHBoxLayout()
        b = QPushButton(Path(target.get(key, "")).name or label)
        b.setIcon(icons.icon("play", C["text"], C["accent"]))

        def pick():
            from PySide6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getOpenFileName(self, "Video wählen", str(Path.home()), media.VIDEO_FILTER)
            if not path:
                return
            result = media.import_video(self.host.folder, path, self)
            if isinstance(result, str):
                QMessageBox.warning(self, "Video", result)
                return
            b.setText(Path(result["rel"]).name)
            target[ratio_key] = result["ratio"]
            target["videoLength"] = result["duration"]
            self.set(target, key, result["rel"])
            self.show_again()
        b.clicked.connect(pick)
        x = QPushButton()
        x.setObjectName("ghost")
        x.setIcon(icons.icon("close", C["muted"]))
        x.setToolTip("Video entfernen")
        x.clicked.connect(lambda: (b.setText(label), self.set(target, key, ""), self.show_again()))
        row.addWidget(b, 1)
        row.addWidget(x)
        return row

    def fit(self, target, key, default):
        c = QComboBox()
        c.addItem("Randlos füllen", "cover")
        c.addItem("Ganz zeigen", "contain")
        c.setCurrentIndex(max(0, c.findData(target.get(key, default))))
        c.currentIndexChanged.connect(lambda _i: self.set(target, key, c.currentData()))
        return c

    def check(self, target, key, text, default=False, on=None, off=None):
        box = QCheckBox(text)
        value = target.get(key, default)
        box.setChecked(value == on if on is not None else bool(value))
        box.toggled.connect(lambda v: self.set(target, key, (on if v else off) if on is not None else v))
        return box

    def show_again(self):
        sel = self.screen.selection
        self.show_element(sel)

    def media_rows(self, form, s):
        """Hintergrundbild/-video (Vollbild) für alle Bildschirm-Schritte."""
        form.addRow("Bild", self.image(s, "bgImage"))
        form.addRow("Video", self.video(s, "bgVideo", "bgRatio"))
        if s.get("bgImage") or s.get("bgVideo"):
            form.addRow("Füllen", self.fit(s, "bgFit", "cover"))
        if s.get("bgVideo"):
            form.addRow("", self.check(s, "videoLoop", "Video wiederholen"))
            form.addRow("", self.check(s, "videoVolume", "Ton aus", 0.0, on=-80.0, off=0.0))
            if s["type"] in ("splash", "seite"):
                length = s.get("videoLength", 0)
                text = "Weiter, wenn das Video endet" + (f" ({length:g} s)".replace(".", ",") if length else "")
                form.addRow("", self.check(s, "untilVideoEnd", text))

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
        if kind in ("menu", "seite") and element is not None:
            self.show_menu_element(element)
            return
        self.pv.addWidget(self.heading({"splash": "Splash", "text": "Zwischentext", "menu": "Menü", "seite": "Seite"}[kind]))
        form = QFormLayout()
        form.addRow("Name", self.line(s, "name"))
        form.addRow("Hintergrund", self.color(s, "bg", "#000000"))
        self.media_rows(form, s)
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
        elif kind == "seite":
            d = self.number(s, "duration", 4.0, 0, 120, 0.5)
            d.setSpecialValueText("bis Tastendruck")
            d.setSuffix(" s")
            d.setToolTip("So lange bleibt die Seite stehen, dann kommt der nächste Schritt (Bild oder Spiel).\n"
                         "0 = bis Leertaste oder Klick. Mit Taste/Klick kann man immer weiterblättern.")
            form.addRow("Anzeigen", d)
        self.pv.addLayout(form)
        if kind == "seite":
            self.pv.addSpacing(6)
            self.pv.addWidget(QLabel("HINZUFÜGEN", objectName="section"))
            row = QGridLayout()
            row.setSpacing(6)
            for i, (label, icon, el) in enumerate((
                    ("Sprechblase", "bubble", {"kind": "bubble", "text": "Hallo!", "speaker": "", "x": 0.5, "y": 0.4,
                                               "w": 0.3, "h": 0.18, "size": 32, "color": "#ffffff",
                                               "textColor": "#1c2433", "tail": "unten-links", "after": 0.0}),
                    ("Text", "text", {"kind": "text", "text": "Kapitel 1", "x": 0.5, "y": 0.15, "w": 0.6,
                                      "h": 0.12, "size": 52, "color": "#ffffff", "bold": True, "after": 0.0}),
                    ("Bild", "image", {"kind": "image", "image": "", "x": 0.5, "y": 0.55, "w": 0.4, "h": 0.5,
                                       "after": 0.0}),
                    ("Video", "play", {"kind": "video", "video": "", "x": 0.5, "y": 0.5, "w": 0.5, "h": 0.5,
                                       "fit": "contain", "after": 0.0}))):
                b = QPushButton(label)
                b.setIcon(icons.icon(icon, C["text"], C["accent"]))
                b.clicked.connect(lambda _=False, el=el: self.add_element(dict(el)))
                row.addWidget(b, i // 2, i % 2)
            self.pv.addLayout(row)
            tip = QLabel("Blasen, Texte und Bilder in der Vorschau verschieben, am Punkt unten rechts die Größe ändern. "
                         "Mit „Erscheint nach“ tauchen sie nacheinander auf – wie in einem Comic.")
            tip.setWordWrap(True)
            tip.setObjectName("sub")
            self.pv.addWidget(tip)
        if kind == "menu":
            self.pv.addSpacing(6)
            self.pv.addWidget(QLabel("HINZUFÜGEN", objectName="section"))
            row = QGridLayout()
            row.setSpacing(6)
            for i, (label, icon, el) in enumerate((
                    ("Knopf", "menu", {"kind": "button", "text": "Knopf", "action": "start", "x": 0.5, "y": 0.8,
                                       "w": 0.24, "h": 0.09, "size": 30, "color": C["accent"],
                                       "textColor": "#12151b", "radius": 16}),
                    ("Text", "text", {"kind": "text", "text": "Überschrift", "x": 0.5, "y": 0.2, "w": 0.6,
                                      "h": 0.12, "size": 56, "color": "#ffffff", "bold": True}),
                    ("Bild", "image", {"kind": "image", "image": "", "x": 0.5, "y": 0.4, "w": 0.3, "h": 0.3}),
                    ("Video", "play", {"kind": "video", "video": "", "x": 0.5, "y": 0.5, "w": 1.0, "h": 1.0,
                                       "fit": "cover", "loop": True}))):
                b = QPushButton(label)
                b.setIcon(icons.icon(icon, C["text"], C["accent"]))
                b.clicked.connect(lambda _=False, el=el: self.add_element(dict(el)))
                row.addWidget(b, i // 2, i % 2)
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
        self.pv.addWidget(self.heading({"button": "Knopf", "image": "Bild", "video": "Video", "bubble": "Sprechblase"}.get(kind, "Text")))
        form = QFormLayout()
        if kind == "bubble":
            t = QPlainTextEdit(e.get("text", ""))
            t.setFixedHeight(80)
            t.textChanged.connect(lambda: self.set(e, "text", t.toPlainText()))
            form.addRow("Text", t)
            speaker = self.line(e, "speaker")
            speaker.setPlaceholderText("optional, z. B. Lotte")
            form.addRow("Wer spricht", speaker)
            form.addRow("Schriftgröße", self.number(e, "size", 32, 8, 200, decimals=0))
            form.addRow("Blasenfarbe", self.color(e, "color", "#ffffff"))
            form.addRow("Textfarbe", self.color(e, "textColor", "#1c2433"))
            tail = QComboBox()
            for key, name in TAILS:
                tail.addItem(name, key)
            tail.setCurrentIndex(max(0, tail.findData(e.get("tail", "unten-links"))))
            tail.currentIndexChanged.connect(lambda _i: self.set(e, "tail", tail.currentData()))
            form.addRow("Spitze", tail)
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
        elif kind == "image":
            form.addRow("Bild", self.image(e, "image"))
        elif kind == "video":
            form.addRow("Video", self.video(e, "video", "ratio"))
            form.addRow("", self.check(e, "loop", "Wiederholen"))
            form.addRow("", self.check(e, "volume", "Ton aus", 0.0, on=-80.0, off=0.0))
        if kind in ("image", "video"):
            form.addRow("Füllen", self.fit(e, "fit", "contain"))
            full = QPushButton("Vollbild")
            full.setIcon(icons.icon("focus", C["text"]))
            full.setToolTip("Füllt den ganzen Bildschirm")

            def fullscreen():
                e.update({"x": 0.5, "y": 0.5, "w": 1.0, "h": 1.0, "fit": "cover"})
                self.screen.update()
                self.changed.emit()
                self.show_element(e)
            full.clicked.connect(fullscreen)
            form.addRow("", full)
        if self.step["type"] == "seite":
            after = self.number(e, "after", 0.0, 0, 60, 0.5)
            after.setSpecialValueText("sofort")
            after.setSuffix(" s")
            form.addRow("Erscheint nach", after)
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
