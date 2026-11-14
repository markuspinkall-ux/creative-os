"""Zeichnet eine Taste (Symbol + Beschriftung) im Graphit-Look als Bild."""

import os
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPainterPath, QPen

from . import apps

BACKGROUND = "#232836"
TEXT = "#dce6ff"
ACCENT = "#8fb3ff"


def creative_qml_dir():
    for p in (Path(__file__).resolve().parent.parent.parent / "shell" / "creative_shell" / "qml",
              Path("/usr/lib/creative-shell/creative_shell/qml")):
        if (p / "Creative" / "qmldir").exists():
            return p
    return None


def glyph_path(name):
    base = creative_qml_dir()
    if not base or not name:
        return ""
    p = base / "Creative" / "icons" / f"{name}.svg"
    return str(p) if p.exists() else ""


def glyph_names():
    base = creative_qml_dir()
    if not base:
        return []
    return sorted(p.stem for p in (base / "Creative" / "icons").glob("*.svg") if not p.stem.endswith("-dark"))


def _theme_pixmap(name, edge):
    try:
        from creative_shell import icons
        return icons.render_icon(name, edge)
    except Exception:  # noqa: BLE001 – ohne Creative Shell: normales Icon-Theme
        icon = QIcon.fromTheme(name)
        return icon.pixmap(edge, edge) if not icon.isNull() else None


def symbol_image(symbol, edge):
    """Symbol einer Taste als QImage (oder None)."""
    if not symbol:
        return None
    kind, _, value = symbol.partition(":")
    if kind == "glyph":
        path = glyph_path(value)
        return QIcon(path).pixmap(edge, edge).toImage() if path else None
    if kind == "app":
        pm = _theme_pixmap(apps.icon_of(value), edge)
        return pm.toImage() if pm is not None and not pm.isNull() else None
    if kind == "icon":
        pm = _theme_pixmap(value, edge)
        return pm.toImage() if pm is not None and not pm.isNull() else None
    if symbol.startswith("/") and os.path.exists(symbol):
        img = QImage(symbol)
        if not img.isNull():
            return img.scaled(edge, edge, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return None


def render_key(key, size, pressed=False, folder=False):
    """Taste als quadratisches QImage in Gerätegröße (z. B. 72×72 beim Stream Deck MK.2)."""
    key = key or {}
    img = QImage(size, size, QImage.Format_RGB888)
    img.fill(QColor("#12151b"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    inset = 2 if pressed else 0
    rect = QRectF(inset, inset, size - 2 * inset, size - 2 * inset)
    path = QPainterPath()
    path.addRoundedRect(rect, size * 0.16, size * 0.16)
    bg = QColor(key.get("farbe") or BACKGROUND)
    if pressed:
        bg = bg.lighter(135)
    p.fillPath(path, bg)

    text = (key.get("text") or "").strip()
    symbol = key.get("symbol") or ""
    if not text and not symbol:
        p.end()
        return img
    edge = int(size * (0.46 if text else 0.62))
    sym = symbol_image(symbol, edge)
    if sym is not None:
        x = (size - sym.width()) / 2
        y = size * (0.12 if text else 0.19) + (edge - sym.height()) / 2
        p.drawImage(int(x), int(y), sym)
    if text:
        font = QFont("Arial")
        font.setBold(True)
        font.setPixelSize(max(9, int(size * (0.15 if sym is not None else 0.2))))
        p.setFont(font)
        p.setPen(QColor(TEXT))
        area = QRectF(size * 0.06, size * (0.6 if sym is not None else 0.08), size * 0.88,
                      size * (0.36 if sym is not None else 0.84))
        align = Qt.AlignHCenter | (Qt.AlignTop if sym is not None else Qt.AlignVCenter) | Qt.TextWordWrap
        p.drawText(area, int(align), text)
    if folder:
        # kleiner Winkel unten rechts: diese Taste öffnet eine Seite
        pen = QPen(QColor(ACCENT))
        pen.setWidthF(max(1.5, size * 0.03))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        s = size * 0.07
        cx, cy = size * 0.86, size * 0.86
        p.drawLine(int(cx - s), int(cy), int(cx), int(cy))
        p.drawLine(int(cx), int(cy - s), int(cx), int(cy))
    p.end()
    return img


def to_png(image):
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "PNG")
    buf.close()
    return bytes(data)
