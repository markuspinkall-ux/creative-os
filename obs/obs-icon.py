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
tile.addRoundedRect(QRectF(16, 16, SIZE - 32, SIZE - 32), 64, 64)     # wie 4..60 von 64
light = len(sys.argv) > 2 and sys.argv[2] == "--hell"     # Porzellan: helle Kachel
p.fillPath(tile, QColor("#ffffff" if light else "#232836"))
# Rand wie bei allen Creative-Symbolen (64er-Kachel: 2 px Akzent → hier 8 px)
p.setPen(QPen(QColor("#3d6fe0" if light else "#8fb3ff"), 8))
p.drawPath(tile)
inner = QRectF(SIZE * 0.21, SIZE * 0.21, SIZE * 0.58, SIZE * 0.58)
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

# Auch die Original-Symboldateien von OBS ersetzen – so zeigen Startmenü, Ablage,
# Taskleiste und Titelleiste überall die angepasste Kachel, egal wie nachgeschlagen wird.
for f in glob.glob("/usr/share/icons/hicolor/*/apps/com.obsproject.Studio*"):
    size_dir = f.split("/")[5]
    if f.endswith(".svg"):
        os.remove(f)
        img.save(f[:-4] + ".png")
        print("ersetzt:", f)
    elif f.endswith(".png"):
        n = int(size_dir.split("x")[0]) if size_dir[0].isdigit() else SIZE
        img.scaled(n, n, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation).save(f)
        print("ersetzt:", f)
