"""Creative 3D – Gelenk-Editor: Ankerpunkte für das Skelett setzen.

Zwei Ansichten der Figur (von vorn und von der Seite) als Silhouette.
Gelenke sind Punkte, die man mit der Maus verschiebt: vorn ändert links/rechts
und oben/unten, die Seitenansicht vorn/hinten und oben/unten.
Blau = linke Körperseite, Orange = rechte, Weiß = Mitte.
"""

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

import creative3d_rig as R

GROUND = QColor("#12151b")
SIL = QColor(220, 230, 255, 60)
LEFT = QColor("#8fb3ff")
RIGHT = QColor("#ffb07a")
MID = QColor("#dce6ff")
BONE = QColor(220, 230, 255, 150)
HIT = 13


def joint_color(name):
    return LEFT if name.startswith("Left") else RIGHT if name.startswith("Right") else MID


class JointView(QWidget):
    """Eine Ansicht. axis 0 = vorn (x waagerecht), 2 = Seite (z waagerecht, vorn rechts)."""
    changed = Signal()
    hovered = Signal(str)

    def __init__(self, editor, axis, title):
        super().__init__()
        self.editor, self.axis, self.title = editor, axis, title
        self.drag = None
        self.cache = None
        self.setMinimumSize(320, 420)
        self.setMouseTracking(True)
        self.setAccessibleName(title)

    # Abbildung Welt → Bild (gleicher Maßstab für beide Ansichten)
    def frame(self):
        lo, hi = self.editor.lo, self.editor.hi
        size = max(hi[1] - lo[1], hi[0] - lo[0], hi[2] - lo[2]) * 1.12
        scale = min(self.width(), self.height() - 30) / size
        cx = (lo[self.axis] + hi[self.axis]) / 2
        cy = (lo[1] + hi[1]) / 2
        return scale, cx, cy

    def to_screen(self, p):
        scale, cx, cy = self.frame()
        return QPointF(self.width() / 2 + (p[self.axis] - cx) * scale,
                       30 + (self.height() - 30) / 2 - (p[1] - cy) * scale)

    def to_world(self, pt):
        scale, cx, cy = self.frame()
        return (cx + (pt.x() - self.width() / 2) / scale,
                cy - (pt.y() - 30 - (self.height() - 30) / 2) / scale)

    def silhouette(self):
        key = (self.width(), self.height())
        if self.cache and self.cache[0] == key:
            return self.cache[1]
        img = QImage(self.width(), self.height(), QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(SIL)
        for v in self.editor.sample:
            s = self.to_screen(v)
            p.drawEllipse(s, 1.6, 1.6)
        p.end()
        self.cache = (key, img)
        return img

    def resizeEvent(self, _e):
        self.cache = None

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), GROUND)
        p.setPen(QColor(220, 230, 255, 150))
        p.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        p.drawText(QRectF(10, 6, self.width() - 20, 20), Qt.AlignmentFlag.AlignLeft, self.title)
        p.drawImage(0, 0, self.silhouette())
        joints = self.editor.joints
        for name in R.NAMES:                                   # Knochen
            parent = R.PARENT[name]
            if parent:
                p.setPen(QPen(BONE, 2.5))
                p.drawLine(self.to_screen(joints[parent]), self.to_screen(joints[name]))
        for name in R.NAMES:                                   # Gelenke
            s = self.to_screen(joints[name])
            active = name == self.editor.selected
            p.setPen(QPen(GROUND, 2))
            p.setBrush(joint_color(name))
            r = 8 if active else 6
            p.drawEllipse(s, r, r)
            if active:
                p.setPen(QPen(joint_color(name), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(s, 12, 12)
        p.end()

    def nearest(self, pt):
        best, dist = None, HIT
        for name in R.NAMES:
            s = self.to_screen(self.editor.joints[name])
            d = ((s.x() - pt.x()) ** 2 + (s.y() - pt.y()) ** 2) ** 0.5
            if d < dist:
                best, dist = name, d
        return best

    def mousePressEvent(self, e):
        name = self.nearest(e.position())
        self.editor.select(name)
        self.drag = name

    def mouseMoveEvent(self, e):
        if self.drag:
            h, y = self.to_world(e.position())
            self.editor.move(self.drag, self.axis, h, y)
            self.changed.emit()
        else:
            name = self.nearest(e.position())
            self.setCursor(Qt.CursorShape.OpenHandCursor if name else Qt.CursorShape.ArrowCursor)
            self.hovered.emit(R.LABEL[name] if name else "")

    def mouseReleaseEvent(self, _e):
        self.drag = None


class RigDialog(QDialog):
    """Gelenke anpassen. Ergebnis: self.joints (Name → np.array) nach accept()."""

    def __init__(self, parent, vertices, joints=None, probe=True):
        super().__init__(parent)
        self.setWindowTitle("Skelett – Gelenke anpassen")
        self.resize(900, 640)
        v = np.asarray(vertices, dtype=np.float64)
        self.vertices = v
        self.lo, self.hi = v.min(0), v.max(0)
        step = max(1, len(v) // 9000)
        self.sample = v[::step]
        self.joints = {k: np.array(p, dtype=np.float64) for k, p in (joints or R.fit_template(v)).items()}
        self.selected = None
        self.symmetric = True

        box = QVBoxLayout(self)
        box.setContentsMargins(16, 14, 16, 14)
        intro = QLabel("Zieh die Punkte dorthin, wo die Gelenke sitzen – vorn für links/rechts und Höhe, "
                       "in der Seitenansicht für vorn/hinten. Blau = linke Körperseite der Figur, Orange = rechte.")
        intro.setWordWrap(True)
        intro.setObjectName("muted")
        box.addWidget(intro)
        views = QHBoxLayout()
        self.front = JointView(self, 0, "VON VORN")
        self.side = JointView(self, 2, "VON DER SEITE  (vorn →)")
        for view in (self.front, self.side):
            view.changed.connect(self.update_views)
            view.hovered.connect(self.show_hover)
            views.addWidget(view, 1)
        box.addLayout(views, 1)
        self.hint = QLabel(" ")
        self.hint.setObjectName("muted")
        box.addWidget(self.hint)
        row = QHBoxLayout()
        self.sym = QCheckBox("Links und rechts gemeinsam (spiegeln)")
        self.sym.setChecked(True)
        self.sym.toggled.connect(lambda on: setattr(self, "symmetric", on))
        row.addWidget(self.sym)
        self.probe = QCheckBox("Probe-Bewegung in der Vorschau (Figur winkt)")
        self.probe.setChecked(probe)
        row.addWidget(self.probe)
        row.addStretch()
        refit = QPushButton("Vorlage neu einpassen")
        refit.clicked.connect(self.refit)
        row.addWidget(refit)
        cancel = QPushButton("Abbrechen")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        ok = QPushButton("Übernehmen", objectName="primary")
        ok.clicked.connect(self.accept)
        row.addWidget(ok)
        box.addLayout(row)

    def select(self, name):
        self.selected = name
        self.hint.setText(R.LABEL[name] if name else " ")
        self.update_views()

    def show_hover(self, text):
        if not self.selected:
            self.hint.setText(text or " ")

    def move(self, name, axis, h, y):
        p = self.joints[name]
        p[axis], p[1] = h, y
        mirror = R.mirror_name(name)
        if self.symmetric and mirror:
            cx = self.joints["Hips"][0]
            m = self.joints[mirror]
            m[0] = 2 * cx - p[0]
            m[1], m[2] = p[1], p[2]
        elif self.symmetric and not R.side(name) and axis == 0 and name != "Hips":
            p[0] = self.joints["Hips"][0]                   # Mittelachse bleibt mittig

    def refit(self):
        self.joints = {k: np.array(v) for k, v in R.fit_template(self.vertices).items()}
        self.select(None)

    def update_views(self):
        self.front.update()
        self.side.update()
