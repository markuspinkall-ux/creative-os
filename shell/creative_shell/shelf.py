"""Ablage oben mittig auf dem Schreibtisch (wie das Dock bei macOS).

Hält Verknüpfungen zu Apps, Ordnern und Dateien. Gespeichert in shell.json
unter „shelf“ als Liste von Einträgen: "app:<desktop-id>" oder ein Dateipfad.
"""

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Property, QMimeDatabase, QObject, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from . import config
from .desktop import file_color
from .runner import spawn_detached

MAX_ITEMS = 16


class ShelfModel(QObject):
    changed = Signal()

    def __init__(self, apps, parent=None):
        super().__init__(parent)
        self._apps = apps
        self._mime = QMimeDatabase()
        cfg = config.load()
        self._entries = [e for e in cfg.get("shelf", []) if isinstance(e, str)]
        self._enabled = bool(cfg.get("desktopShelf", True))
        self._items = []
        self._build()
        # Apps können später erscheinen (Flatpak-Installation) – dann neu auflösen
        try:
            self._apps.modelReset.connect(self._build)
        except (AttributeError, RuntimeError):
            pass

    # ---- intern ---------------------------------------------------------------------
    def _build(self):
        items = []
        for e in self._entries:
            if e.startswith("app:"):
                info = self._apps.lookup(e[4:])
                if not info:
                    continue
                items.append({"key": e, "kind": "app", "name": info["name"], "icon": info["icon"],
                              "ext": "", "tint": "", "missing": False})
            else:
                p = Path(e)
                is_dir = p.is_dir()
                mime = "" if is_dir else self._mime.mimeTypeForFile(str(p)).name()
                items.append({"key": e, "kind": "dir" if is_dir else "file", "name": p.name or e,
                              "icon": "", "ext": "" if is_dir else p.suffix[1:5].upper(),
                              "tint": "#5a6b8c" if is_dir else file_color(mime), "missing": not p.exists()})
        self._items = items
        self.changed.emit()

    def _save(self):
        config.set_value("shelf", self._entries)
        self._build()

    def _add(self, entry):
        if entry in self._entries:
            return
        if len(self._entries) >= MAX_ITEMS:
            self._entries.pop(0)
        self._entries.append(entry)
        self._save()

    # ---- für QML ----------------------------------------------------------------------
    @Slot(str)
    def addApp(self, desktop_id):
        if desktop_id:
            self._add("app:" + desktop_id)

    @Slot(str)
    def addPath(self, path_or_url):
        """Datei, Ordner oder .desktop-Datei (auch als file://-Adresse beim Ziehen)."""
        s = path_or_url.strip()
        if s.startswith("file:"):
            s = QUrl(s).toLocalFile()
        if not s or not os.path.exists(s):
            return
        if s.endswith(".desktop"):
            info = self._apps.lookup(Path(s).name)
            if info:
                self._add("app:" + info["desktopId"])
                return
        self._add(s)

    @Slot("QVariantList")
    def addUrls(self, urls):
        for u in urls:
            self.addPath(u.toString() if isinstance(u, QUrl) else str(u))

    @Slot(str)
    def remove(self, key):
        if key in self._entries:
            self._entries.remove(key)
            self._save()

    @Slot(str, int)
    def move(self, key, to):
        if key not in self._entries:
            return
        self._entries.remove(key)
        self._entries.insert(max(0, min(to, len(self._entries))), key)
        self._save()

    @Slot(str)
    def open(self, key):
        if key.startswith("app:"):
            self._apps.launch(self._apps.lookup(key[4:])["desktopId"] if self._apps.lookup(key[4:]) else key[4:])
        elif os.path.isdir(key):
            if not spawn_detached(["creative-files", key]):
                QDesktopServices.openUrl(QUrl.fromLocalFile(key))
        elif os.path.exists(key):
            QDesktopServices.openUrl(QUrl.fromLocalFile(key))

    @Slot(str)
    def showInFiles(self, key):
        if key.startswith("app:"):
            return
        folder = key if os.path.isdir(key) else str(Path(key).parent)
        if not spawn_detached(["creative-files", folder]):
            subprocess.Popen(["xdg-open", folder], start_new_session=True)

    @Slot(bool)
    def setEnabled(self, on):
        self._enabled = bool(on)
        config.set_value("desktopShelf", self._enabled)
        self.changed.emit()

    items = Property("QVariantList", lambda self: self._items, notify=changed)
    enabled = Property(bool, lambda self: self._enabled, notify=changed)
