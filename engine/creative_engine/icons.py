"""Symbole für die Creative Engine (wie Creative Writer): schlichte Strich-Icons (24×24), passend zur Graphit-Optik.

icon(name, color) → QIcon. Die Formen sind bewusst einfach gehalten und werden in der
Textfarbe des Designs gezeichnet (hell auf Graphit, dunkel auf Porzellan).
"""

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# Jeder Eintrag: SVG-Inhalt im 24er-Raster. „{c}“ = Strichfarbe, „{a}“ = Akzentfarbe.
SHAPES = {
    # Datei
    "new": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/><path d="M12 11v6M9 14h6"/>',
    "open": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v1"/><path d="M3 7v11a2 2 0 0 0 2 2h12.5a2 2 0 0 0 1.9-1.4L22 12H7.5a2 2 0 0 0-1.9 1.4L3 20"/>',
    "save": '<path d="M5 3h11l3 3v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M7 3v5h8V3"/><rect x="7" y="13" width="10" height="8" rx="1"/>',
    "saveas": '<path d="M5 3h11l3 3v5"/><path d="M3 5v14a2 2 0 0 0 2 2h6"/><path d="M7 3v5h8"/><path d="M14 21l1-3 5.5-5.5a1.4 1.4 0 0 1 2 2L17 20z"/>',
    "pdf": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/><text x="12" y="17" font-size="6.2" font-family="sans-serif" font-weight="700" text-anchor="middle" fill="{c}" stroke="none">PDF</text>',
    "word": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/><path d="M8.5 11l1.3 6 2.2-5 2.2 5 1.3-6"/>',
    "export": '<path d="M12 3v12"/><path d="M7 8l5-5 5 5"/><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5"/>',
    "print": '<path d="M6 9V3h12v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M6 14h12v7H6z"/>',
    "preview": '<path d="M6 3h8l4 4v6"/><path d="M6 3v18h6"/><circle cx="16.5" cy="16.5" r="3"/><path d="M18.7 18.7L21 21"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "recent": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
    # Bearbeiten
    "undo": '<path d="M9 14L4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
    "redo": '<path d="M15 14l5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/>',
    "paste": '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M8 11h8M8 15h6"/>',
    "cut": '<circle cx="6" cy="18" r="3"/><circle cx="18" cy="18" r="3"/><path d="M8.1 15.9L19 3M15.9 15.9L5 3"/>',
    "copy": '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M4 16a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2"/>',
    "brush": '<path d="M18 3l3 3-9 9-3-3z"/><path d="M9 12l-2.5.5A3 3 0 0 0 4 15.5c0 1.5-1 3-2 3.5 3 1 7 0 8-3l.5-2"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    "replace": '<path d="M4 7h11l-3-3M15 7l-3 3"/><path d="M20 17H9l3 3M9 17l3-3"/>',
    "select": '<path d="M5 3l14 8-6 2-2 6z"/>',
    "eraser": '<path d="M7 21h13"/><path d="M5.5 15.5l9-9a2 2 0 0 1 2.8 0l2.2 2.2a2 2 0 0 1 0 2.8L12 19H8.5z"/><path d="M9 12l5 5"/>',
    # Absatz
    "bullets": '<circle cx="5" cy="6" r="1.2" fill="{c}"/><circle cx="5" cy="12" r="1.2" fill="{c}"/><circle cx="5" cy="18" r="1.2" fill="{c}"/><path d="M9 6h11M9 12h11M9 18h11"/>',
    "numbers": '<path d="M4 4h1.5v4"/><path d="M3.5 8h3"/><path d="M3.5 13.5a1.5 1.5 0 0 1 3 .3c0 1-3 1.7-3 3.2h3"/><path d="M10 6h10M10 12h10M10 18h10"/>',
    "outdent": '<path d="M21 5H11M21 10H11M21 15H11M21 20H3"/><path d="M7 8l-4 4 4 4"/>',
    "indent": '<path d="M21 5H11M21 10H11M21 15H11M21 20H3"/><path d="M3 8l4 4-4 4"/>',
    "alignleft": '<path d="M3 5h18M3 10h12M3 15h18M3 20h12"/>',
    "aligncenter": '<path d="M3 5h18M6 10h12M3 15h18M6 20h12"/>',
    "alignright": '<path d="M3 5h18M9 10h12M3 15h18M9 20h12"/>',
    "justify": '<path d="M3 5h18M3 10h18M3 15h18M3 20h18"/>',
    "spacing": '<path d="M11 5h10M11 12h10M11 19h10"/><path d="M5 4v16"/><path d="M2.5 6.5L5 4l2.5 2.5M2.5 17.5L5 20l2.5-2.5"/>',
    "shading": '<path d="M11 4l7 7-6 6-7-7z"/><path d="M5 10l13 1"/><path d="M20 15s2 2.2 2 3.5a2 2 0 0 1-4 0c0-1.3 2-3.5 2-3.5z"/><rect x="2" y="21" width="20" height="2" fill="{a}" stroke="none"/>',
    "pilcrow": '<path d="M13 4v16M17 4v16"/><path d="M19 4H9.5a4.5 4.5 0 0 0 0 9H13"/>',
    # Einfügen
    "page": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/>',
    "pagebreak": '<path d="M6 3v6h12V3"/><path d="M6 21v-6h12v6"/><path d="M3 12h2M8 12h2M14 12h2M19 12h2"/>',
    "table": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M3 15h18M9 4v16M15 4v16"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 17l-5-5L5 20"/>',
    "link": '<path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>',
    "header": '<path d="M5 3h14v18H5z"/><path d="M5 8h14"/><rect x="7.5" y="4.6" width="9" height="2" fill="{a}" stroke="none"/><path d="M8 12h8M8 15h6"/>',
    "footer": '<path d="M5 3h14v18H5z"/><path d="M5 16h14"/><rect x="7.5" y="17.6" width="9" height="2" fill="{a}" stroke="none"/><path d="M8 7h8M8 10h6"/>',
    "pagenum": '<path d="M5 3h14v18H5z"/><text x="12" y="18.6" font-size="6" font-family="sans-serif" font-weight="700" text-anchor="middle" fill="{a}" stroke="none">#</text><path d="M8 7h8M8 10h8"/>',
    "date": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/><path d="M8 14h2M14 14h2M8 17h2"/>',
    "rule": '<path d="M3 12h18"/><path d="M6 7h12M6 17h12" stroke-opacity=".4"/>',
    "symbol": '<text x="12" y="18" font-size="16" font-family="serif" text-anchor="middle" fill="{c}" stroke="none">Ω</text>',
    "toc": '<path d="M4 5h10M4 10h14M7 15h11M7 20h11"/><path d="M18 5h2" stroke-dasharray="1 1.5"/>',
    "comment": '<path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    # Layout
    "margins": '<rect x="4" y="3" width="16" height="18" rx="1"/><rect x="7.5" y="6.5" width="9" height="11" stroke-dasharray="1.6 1.6"/>',
    "orientation": '<rect x="3" y="6" width="12" height="15" rx="1"/><rect x="9" y="3" width="12" height="9" rx="1" stroke="{a}"/>',
    "size": '<rect x="5" y="3" width="14" height="18" rx="1"/><path d="M8 7h8M8 7l2-1.5M8 7l2 1.5M16 7l-2-1.5M16 7l-2 1.5"/>',
    "columns": '<rect x="3" y="3" width="18" height="18" rx="1"/><path d="M12 3v18"/><path d="M6 7h3M6 10h3M6 13h3M15 7h3M15 10h3M15 13h3"/>',
    "pagecolor": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/><rect x="8" y="11" width="8" height="7" fill="{a}" stroke="none"/>',
    "watermark": '<path d="M6 3h8l4 4v14H6z"/><path d="M8.5 17.5l7-7" stroke="{a}"/>',
    # Überprüfen
    "spell": '<path d="M4 15l3.5-9 3.5 9M5.3 12h4.4"/><path d="M13 16l3 3 5-7"/>',
    "count": '<path d="M4 9h16M4 15h16M10 3l-2 18M16 3l-2 18"/>',
    "read": '<path d="M11 5L6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>',
    # Ansicht
    "printlayout": '<rect x="5" y="2" width="14" height="20" rx="1"/><path d="M8 6h8M8 9h8M8 12h8M8 15h5"/>',
    "weblayout": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    "focus": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
    "navpane": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/><path d="M5 8h2M5 11h2M5 14h2"/>',
    "zoom": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4M11 8v6M8 11h6"/>',
    "zoom100": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/><text x="11" y="13.4" font-size="6.4" font-family="sans-serif" font-weight="700" text-anchor="middle" fill="{c}" stroke="none">1:1</text>',
    "pagewidth": '<rect x="3" y="5" width="18" height="14" rx="1"/><path d="M6 12h12M6 12l2.5-2.5M6 12l2.5 2.5M18 12l-2.5-2.5M18 12l-2.5 2.5"/>',
    "ruler": '<rect x="2" y="8" width="20" height="8" rx="1"/><path d="M6 8v3M10 8v4M14 8v3M18 8v4"/>',
    "theme": '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 0 0 18z" fill="{c}"/>',
    "chevron": '<path d="M6 9l6 6 6-6"/>',
    "check": '<path d="M5 12l5 5L20 7"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "back": '<path d="M15 6l-6 6 6 6"/>',
    "up": '<path d="M6 15l6-6 6 6"/>',
    "bubble": '<path d="M4 5h16a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H10l-4 4v-4H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z"/><path d="M8 9.5h8M8 12.5h5" stroke="{a}"/>',
    # Creative Engine
    "play": '<path d="M7 4.5v15l12-7.5z" fill="{a}"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="2" fill="{a}"/>',
    "brick": '<rect x="3" y="5" width="18" height="14" rx="1.5"/><path d="M3 12h18M9 5v7M15 12v7"/>',
    "pencil": '<path d="M4 20l1-4L16 5a2 2 0 0 1 3 3L8 19z"/><path d="M14 7l3 3"/>',
    "rect": '<rect x="4" y="5" width="16" height="14" rx="1.5" stroke-dasharray="2.2 2"/><rect x="7" y="8" width="10" height="8" fill="{a}" stroke="none" opacity=".6"/>',
    "cursor": '<path d="M5 3l14 8-6 2-2 6z"/>',
    "gamepad": '<path d="M7 8h10a5 5 0 0 1 4.8 6.4l-.9 3a2.5 2.5 0 0 1-4.3.9L14.5 16h-5l-2.1 2.3a2.5 2.5 0 0 1-4.3-.9l-.9-3A5 5 0 0 1 7 8z"/><path d="M8 11v3M6.5 12.5h3"/><circle cx="15.5" cy="11.5" r=".6" fill="{c}"/><circle cx="17.5" cy="13.5" r=".6" fill="{c}"/>',
    "splash": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 8l1.3 3.2L16.5 12l-3.2 1.2L12 16.5l-1.3-3.3L7.5 12l3.2-.8z" fill="{a}" stroke="none"/>',
    "menu": '<rect x="3" y="4" width="18" height="16" rx="2"/><rect x="8" y="8.5" width="8" height="2.6" rx="1.3" fill="{a}" stroke="none"/><rect x="8" y="13" width="8" height="2.6" rx="1.3"/>',
    "level": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 16h6v-3h5v3h7"/><circle cx="16.5" cy="9" r="1.3" fill="{a}" stroke="none"/>',
    "text": '<path d="M5 6V4h14v2M12 4v16M9 20h6"/>',
    "model": '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/><path d="M10 11v6M14 11v6"/>',
    "duplicate": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "download": '<path d="M12 3v12M7 10l5 5 5-5"/><path d="M5 19h14"/>',
    "character": '<circle cx="12" cy="5" r="2.2"/><path d="M12 7.5v7M7 10l5-1 5 1M9 21l3-6.5 3 6.5"/>',
    "bone": '<circle cx="12" cy="5" r="1.6" fill="{a}"/><circle cx="12" cy="12" r="1.6" fill="{a}"/><circle cx="7" cy="10" r="1.4" fill="{a}"/><circle cx="17" cy="10" r="1.4" fill="{a}"/><circle cx="9" cy="20" r="1.4" fill="{a}"/><circle cx="15" cy="20" r="1.4" fill="{a}"/><path d="M12 6.6v3.8M8.4 10.3l2.2.9M15.6 10.3l-2.2.9M11.3 13.4l-1.8 5.2M12.7 13.4l1.8 5.2"/>',
    "walk": '<circle cx="13" cy="4" r="2"/><path d="M12 7l-2 6 3 3v5M10 13l-3 7M12 8l4 3 3-1M11.5 9L8 11v3"/>',
    "car": '<path d="M4 15l1.5-5A2 2 0 0 1 7.4 8.6h9.2a2 2 0 0 1 1.9 1.4L20 15"/><rect x="3" y="14" width="18" height="4" rx="1.5"/><circle cx="7.5" cy="18.5" r="1.6"/><circle cx="16.5" cy="18.5" r="1.6"/>',
    "build": '<path d="M14 6a4 4 0 0 0 4 5l2.5-2.5-2-.5-.5-2L20.5 3.5A4 4 0 0 0 14 6z"/><path d="M14.5 9.5L4 20"/>',
    "ai": '<path d="M12 3l1.8 4.6L18 9l-4.2 1.4L12 15l-1.8-4.6L6 9l4.2-1.4z"/><path d="M19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/>',
}

_cache = {}


def svg(name, color, accent=None):
    body = SHAPES.get(name, SHAPES["page"]).replace("{c}", color).replace("{a}", accent or color)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%s" '
            'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">%s</svg>' % (color, body))


def pixmap(name, color, size=20, accent=None, ratio=2.0):
    key = (name, color, size, accent, ratio)
    if key in _cache:
        return _cache[key]
    renderer = QSvgRenderer(QByteArray(svg(name, color, accent).encode("utf-8")))
    pm = QPixmap(int(size * ratio), int(size * ratio))
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, pm.width(), pm.height()))
    painter.end()
    pm.setDevicePixelRatio(ratio)
    _cache[key] = pm
    return pm


def icon(name, color, accent=None, disabled=None):
    ic = QIcon()
    for size in (16, 20, 24, 32):
        ic.addPixmap(pixmap(name, color, size, accent), QIcon.Mode.Normal)
        if disabled:
            ic.addPixmap(pixmap(name, disabled, size, None), QIcon.Mode.Disabled)
    return ic


def color_bar_icon(name, color, bar, size=20):
    """Symbol mit Farbbalken darunter (Schriftfarbe, Hervorhebung) – Farbe ändert sich mit der Auswahl."""
    base = pixmap(name, color, size)
    pm = QPixmap(base.size())
    pm.setDevicePixelRatio(base.devicePixelRatio())
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.drawPixmap(0, 0, base)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(bar))
    p.drawRoundedRect(QRectF(size * 0.12, size * 0.82, size * 0.76, size * 0.16), 1.5, 1.5)
    p.end()
    return QIcon(pm)


# Zusätzliche Formen für Schriftfarbe und Hervorhebung (mit Balken via color_bar_icon)
SHAPES["fontcolor"] = '<path d="M6 16L11 3h2l5 13M8 11.5h8"/>'
SHAPES["highlight"] = '<path d="M9 11l-4 4v2h4l4-4"/><path d="M13 13l6-6-4-4-6 6z"/>'
