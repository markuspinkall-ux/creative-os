"""Liefert App-Symbole aus dem Icon-Theme an QML (image://icon/<name>)."""

import hashlib
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QSize, QUrl, Slot
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtQuick import QQuickImageProvider

FALLBACK = "application-x-executable"
# Creative-Symbole haben immer Vorrang – auch wenn eine App (z. B. ein OBS-Update oder
# eine Flatpak-Version) ihr eigenes Symbol mitbringt oder ihr Symbol als Dateipfad angibt.
CREATIVE_DIRS = ("/usr/share/icons/Creative/apps/scalable",)
PORZELLAN_DIRS = ("/usr/share/icons/CreativePorzellan/apps/scalable",) + CREATIVE_DIRS


def _light():
    try:
        from creative_shell import look
        return look.is_light() and os.path.isdir(PORZELLAN_DIRS[0])
    except Exception:  # noqa: BLE001
        return False
ALIASES = {
    "com.obsproject.studio": "com.obsproject.Studio",
    "obs": "com.obsproject.Studio",
    "obs-studio": "com.obsproject.Studio",
}


def creative_icon(icon_id):
    """Pfad des Creative-Symbols für einen Symbolnamen oder Symbolpfad – sonst None."""
    stem = os.path.splitext(os.path.basename(icon_id or ""))[0]
    for name in dict.fromkeys((stem, ALIASES.get(stem.lower(), stem))):
        for folder in (PORZELLAN_DIRS if _LIGHT else CREATIVE_DIRS):
            for ext in (".svg", ".png"):
                path = os.path.join(folder, name + ext)
                if name and os.path.exists(path):
                    return path
    return None


_LIGHT = False


class IconProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)
        # Die Shell startet beim Wechsel des Designs neu – hier einmal festlegen
        global _LIGHT
        _LIGHT = _light()
        QIcon.setThemeName("CreativePorzellan" if _LIGHT else "Creative")

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


def render_icon(icon_id, edge):
    """Symbol als QPixmap (gleiche Suche wie der Bildlieferant)."""
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
    return pixmap


class IconFiles(QObject):
    """Symbole als PNG-Dateien statt über einen Python-Bildlieferanten.

    Ein in Python geschriebener QQuickImageProvider kann die Oberfläche beim Start
    verklemmen: Qts Bild-Thread fragt den Lieferanten (braucht die Python-Sperre),
    während der Haupt-Thread mit der Python-Sperre auf den Bild-Thread wartet –
    schwarzer Bildschirm. Darum: Symbol einmal im Haupt-Thread als Datei ablegen,
    QML lädt nur noch eine normale Datei (QML: iconFiles.url(name)).
    """

    EDGE = 128

    def __init__(self, parent=None):
        super().__init__(parent)
        global _LIGHT
        _LIGHT = _light()
        QIcon.setThemeName("CreativePorzellan" if _LIGHT else "Creative")
        base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
        self._dir = Path(base) / "creative-icons" / ("hell" if _LIGHT else "dunkel")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._urls = {}

    @Slot(str, result=str)
    def url(self, icon_id):
        icon_id = icon_id or FALLBACK
        cached = self._urls.get(icon_id)
        if cached:
            return cached
        name = hashlib.sha1(icon_id.encode("utf-8", "replace")).hexdigest()[:20] + ".png"
        path = self._dir / name
        if not path.exists():
            tmp = path.with_suffix(".tmp.png")
            if render_icon(icon_id, self.EDGE).save(str(tmp), "PNG"):
                os.replace(tmp, path)
        url = QUrl.fromLocalFile(str(path)).toString()
        self._urls[icon_id] = url
        return url
