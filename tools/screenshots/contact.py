#!/usr/bin/python3
"""Übersichtsbild aller Bildschirmfotos + Warnung bei leeren Fenstern.

  python3 contact.py /out
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QRect, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter  # noqa: E402

TILE_W, TILE_H, LABEL, COLS, PAD = 480, 320, 26, 3, 14


def blank(image):
    """Fast nur eine Farbe? → vermutlich leeres oder kaputtes Fenster."""
    small = image.scaled(64, 48).convertToFormat(QImage.Format.Format_RGB32)
    colors = {small.pixel(x, y) for x in range(small.width()) for y in range(small.height())}
    return len(colors) < 6


def main(folder):
    app = QGuiApplication(sys.argv[:1])
    shots = sorted(p for p in Path(folder).glob("*.png") if p.name != "uebersicht.png")
    if not shots:
        print("::warning::Keine Bildschirmfotos entstanden.")
        return 0
    rows = (len(shots) + COLS - 1) // COLS
    sheet = QImage(COLS * (TILE_W + PAD) + PAD, rows * (TILE_H + LABEL + PAD) + PAD, QImage.Format.Format_RGB32)
    sheet.fill(QColor("#0b0d12"))
    painter = QPainter(sheet)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    font = QFont("Arial")
    font.setPixelSize(14)
    painter.setFont(font)
    for i, path in enumerate(shots):
        image = QImage(str(path))
        x = PAD + (i % COLS) * (TILE_W + PAD)
        y = PAD + (i // COLS) * (TILE_H + LABEL + PAD)
        name = path.stem
        if image.isNull():
            print(f"::warning::{name}: Bild unlesbar")
            continue
        if blank(image):
            print(f"::warning::{name}: Fenster wirkt leer (fast nur eine Farbe)")
            name += "  ⚠ leer?"
        scaled = image.scaled(TILE_W, TILE_H, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        painter.fillRect(QRect(x, y, TILE_W, TILE_H), QColor("#12151b"))
        painter.drawImage(x + (TILE_W - scaled.width()) // 2, y + (TILE_H - scaled.height()) // 2, scaled)
        painter.setPen(QColor("#dce6ff"))
        painter.drawText(QRect(x, y + TILE_H + 4, TILE_W, LABEL), Qt.AlignmentFlag.AlignLeft, name)
    painter.end()
    out = Path(folder) / "uebersicht.png"
    sheet.save(str(out))
    print(f"Übersicht: {out} ({len(shots)} Fenster)")
    del app
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
