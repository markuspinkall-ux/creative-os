"""Qt-Anbindung für „Öffnen mit“ (Dateien und Schreibtisch: `creative-files --open-with Datei`)."""

from pathlib import Path

from PySide6.QtCore import QMimeDatabase, QObject, Signal, Slot

from . import openwith


class OpenWithChooser(QObject):
    """prepare(Pfade) liefert die App-Liste fürs Fenster, choose(App, immer) öffnet."""

    message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = QMimeDatabase()
        self._paths, self._mime, self._apps = [], "", {}

    def _mimes(self, path):
        mime = self._db.mimeTypeForFile(path)
        names = [mime.name()] + list(mime.aliases()) + list(mime.allAncestors())
        if mime.name().startswith("text/") and "text/plain" not in names:
            names.append("text/plain")
        return mime, list(dict.fromkeys(names))

    @Slot("QVariantList", result="QVariantMap")
    def prepare(self, paths):
        self._paths = [str(p) for p in paths if p and Path(str(p)).is_file()]
        if not self._paths:
            return {"ok": False}
        mime, names = self._mimes(self._paths[0])
        self._mime = mime.name()
        self._apps = openwith.installed_apps()
        lists = openwith.apps_for(names, self._apps)
        first = Path(self._paths[0]).name
        return {
            "ok": True,
            "title": first if len(self._paths) == 1 else f"{len(self._paths)} Dateien",
            "typeName": mime.comment() or self._mime,
            "recommended": lists["recommended"],
            "others": lists["others"],
        }

    @Slot(str, bool, result=bool)
    def choose(self, desktop_id, always):
        if not self._paths:
            return False
        if always and self._mime:
            try:
                openwith.set_default(self._mime, desktop_id)
            except OSError:
                self.message.emit("Die Standard-App konnte nicht gespeichert werden.")
        ok = openwith.launch(desktop_id, self._paths, self._apps)
        if not ok:
            self.message.emit("Die App konnte nicht gestartet werden.")
        return ok
