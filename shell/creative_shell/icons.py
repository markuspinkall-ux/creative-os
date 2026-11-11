"""Liefert App-Symbole aus dem Icon-Theme an QML (image://icon/<name>)."""

import os

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtQuick import QQuickImageProvider

FALLBACK = "application-x-executable"
# Creative-Symbole haben immer Vorrang – auch wenn eine App (z. B. ein OBS-Update oder
# eine Flatpak-Version) ihr eigenes Symbol mitbringt oder ihr Symbol als Dateipfad angibt.
CREATIVE_DIRS = ("/usr/share/icons/Creative/apps/scalable",)
ALIASES = {
    "com.obsproject.studio": "com.obsproject.Studio",
    "obs": "com.obsproject.Studio",
    "obs-studio": "com.obsproject.Studio",
}


def creative_icon(icon_id):
    """Pfad des Creative-Symbols für einen Symbolnamen oder Symbolpfad – sonst None."""
    stem = os.path.splitext(os.path.basename(icon_id or ""))[0]
    for name in dict.fromkeys((stem, ALIASES.get(stem.lower(), stem))):
        for folder in CREATIVE_DIRS:
            for ext in (".svg", ".png"):
                path = os.path.join(folder, name + ext)
                if name and os.path.exists(path):
                    return path
    return None


class IconProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)

    def requestPixmap(self, icon_id, size, requested_size):
        edge = max(requested_size.width(), requested_size.height(), 0) or 64
        icon = None
        override = creative_icon(icon_id)
        if override:
            icon = QIcon(override)
        elif icon_id.startswith("/") and os.path.exists(icon_id):
            icon = QIcon(icon_id)
        elif icon_id:
            icon = QIcon.fromTheme(icon_id)
        if icon is None or icon.isNull():
            icon = QIcon.fromTheme(FALLBACK)
        pixmap = icon.pixmap(QSize(edge, edge)) if not icon.isNull() else QPixmap()
        if pixmap.isNull():
            pixmap = QPixmap(edge, edge)
            pixmap.fill()
        if size is not None:
            size.setWidth(pixmap.width())
            size.setHeight(pixmap.height())
        return pixmap
