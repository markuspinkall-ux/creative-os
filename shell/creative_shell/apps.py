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

# Früher lagen die eigenen Apps im Startmenü gesammelt im Ordner „Gibeon OS Suite“. Seit
# „Emerald Earth“ stehen alle Apps ganz normal alphabetisch im Startmenü (USE_FOLDER = False);
# der Ordner-Code bleibt, falls er einmal wieder gebraucht wird.
USE_FOLDER = False
FOLDER_ID = "creative-apps-ordner"
FOLDER_NAME = "Gibeon OS Suite"
NOT_IN_FOLDER = {"creative-installer.desktop", "creative-browser.desktop",   # Browser gehört direkt ins Startmenü
                 "gibeon-android.desktop"}                                    # Android-Apps ebenso
SUITE = {
    "creative-art.desktop", "creative-capture.desktop", "creative-3d.desktop",
    "creative-cut.desktop", "creative-ftp.desktop",
    "creative-iso.desktop", "creative-magazin.desktop", "creative-player.desktop",
    "creative-writer.desktop", "gibeon-studio.desktop",
}
# Broadcast, Deck, Shots, Widgets, Pictures, 3D-Ansicht und Taskmanager stehen nicht im Startmenü (NoDisplay):
# der Taskmanager kommt wie bei Windows mit Strg+Umschalt+Esc oder Strg+Alt+Entf;
# Broadcast und Deck leben im Tray, Shots startet mit der Druck-Taste, Widgets per Rechtsklick auf den
# Schreibtisch, Pictures und 3D-Ansicht öffnen sich beim Doppelklick auf ein Bild bzw. eine .glb-Datei.
# Diese Apps stehen nie im Startmenü und nie im Ordner – auch wenn irgendwo noch eine ältere
# Desktop-Datei ohne NoDisplay liegt (z. B. eine lokale Kopie unter ~/.local/share/applications).
ALWAYS_HIDDEN = {"creative-widgets.desktop", "creative-pictures.desktop", "creative-3dansicht.desktop",
                 "creative-broadcast.desktop", "creative-deck.desktop", "creative-shots.desktop",
                 "creative-chatgpt.desktop", "creative-taskmanager.desktop"}
OLD_PREFIX = "Creative "        # alte Namen ohne „Creative“ anzeigen


def is_creative(entry):
    """Gehört in den Ordner „Gibeon OS Suite“."""
    return entry.desktop_id not in NOT_IN_FOLDER and (entry.desktop_id in SUITE or getattr(entry, "suite", False))


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


# Startmenü nach Kategorien (Systemsteuerung › Darstellung › Startmenü: „kategorien“ = Standard,
# „alphabet“ = die alte A–Z-Liste, „kacheln“ = Kategorie-Leiste oben, Apps als Kacheln)
CATEGORY_ORDER = ["Internet", "Kreativ und Medien", "Büro", "Spiele", "Werkzeuge", "Entwicklung", "System", "Sonstige"]
FREEDESKTOP = [            # erste passende Hauptkategorie gewinnt (Reihenfolge = Vorrang)
    ("Game", "Spiele"),
    ("WebBrowser", "Internet"), ("Email", "Internet"), ("InstantMessaging", "Internet"), ("Chat", "Internet"),
    ("Network", "Internet"),
    ("Office", "Büro"), ("WordProcessor", "Büro"), ("Spreadsheet", "Büro"), ("Presentation", "Büro"),
    ("AudioVideo", "Kreativ und Medien"), ("Audio", "Kreativ und Medien"), ("Video", "Kreativ und Medien"),
    ("Graphics", "Kreativ und Medien"), ("Photography", "Kreativ und Medien"),
    ("Development", "Entwicklung"), ("IDE", "Entwicklung"),
    ("Settings", "System"), ("System", "System"), ("PackageManager", "System"), ("Monitor", "System"),
    ("Utility", "Werkzeuge"), ("Accessories", "Werkzeuge"), ("Education", "Büro"), ("Science", "Werkzeuge"),
]
CATEGORY_OVERRIDE = {      # eigene Apps, wo die Freedesktop-Kategorie nicht passt
    "creative-notes.desktop": "Büro",
    "creative-deck.desktop": "Kreativ und Medien",
    "creative-shots.desktop": "Kreativ und Medien",
    "gibeon-android.desktop": "Werkzeuge",
    "creative-iso.desktop": "Werkzeuge",
    "creative-files.desktop": "Werkzeuge",
    "gibeon-fehler-melden.desktop": "System",
    "creative-gamelauncher.desktop": "Spiele",
}
STYLES = ("kategorien", "alphabet", "kacheln")


def category_of(entry):
    if entry.desktop_id in CATEGORY_OVERRIDE:
        return CATEGORY_OVERRIDE[entry.desktop_id]
    cats = set(entry.categories or ())
    for key, group in FREEDESKTOP:
        if key in cats:
            return group
    return "Sonstige"


def start_menu_style():
    style = config.load().get("startMenuStyle", "kategorien")
    return style if style in STYLES else "kategorien"


def _letter(name):
    plain = _plain(name).strip()
    return plain[0].upper() if plain and plain[0].isalpha() else "#"


class AppEntry:
    __slots__ = ("desktop_id", "path", "name", "icon", "comment", "keywords", "exec", "terminal", "search", "hidden",
                 "members", "suite", "categories")

    def __init__(self, desktop_id, path, name, icon, comment, keywords, exec_line, terminal):
        self.desktop_id = desktop_id
        self.path = path
        self.suite = name.startswith(OLD_PREFIX) and len(name) > len(OLD_PREFIX)
        if self.suite:
            name = name[len(OLD_PREFIX):]
        self.name = name
        self.icon = icon
        self.comment = comment
        self.keywords = keywords
        self.exec = exec_line
        self.terminal = terminal
        self.hidden = False   # im Startmenü ausgeblendet, aber startbar (z. B. Taskleiste)
        self.members = None   # nur beim Ordner „Gibeon OS Suite“: die Apps darin
        self.categories = []  # Freedesktop-Kategorien aus der .desktop-Datei
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
    entry.hidden = no_display or desktop_id in ALWAYS_HIDDEN
    entry.categories = [c for c in s.get("Categories", "").split(";") if c]
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
        self._style = start_menu_style()
        self._category = ""          # Kachel-Ansicht: gewählte Kategorie ("" = alle)
        self._categories = []
        self._pinned = []
        cfg = config.load()
        # None = Grundausstattung; sonst die eigene Liste (Desktop-IDs in Reihenfolge)
        self._user_pins = list(cfg.get("taskbarApps", [])) if cfg.get("taskbarAppsSet") else None
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

    def _pin_meta(self, desktop_id):
        """Symbol und Fensternamen aus der Grundausstattung (z. B. für Web-Apps wie Claude)."""
        for item in self._pinned_config:
            if desktop_id in item.get("candidates", []):
                return item
        return {}

    def _update_pinned(self):
        pinned = []
        if self._user_pins is not None:
            for desktop_id in self._user_pins:
                entry = self._by_id.get(desktop_id)
                if entry:
                    item = self._pin_meta(desktop_id)
                    pinned.append({"desktopId": entry.desktop_id, "name": entry.name, "icon": item.get("icon", ""),
                                   "match": [m.lower() for m in item.get("match", [])]})
        else:
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
            creative = [e for e in visible if is_creative(e)] if USE_FOLDER else []
            present = {category_of(e) for e in visible}
            self._categories = [c for c in CATEGORY_ORDER if c in present]
            if self._category and self._category not in present:
                self._category = ""
            if self._style in ("kategorien", "kacheln"):
                order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
                pool = visible if not (self._style == "kacheln" and self._category) else \
                    [e for e in visible if category_of(e) == self._category]
                self._shown = sorted(pool, key=lambda e: (order[category_of(e)], _plain(e.name)))
            elif not USE_FOLDER:
                self._shown = sorted(visible, key=lambda e: (_letter(e.name) == "#", _plain(e.name)))
            elif self._folder:
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
    # ---- Taskleiste: anheften / lösen --------------------------------------------
    def _set_user_pins(self, ids):
        self._user_pins = list(ids)
        config.set_value("taskbarApps", self._user_pins)
        config.set_value("taskbarAppsSet", True)
        self._update_pinned()

    @Slot(str, result=bool)
    def isAutostart(self, desktop_id):
        """Startet diese App beim Anmelden (~/.config/autostart)?"""
        from . import autostart
        return autostart.is_enabled(desktop_id)

    @Slot(str, bool)
    def setAutostart(self, desktop_id, on):
        from . import autostart
        entry = self._by_id.get(desktop_id)
        try:
            if on and entry is not None:
                autostart.enable(desktop_id, entry.path)
            elif not on:
                autostart.disable(desktop_id)
        except OSError as e:
            print(f"creative-shell: Autostart {desktop_id}: {e}")

    @Slot(str, result=bool)
    def isPinned(self, desktop_id):
        return any(p["desktopId"] == desktop_id for p in self._pinned)

    @Slot(str)
    def pin(self, desktop_id):
        ids = [p["desktopId"] for p in self._pinned]
        if desktop_id in self._by_id and desktop_id not in ids:
            self._set_user_pins(ids + [desktop_id])

    @Slot(str)
    def unpin(self, desktop_id):
        ids = [p["desktopId"] for p in self._pinned]
        if desktop_id in ids:
            self._set_user_pins([i for i in ids if i != desktop_id])

    @Slot(str, int)
    def movePin(self, desktop_id, index):
        ids = [p["desktopId"] for p in self._pinned]
        if desktop_id not in ids:
            return
        ids.remove(desktop_id)
        ids.insert(max(0, min(index, len(ids))), desktop_id)
        self._set_user_pins(ids)

    @Slot(str)
    def hideFromStartMenu(self, desktop_id):
        if desktop_id in self._by_id:
            hidden = config.load()["hiddenStartApps"]
            if desktop_id not in hidden:
                config.set_value("hiddenStartApps", [*hidden, desktop_id])
                self._apply_filter()

    def hidden_apps(self):
        """Ausgeblendete Apps (nur solche, die es noch gibt) – für Systemsteuerung › Darstellung."""
        rows = []
        for desktop_id in config.load()["hiddenStartApps"]:
            entry = self._by_id.get(desktop_id) if isinstance(desktop_id, str) else None
            if entry:
                rows.append({"desktopId": desktop_id, "name": entry.name, "icon": entry.icon})
        rows.sort(key=lambda r: _plain(r["name"]))
        return rows

    @Slot(str)
    def showInStartMenu(self, desktop_id):
        hidden = config.load()["hiddenStartApps"]
        if desktop_id in hidden:
            config.set_value("hiddenStartApps", [h for h in hidden if h != desktop_id])
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
            # Bei der Suche keine Überschriften; je nach Stil Kategorie oder Anfangsbuchstabe
            if self._filter.strip() or self._folder or self._style == "kacheln":
                return ""
            return category_of(e) if self._style == "kategorien" else _letter(e.name)
        if role == COMMENT:
            return e.comment
        if role == IS_FOLDER:
            return e.members is not None
        if role == FOLDER_ICONS:
            return [m.icon for m in (e.members or [])[:4]]
        if role == FOLDER_COUNT:
            return len(e.members or [])
        return None

    # ---- Startmenü-Stil und Kategorien --------------------------------------------
    styleChanged = Signal()

    @Slot()
    def refreshStyle(self):
        """Beim Öffnen des Startmenüs: Stil aus der Systemsteuerung übernehmen."""
        style = start_menu_style()
        if style != self._style:
            self._style = style
            self._category = ""
            self._apply_filter()
            self.styleChanged.emit()

    @Slot(str)
    def setCategory(self, category):
        if category != self._category:
            self._category = category
            self._apply_filter()
            self.styleChanged.emit()

    style = Property(str, lambda self: self._style, notify=styleChanged)
    category = Property(str, lambda self: self._category, notify=styleChanged)
    categories = Property("QVariantList", lambda self: list(self._categories), notify=styleChanged)

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
        """Startet die App – oder öffnet den Ordner „Gibeon OS Suite“ (Rückgabe False: Menü bleibt offen)."""
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
