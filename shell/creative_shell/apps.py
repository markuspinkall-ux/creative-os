"""App-Liste für Startmenü und Taskleiste.

Liest alle .desktop-Dateien nach XDG-Standard (System, Flatpak, Benutzer),
sortiert sie alphabetisch, gruppiert nach Anfangsbuchstaben und filtert für
die Suche. Neue oder entfernte Apps erscheinen automatisch.
"""

import configparser
import os
import shlex
import shutil
import unicodedata
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QFileSystemWatcher,
    QLocale,
    QModelIndex,
    Qt,
    QTimer,
    Signal,
    Slot,
)

from . import config
from .runner import spawn_detached

DESKTOP_NAMES = {"creative", "kde"}

NAME, ICON, DESKTOP_ID, LETTER, COMMENT, IS_FOLDER, FOLDER_ICONS, FOLDER_COUNT = range(
    Qt.ItemDataRole.UserRole + 1, Qt.ItemDataRole.UserRole + 9)

# Eigene Apps („Creative …“) liegen im Startmenü gesammelt im Ordner „Creative Apps“.
FOLDER_ID = "creative-apps-ordner"
FOLDER_NAME = "Creative Apps"
NOT_IN_FOLDER = {"creative-installer.desktop", "creative-browser.desktop"}   # Browser gehört direkt ins Startmenü


def is_creative(entry):
    return entry.name.startswith("Creative ") and entry.desktop_id not in NOT_IN_FOLDER


def is_steam_game(entry):
    """Von Steam angelegte Spiel-Verknüpfung – Spiele gibt es im Game Launcher, nicht im Startmenü."""
    return "steam://rungameid/" in (entry.exec or "")


def application_dirs():
    home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    dirs = [home] + (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    # Flatpak-Apps auch dann finden, wenn XDG_DATA_DIRS sie nicht enthält.
    dirs += [str(Path.home() / ".local/share/flatpak/exports/share"), "/var/lib/flatpak/exports/share"]
    seen, result = set(), []
    for d in dirs:
        p = Path(d) / "applications"
        if d and str(p) not in seen:
            seen.add(str(p))
            result.append(p)
    return result


def _plain(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold()


def _letter(name):
    plain = _plain(name).strip()
    return plain[0].upper() if plain and plain[0].isalpha() else "#"


class AppEntry:
    __slots__ = ("desktop_id", "path", "name", "icon", "comment", "keywords", "exec", "terminal", "search", "hidden",
                 "members")

    def __init__(self, desktop_id, path, name, icon, comment, keywords, exec_line, terminal):
        self.desktop_id = desktop_id
        self.path = path
        self.name = name
        self.icon = icon
        self.comment = comment
        self.keywords = keywords
        self.exec = exec_line
        self.terminal = terminal
        self.hidden = False   # im Startmenü ausgeblendet, aber startbar (z. B. Taskleiste)
        self.members = None   # nur beim Ordner „Creative Apps“: die Apps darin
        self.search = _plain(" ".join([name, comment, keywords, desktop_id]))


def _localized(section, key, langs):
    for lang in langs:
        value = section.get(f"{key}[{lang}]")
        if value:
            return value
    return section.get(key, "")


def parse_desktop_file(path, desktop_id, langs):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeDecodeError):
        return None
    if "Desktop Entry" not in parser:
        return None
    s = parser["Desktop Entry"]
    if s.get("Type") != "Application":
        return None
    if s.get("Hidden", "").lower() == "true":
        return None
    no_display = s.get("NoDisplay", "").lower() == "true"
    only = {x.lower() for x in s.get("OnlyShowIn", "").split(";") if x}
    if only and not (only & DESKTOP_NAMES):
        return None
    not_in = {x.lower() for x in s.get("NotShowIn", "").split(";") if x}
    if not_in & DESKTOP_NAMES:
        return None
    try_exec = s.get("TryExec")
    if try_exec and shutil.which(try_exec) is None and not os.path.exists(try_exec):
        return None
    name = _localized(s, "Name", langs)
    if not name or not s.get("Exec"):
        return None
    entry = AppEntry(
        desktop_id,
        str(path),
        name,
        s.get("Icon", ""),
        _localized(s, "Comment", langs) or _localized(s, "GenericName", langs),
        _localized(s, "Keywords", langs).replace(";", " "),
        s.get("Exec", ""),
        s.get("Terminal", "").lower() == "true",
    )
    entry.hidden = no_display
    return entry


class AppModel(QAbstractListModel):
    filterTextChanged = Signal()
    pinnedChanged = Signal()

    def __init__(self, pinned_config, parent=None):
        super().__init__(parent)
        self._pinned_config = pinned_config
        self._all = []
        self._shown = []
        self._filter = ""
        self._folder = ""
        self._pinned = []
        locale = QLocale().name()  # z. B. de_DE
        self._langs = [locale, locale.split("_")[0]]

        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(800)
        self._reload_timer.timeout.connect(self.reload)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(lambda _p: self._reload_timer.start())
        self.reload()

    # ---- Laden --------------------------------------------------------------
    @Slot()
    def reload(self):
        found = {}
        dirs = application_dirs()
        for base in dirs:
            if not base.is_dir():
                continue
            if str(base) not in self._watcher.directories():
                self._watcher.addPath(str(base))
            for path in base.rglob("*.desktop"):
                desktop_id = str(path.relative_to(base)).replace(os.sep, "-")
                if desktop_id in found:  # frühere Verzeichnisse haben Vorrang
                    continue
                found[desktop_id] = parse_desktop_file(path, desktop_id, self._langs)
        entries = [e for e in found.values() if e is not None]
        entries.sort(key=lambda e: (_letter(e.name) == "#", _plain(e.name)))
        self._all = [e for e in entries if not e.hidden and not is_steam_game(e)]
        self._by_id = {e.desktop_id: e for e in entries}
        self._by_lower = {e.desktop_id.lower(): e for e in entries}
        self._apply_filter()
        self._update_pinned()

    def _update_pinned(self):
        pinned = []
        for item in self._pinned_config:
            for candidate in item.get("candidates", []):
                entry = self._by_id.get(candidate)
                if entry:
                    pinned.append({"desktopId": entry.desktop_id, "name": entry.name, "icon": item.get("icon", ""),
                                   "match": [m.lower() for m in item.get("match", [])]})
                    break
        if pinned != self._pinned:
            self._pinned = pinned
            self.pinnedChanged.emit()

    def _apply_filter(self):
        self.beginResetModel()
        hidden = set(e for e in config.load()['hiddenStartApps'] if isinstance(e, str))
        visible = [e for e in self._all if e.desktop_id not in hidden]
        terms = _plain(self._filter).split()
        if terms:
            hits = [e for e in visible if all(t in e.search for t in terms)]
            # Treffer am Namensanfang zuerst
            hits.sort(key=lambda e: (not _plain(e.name).startswith(terms[0]), _plain(e.name)))
            self._shown = hits
        else:
            creative = [e for e in visible if is_creative(e)]
            if self._folder:
                self._shown = creative
            elif len(creative) >= 2:
                folder = AppEntry(FOLDER_ID, "", FOLDER_NAME, creative[0].icon,
                                  f"{len(creative)} Apps", "", "", False)
                folder.members = creative
                rest = [e for e in visible if not is_creative(e)] + [folder]
                rest.sort(key=lambda e: (_letter(e.name) == "#", _plain(e.name)))
                self._shown = rest
            else:
                self._shown = visible
        self.endResetModel()

    # ---- Model --------------------------------------------------------------
    @Slot(str)
    def hideFromStartMenu(self, desktop_id):
        if desktop_id in self._by_id:
            hidden = config.load()["hiddenStartApps"]
            if desktop_id not in hidden:
                config.set_value("hiddenStartApps", [*hidden, desktop_id])
                self._apply_filter()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._shown)

    def roleNames(self):
        return {
            NAME: QByteArray(b"name"),
            ICON: QByteArray(b"icon"),
            DESKTOP_ID: QByteArray(b"desktopId"),
            LETTER: QByteArray(b"letter"),
            COMMENT: QByteArray(b"comment"),
            IS_FOLDER: QByteArray(b"isFolder"),
            FOLDER_ICONS: QByteArray(b"folderIcons"),
            FOLDER_COUNT: QByteArray(b"folderCount"),
        }

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._shown):
            return None
        e = self._shown[index.row()]
        if role in (NAME, Qt.ItemDataRole.DisplayRole):
            return e.name
        if role == ICON:
            return e.icon
        if role == DESKTOP_ID:
            return e.desktop_id
        if role == LETTER:
            # Bei der Suche keine Buchstaben-Überschriften
            return "" if (self._filter.strip() or self._folder) else _letter(e.name)
        if role == COMMENT:
            return e.comment
        if role == IS_FOLDER:
            return e.members is not None
        if role == FOLDER_ICONS:
            return [m.icon for m in (e.members or [])[:4]]
        if role == FOLDER_COUNT:
            return len(e.members or [])
        return None

    # ---- Für QML ------------------------------------------------------------
    def _get_filter(self):
        return self._filter

    def _set_filter(self, text):
        if text != self._filter:
            self._filter = text
            self._apply_filter()
            self.filterTextChanged.emit()

    filterText = Property(str, _get_filter, _set_filter, notify=filterTextChanged)

    folderChanged = Signal()

    def _get_folder(self):
        return self._folder

    def _set_folder(self, name):
        if name != self._folder:
            self._folder = name
            self._apply_filter()
            self.folderChanged.emit()

    folder = Property(str, _get_folder, _set_folder, notify=folderChanged)
    folderName = Property(str, lambda self: FOLDER_NAME if self._folder else "", notify=folderChanged)

    @Slot()
    def closeFolder(self):
        self._set_folder("")

    def _get_pinned(self):
        return self._pinned

    pinned = Property("QVariantList", _get_pinned, notify=pinnedChanged)

    def lookup(self, desktop_id):
        """Name und Symbol zu einer .desktop-Datei (Groß/Klein egal) oder None."""
        entry = self._by_id.get(desktop_id) or self._by_lower.get(desktop_id.lower())
        if entry is None:
            return None
        return {"desktopId": entry.desktop_id, "name": entry.name, "icon": entry.icon}

    @Slot(int, result=bool)
    def launchAt(self, row):
        """Startet die App – oder öffnet den Ordner „Creative Apps“ (Rückgabe False: Menü bleibt offen)."""
        if 0 <= row < len(self._shown):
            entry = self._shown[row]
            if entry.members is not None:
                self._set_folder(FOLDER_ID)
                return False
            self._launch(entry)
        return True

    @Slot(str)
    def launch(self, desktop_id):
        entry = self._by_id.get(desktop_id)
        if entry:
            self._launch(entry)

    def _launch(self, entry):
        # gio kennt alle Feinheiten der .desktop-Spezifikation (Feldcodes, Terminal …)
        if spawn_detached(["gio", "launch", entry.path]):
            return
        args = [a for a in shlex.split(entry.exec) if not (len(a) == 2 and a.startswith("%"))]
        if entry.terminal:
            args = ["x-terminal-emulator", "-e"] + args
        spawn_detached(args)
