"""Liefert App-Symbole aus dem Icon-Theme an QML (image://icon/<name>)."""

import os

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtQuick import QQuickImageProvider

FALLBACK = "application-x-executable"


class IconProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)

    def requestPixmap(self, icon_id, size, requested_size):
        edge = max(requested_size.width(), requested_size.height(), 0) or 64
        icon = None
        if icon_id.startswith("/") and os.path.exists(icon_id):
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
