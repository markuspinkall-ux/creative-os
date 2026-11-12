"""Klappliste (QComboBox) in einem #panel mit dem Stylesheet einer App fotografieren.
   QT_QPA_PLATFORM=offscreen python3 tools/combo-vorschau.py <app-datei> <ausgabe.png>"""
import re
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QComboBox, QFrame, QLabel, QVBoxLayout

src = open(sys.argv[1], encoding="utf-8").read()
style = re.search(r'^STYLE = """(.*?)"""', src, re.S | re.M).group(1)
app = QApplication([])
app.setStyle("Fusion")
app.setStyleSheet(style)
panel = QFrame(objectName="panel")
panel.resize(360, 220)
v = QVBoxLayout(panel)
v.addWidget(QLabel("Qualität"))
combo = QComboBox()
combo.addItems(["Normal (≈ 1–2 Min.)", "Hoch – schärfere Textur (≈ 3–5 Min.)"])
v.addWidget(combo)
other = QComboBox()
other.addItems(["Kein Skelett (Objekt)"])
v.addWidget(other)
v.addStretch(1)
panel.show()


def shoot():
    combo.showPopup()
    QTimer.singleShot(300, grab)


def grab():
    popup = combo.view().window()
    base = panel.grab()
    pm = QPixmap(base.size())
    pm.fill(QColor("#12151b"))
    p = QPainter(pm)
    p.drawPixmap(0, 0, base)
    pos = panel.mapFromGlobal(popup.mapToGlobal(popup.rect().topLeft()))
    p.drawPixmap(pos, popup.grab())
    p.end()
    pm.save(sys.argv[2])
    app.quit()


QTimer.singleShot(300, shoot)
app.exec()
