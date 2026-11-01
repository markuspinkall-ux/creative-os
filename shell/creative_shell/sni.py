"""Tray-Symbole anderer Programme (z. B. Steam, Discord).

Programme melden ihr Tray-Symbol beim „StatusNotifierWatcher“ an (den stellt
kded6 bereit). Hier werden die angemeldeten Symbole gelesen und im Creative-
Look angezeigt; Klick öffnet das Programm, Rechtsklick zeigt sein Menü.
Abfragen laufen über `busctl` (JSON), damit nichts blockiert.
"""

import json

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from .runner import Runner

WATCHER = ("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher", "org.kde.StatusNotifierWatcher")
ITEM_IF = "org.kde.StatusNotifierItem"
MENU_IF = "com.canonical.dbusmenu"

# Bekannte Programme bekommen das passende Creative-Symbol
CREATIVE_ICONS = {"steam": "games", "discord": "chat", "brave": "browser", "creative": "rocket"}


def _data(v):
    """busctl-JSON: {"type": …, "data": …} → Wert"""
    return v.get("data") if isinstance(v, dict) and "data" in v else v


def split_item(entry):
    """„:1.42/org/ayatana/NotificationItem/x“ oder „org.kde.Item-12-1“ → (dienst, pfad)"""
    if "/" in entry:
        i = entry.index("/")
        return entry[:i], entry[i:]
    return entry, "/StatusNotifierItem"


def flatten_menu(node, depth=0):
    """dbusmenu-Layout → flache Liste {id, label, enabled, separator, checked}"""
    out = []
    for child in node[2] if len(node) > 2 else []:
        c = _data(child)
        if not isinstance(c, list) or len(c) < 2:
            continue
        cid, props = c[0], {k: _data(v) for k, v in (c[1] or {}).items()}
        if props.get("visible") is False:
            continue
        if props.get("type") == "separator":
            out.append({"id": cid, "label": "", "separator": True, "enabled": False, "checked": False})
            continue
        label = str(props.get("label", "")).replace("_", "")
        sub = flatten_menu(c, depth + 1) if props.get("children-display") == "submenu" else []
        out.append({"id": cid, "label": ("    " * depth) + label, "separator": False,
                    "enabled": props.get("enabled", True) is not False and not sub,
                    "checked": props.get("toggle-state") == 1})
        out.extend(sub)
    return out


class TrayItems(QObject):
    changed = Signal()
    menuChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = Runner(self, force_c_locale=True)
        self._items = {}            # eintrag → {key, service, path, id, title, icon, creative, menu}
        self._menu = []
        self._menu_key = ""
        self._host_registered = False
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        QTimer.singleShot(1500, self.refresh)

    def _busctl(self, args, cb=None):
        self._run.run(["busctl", "--user", "--json=short"] + args, cb)

    @Slot()
    def refresh(self):
        if not self._host_registered:
            # Damit Programme wissen, dass es einen Tray gibt
            self._run.run(["busctl", "--user", "call", WATCHER[0], WATCHER[1], WATCHER[2],
                           "RegisterStatusNotifierHost", "s", "org.creativeos.Shell"],
                          lambda code, *_: setattr(self, "_host_registered", code == 0))
        self._busctl(["get-property", WATCHER[0], WATCHER[1], WATCHER[2], "RegisteredStatusNotifierItems"],
                     self._on_list)

    def _on_list(self, code, out, _err):
        if code != 0:
            if self._items:
                self._items = {}
                self.changed.emit()
            return
        try:
            entries = _data(json.loads(out)) or []
        except ValueError:
            return
        gone = set(self._items) - set(entries)
        for g in gone:
            del self._items[g]
        if gone:
            self.changed.emit()
        self._round = getattr(self, "_round", 0) + 1
        for e in entries:
            if e not in self._items:
                service, path = split_item(e)
                self._items[e] = {"key": e, "service": service, "path": path, "id": "", "title": "",
                                  "icon": "", "creative": "", "menu": "", "status": "Active"}
                self._fetch(e)
            elif self._round % 5 == 0:          # Status/Symbol ab und zu nachlesen
                self._fetch(e)

    def _fetch(self, entry):
        """Liest Id, Title, IconName, Menu, Status einzeln (fehlt eine, stört das nicht)."""
        it = self._items.get(entry)
        if not it:
            return
        result = {}
        names = ["Id", "Title", "IconName", "Menu", "Status"]

        def got(name):
            def done(code, out, _err):
                try:
                    result[name] = str(_data(json.loads(out)) or "") if code == 0 else ""
                except ValueError:
                    result[name] = ""
                if len(result) == len(names):
                    self._apply(entry, result)
            return done

        for n in names:
            self._busctl(["get-property", it["service"], it["path"], ITEM_IF, n], got(n))

    def _apply(self, entry, r):
        it = self._items.get(entry)
        if not it:
            return
        name = (r["Id"] + " " + r["Title"] + " " + r["IconName"]).lower()
        creative = next((c for k, c in CREATIVE_ICONS.items() if k in name), "")
        new = {**it, "id": r["Id"], "title": r["Title"] or r["Id"], "icon": r["IconName"], "menu": r["Menu"],
               "status": r["Status"] or "Active", "creative": creative}
        if new != it:
            self._items[entry] = new
            self.changed.emit()

    # ---- Aktionen -----------------------------------------------------------------
    @Slot(str)
    def activate(self, key):
        it = self._items.get(key)
        if it:
            self._run.run(["busctl", "--user", "call", it["service"], it["path"], ITEM_IF, "Activate", "ii", "0", "0"])

    @Slot(str)
    def loadMenu(self, key):
        it = self._items.get(key)
        self._menu, self._menu_key = [], key
        self.menuChanged.emit()
        if not it or not it["menu"]:
            return
        self._run.run(["busctl", "--user", "call", it["service"], it["menu"], MENU_IF, "AboutToShow", "i", "0"])

        def done(code, out, _err):
            if code != 0 or self._menu_key != key:
                return
            try:
                data = _data(json.loads(out))
                layout = _data(data[1]) if isinstance(data, list) and len(data) > 1 else None
                self._menu = flatten_menu(layout) if layout else []
            except (ValueError, TypeError, IndexError):
                self._menu = []
            self.menuChanged.emit()

        self._busctl(["call", it["service"], it["menu"], MENU_IF, "GetLayout", "iias", "0", "-1", "0"], done)

    @Slot(int)
    def menuClick(self, item_id):
        it = self._items.get(self._menu_key)
        if it and it["menu"]:
            self._run.run(["busctl", "--user", "call", it["service"], it["menu"], MENU_IF, "Event", "isvu",
                           str(item_id), "clicked", "s", "", "0"])

    def _list(self):
        return [{"key": i["key"], "title": i["title"], "icon": i["icon"], "creative": i["creative"],
                 "hasMenu": bool(i["menu"])}
                for i in self._items.values() if i["status"] != "Passive" and (i["id"] or i["icon"])]

    items = Property("QVariantList", _list, notify=changed)
    menu = Property("QVariantList", lambda self: self._menu, notify=menuChanged)
    menuTitle = Property(str, lambda self: self._items.get(self._menu_key, {}).get("title", ""), notify=menuChanged)
    menuKey = Property(str, lambda self: self._menu_key, notify=menuChanged)
