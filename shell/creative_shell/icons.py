"""Liefert App-Symbole aus dem Icon-Theme an QML (image://icon/<name>)."""

import hashlib
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QRectF, QSize, Qt, QUrl, Slot
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtQuick import QQuickImageProvider

FALLBACK = "application-x-executable"
# Gibeon-Symbole haben immer Vorrang – auch wenn eine App (z. B. ein OBS-Update oder
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
    # OBS setzt im Tray eigene Symbolnamen (Breeze bringt dafür ein eigenes Symbol mit)
    "obs-tray": "com.obsproject.Studio",
    "obs-tray-active": "com.obsproject.Studio",
    "com.obsproject.studio-tray": "com.obsproject.Studio",
}


def creative_icon(icon_id):
    """Pfad des Gibeon-Symbols für einen Symbolnamen oder Symbolpfad – sonst None."""
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


# Runde Fläche hinter den App-Symbolen (wie in theme/icons/round-icons.py)
CIRCLE_DARK = "#10131a"
CIRCLE_LIGHT = "#d6dce6"
CIRCLE_SCALE = 58 / 64     # Kreis wie bei den Gibeon-Symbolen (r = 29 im 64er-Raster)
LOGO_SCALE = 0.60          # fremdes Logo: so groß, dass es ganz in den Kreis passt


def wants_circle(icon_id):
    """Fremde App-Symbole (keine Gibeon-Symbole, keine Android-Apps) bekommen die runde
    Fläche, damit sie zu den übrigen Symbolen in Startmenü und Taskleiste passen."""
    if not icon_id or creative_icon(icon_id):
        return False
    stem = os.path.splitext(os.path.basename(icon_id))[0].lower()
    return not stem.startswith(("waydroid.", "creative-", "gibeon-"))


def in_circle(pixmap, edge, light=None):
    """Legt ein Symbol mittig in die runde Gibeon-Fläche."""
    light = _LIGHT if light is None else light
    out = QPixmap(edge, edge)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    d = edge * CIRCLE_SCALE
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(CIRCLE_LIGHT if light else CIRCLE_DARK))
    p.drawEllipse(QRectF((edge - d) / 2, (edge - d) / 2, d, d))
    logo = edge * LOGO_SCALE
    p.drawPixmap(QRectF((edge - logo) / 2, (edge - logo) / 2, logo, logo), pixmap,
                 QRectF(0, 0, pixmap.width(), pixmap.height()))
    p.end()
    return out


def render_app_icon(icon_id, edge):
    """App-Symbol für Startmenü und Taskleiste: fremde Symbole in der runden Fläche."""
    if wants_circle(icon_id):
        return in_circle(render_icon(icon_id, edge), edge)
    return render_icon(icon_id, edge)


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
        """Symbol so, wie es ist (z. B. für den Tray)."""
        return self._file(icon_id or FALLBACK, False)

    @Slot(str, result=str)
    def app(self, icon_id):
        """App-Symbol für Startmenü, Taskleiste und Ablage: fremde Symbole rund wie die eigenen."""
        icon_id = icon_id or FALLBACK
        return self._file(icon_id, wants_circle(icon_id))

    def _file(self, icon_id, circle):
        key = ("rund:" if circle else "") + icon_id
        cached = self._urls.get(key)
        if cached:
            return cached
        # Gibeon-Symbol samt Änderungszeit im Namen: ein neues Symbol (Update) ersetzt das alte sofort
        override = creative_icon(icon_id) or ""
        try:
            stamp = f"{override}:{os.path.getmtime(override)}" if override else ""
        except OSError:
            stamp = override
        name = hashlib.sha1(f"{key}|{stamp}|kreis2".encode("utf-8", "replace")).hexdigest()[:20] + ".png"
        path = self._dir / name
        if not path.exists():
            tmp = path.with_suffix(".tmp.png")
            pix = render_icon(icon_id, self.EDGE)
            if circle:
                pix = in_circle(pix, self.EDGE)
            if pix.save(str(tmp), "PNG"):
                os.replace(tmp, path)
        url = QUrl.fromLocalFile(str(path)).toString()
        self._urls[key] = url
        return url
