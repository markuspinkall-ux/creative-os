#!/usr/bin/python3
"""OBS-Symbol im Creative-Look: Original-Logo von OBS Studio (GPL v2+) auf einer
Graphit-Kachel wie die übrigen Creative-Symbole. Läuft beim Bauen des Abbilds."""

import glob
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgRenderer

SIZE = 256
cands = sorted(glob.glob("/usr/share/icons/hicolor/scalable/apps/com.obsproject.Studio*.svg"))
pngs = sorted(glob.glob("/usr/share/icons/hicolor/*/apps/com.obsproject.Studio.png"),
              key=lambda p: int(p.split("/")[5].split("x")[0]) if p.split("/")[5][0].isdigit() else 0)
app = QGuiApplication(sys.argv)
img = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32_Premultiplied)
img.fill(Qt.GlobalColor.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
tile = QPainterPath()
tile.addRoundedRect(QRectF(8, 8, SIZE - 16, SIZE - 16), 56, 56)
p.fillPath(tile, QColor("#232836"))
p.setPen(QPen(QColor(255, 255, 255, 30), 3))
p.drawPath(tile)
inner = QRectF(SIZE * 0.17, SIZE * 0.17, SIZE * 0.66, SIZE * 0.66)
if cands:
    QSvgRenderer(cands[0]).render(p, inner)
elif pngs:
    p.drawImage(inner, QImage(pngs[-1]))
else:
    print("OBS-Symbol: Original nicht gefunden")
    sys.exit(0)
p.end()
out = sys.argv[1] if len(sys.argv) > 1 else "/usr/share/icons/hicolor/256x256/apps/creative-obs.png"
os.makedirs(os.path.dirname(out), exist_ok=True)
img.save(out)
print("OBS-Symbol im Creative-Look:", out)
