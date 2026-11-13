"""Tray-Symbole anderer Programme (z. B. Steam, Discord).

Programme melden ihr Tray-Symbol beim „StatusNotifierWatcher“ an (den stellt
kded6 bereit). Hier werden die angemeldeten Symbole gelesen und im Creative-
Look angezeigt; Klick öffnet das Programm, Rechtsklick zeigt sein Menü.
Abfragen laufen über `busctl` (JSON), damit nichts blockiert.
"""

import glob
import hashlib
import json
import os
import re
import signal
import struct
import tempfile
import zlib

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtGui import QIcon

from .runner import Runner

WATCHER = ("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher", "org.kde.StatusNotifierWatcher")
ITEM_IF = "org.kde.StatusNotifierItem"
MENU_IF = "com.canonical.dbusmenu"

# Bekannte Programme bekommen das passende Creative-Symbol
CREATIVE_ICONS = {"steam": "games", "discord": "chat", "brave": "browser", "creative": "rocket"}


# Gehören zum System und laufen ab dem Start immer – die lassen sich im Tray nicht beenden
SYSTEM_PROCS = ("creative", "kded", "polkit", "xembedsniproxy", "kwalletd", "plasmashell", "powerdevil",
                "pipewire", "wireplumber", "kwin", "ksmserver", "nm-applet", "kaccess")
QUIT_LABEL = re.compile(r"^\s*(beenden|quit|exit|schließen|programm beenden)\b|\b(beenden|quit|exit)\s*$|^\s*(quit|exit)\s+\S+",
                        re.I)


def process_info(pid):
    """(Befehlszeile, gehört zum System?) eines Prozesses."""
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
    except OSError:
        return "", True
    low = cmd.lower()
    return cmd, any(p in low for p in SYSTEM_PROCS)


def _data(v):
    """busctl-JSON: {"type": …, "data": …} → Wert"""
    return v.get("data") if isinstance(v, dict) and "data" in v else v


PIXMAP_DIR = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir(),
                          "creative-shell", "tray")
ICON_EXTS = (".png", ".svg", ".xpm")


def find_in_theme_path(name, theme_path):
    """IconName + IconThemePath → absoluter Dateipfad (oder "").
    Electron/Chromium legen das Symbol z. B. direkt als <pfad>/<name>.png ab,
    andere Programme als kleines Theme (<pfad>/hicolor/32x32/apps/<name>.png)."""
    if not name or not theme_path or not os.path.isdir(theme_path):
        return ""
    if os.path.isabs(name) and os.path.exists(name):
        return name
    for ext in ("",) + ICON_EXTS:
        p = os.path.join(theme_path, name + ext)
        if os.path.isfile(p):
            return p
    found = []
    for ext in ICON_EXTS:
        found += glob.glob(os.path.join(theme_path, "*", "*", "*", name + ext))
        found += glob.glob(os.path.join(theme_path, "*", "*", name + ext))
    if not found:
        return ""

    def size(p):                       # „…/48x48/apps/x.png“ → 48, scalable zuerst
        for part in p.split(os.sep):
            if part == "scalable":
                return 10 ** 6
            if "x" in part and part.split("x")[0].isdigit():
                return int(part.split("x")[0])
        return 0
    return max(found, key=size)


def best_pixmap(pixmaps):
    """IconPixmap (a(iiay)) → (breite, höhe, bytes) der größten gültigen Variante."""
    best = None
    for p in pixmaps or []:
        p = _data(p)
        if not isinstance(p, list) or len(p) < 3:
            continue
        w, h, raw = int(_data(p[0])), int(_data(p[1])), _data(p[2])
        raw = bytes(raw or [])
        if w > 0 and h > 0 and len(raw) >= w * h * 4 and (best is None or w * h > best[0] * best[1]):
            best = (w, h, raw[:w * h * 4])
    return best


def pixmap_to_png(w, h, argb):
    """SNI-Pixmap (ARGB32, Big Endian = Bytes A,R,G,B) → PNG-Bytes (RGBA)."""
    rgba = bytearray(len(argb))
    rgba[0::4], rgba[1::4], rgba[2::4], rgba[3::4] = argb[1::4], argb[2::4], argb[3::4], argb[0::4]
    stride = w * 4
    rows = b"".join(b"\0" + bytes(rgba[y * stride:(y + 1) * stride]) for y in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def save_pixmap(pixmaps):
    """Schreibt die Pixmap als PNG in den Cache und gibt den Pfad zurück ("" wenn leer).
    Der Dateiname enthält eine Prüfsumme: ändert das Programm sein Symbol,
    ändert sich der Pfad, und QML lädt das neue Bild statt eines gecachten."""
    best = best_pixmap(pixmaps)
    if not best:
        return ""
    w, h, raw = best
    if not any(raw[0::4]):                        # komplett transparent
        return ""
    digest = hashlib.sha1(struct.pack(">II", w, h) + raw).hexdigest()[:16]
    path = os.path.join(PIXMAP_DIR, digest + ".png")
    if not os.path.exists(path):
        try:
            os.makedirs(PIXMAP_DIR, mode=0o700, exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(pixmap_to_png(w, h, raw))
            os.replace(tmp, path)
        except OSError:
            return ""
    return path


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

    def __init__(self, tasks, parent=None):
        super().__init__(parent)
        self._tasks = tasks
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
        """Liest Id, Title, IconName, IconThemePath, Menu, Status einzeln (fehlt eine, stört das nicht)."""
        it = self._items.get(entry)
        if not it:
            return
        result = {}
        names = ["Id", "Title", "IconName", "IconThemePath", "Menu", "Status"]

        def got(name):
            def done(code, out, _err):
                try:
                    result[name] = str(_data(json.loads(out)) or "") if code == 0 else ""
                except ValueError:
                    result[name] = ""
                if len(result) == len(names):
                    self._resolve_icon(entry, result)
            return done

        for n in names:
            self._busctl(["get-property", it["service"], it["path"], ITEM_IF, n], got(n))
        if not it.get("pid"):
            def pid_done(code, out, _err):
                cur = self._items.get(entry)
                if not cur or code != 0:
                    return
                try:
                    result = _data(json.loads(out))
                    pid = int(result[0] if isinstance(result, list) and result else result)
                except (ValueError, TypeError):
                    return
                _cmd, system = process_info(pid)
                if pid != cur.get("pid") or system != cur.get("system"):
                    self._items[entry] = {**cur, "pid": pid, "system": system}
                    self.changed.emit()
                    self.menuChanged.emit()
            self._busctl(["call", "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                          "GetConnectionUnixProcessID", "s", it["service"]], pid_done)

    def _resolve_icon(self, entry, r):
        """Symbol in dieser Reihenfolge suchen (wie KDE):
        1. IconName im eigenen IconThemePath des Programms
        2. IconName im Icon-Theme
        3. IconPixmap – die Bilddaten selbst (Electron-Apps wie ChatGPT, Slack, Element)"""
        name, theme_path = r["IconName"], r["IconThemePath"]
        icon = find_in_theme_path(name, theme_path)
        if not icon and name and (os.path.isabs(name) and os.path.exists(name) or QIcon.hasThemeIcon(name)):
            icon = name
        if icon:
            self._apply(entry, {**r, "Icon": icon})
            return
        it = self._items.get(entry)
        if not it:
            return

        def done(code, out, _err):
            path = ""
            if code == 0:
                try:
                    path = save_pixmap(_data(json.loads(out)))
                except (ValueError, TypeError):
                    path = ""
            # Ohne Pixmap den Namen trotzdem durchreichen (QML zeigt dann das Ersatzsymbol)
            self._apply(entry, {**r, "Icon": path or name})

        self._busctl(["get-property", it["service"], it["path"], ITEM_IF, "IconPixmap"], done)

    def _apply(self, entry, r):
        it = self._items.get(entry)
        if not it:
            return
        name = (r["Id"] + " " + r["Title"] + " " + r["IconName"]).lower()
        creative = next((c for k, c in CREATIVE_ICONS.items() if k in name), "")
        new = {**it, "id": r["Id"], "title": r["Title"] or r["Id"], "icon": r.get("Icon", r["IconName"]), "menu": r["Menu"],
               "status": r["Status"] or "Active", "creative": creative}
        if new != it:
            self._items[entry] = new
            self.changed.emit()

    # ---- Aktionen -----------------------------------------------------------------
    @Slot(str)
    def activate(self, key):
        it = self._items.get(key)
        if not it:
            return

        def done(code, out, _err):
            if self._items.get(key) is not it:
                return
            try:
                result = _data(json.loads(out)) if code == 0 else 0
                pid = int(result[0] if isinstance(result, list) and result else result)
            except (ValueError, TypeError):
                pid = 0
            if not self._tasks.toggle_tray_window(pid, it["id"]):
                self._run.run(["busctl", "--user", "call", it["service"], it["path"],
                               ITEM_IF, "Activate", "ii", "0", "0"])

        self._busctl(["call", "org.freedesktop.DBus", "/org/freedesktop/DBus",
                      "org.freedesktop.DBus", "GetConnectionUnixProcessID", "s", it["service"]], done)

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

    @Slot(str)
    def quit(self, key):
        """Programm beenden: zuerst über seinen eigenen „Beenden“-Eintrag (sauber, speichert),
        sonst – oder wenn es nach 4 s noch läuft – mit SIGTERM."""
        it = self._items.get(key)
        if not it or it.get("system", True) or not it.get("pid"):
            return
        pid = it["pid"]
        entry = next((m for m in (self._menu if self._menu_key == key else [])
                      if not m["separator"] and m["enabled"] and QUIT_LABEL.search(m["label"].strip())), None)

        def term():
            cmd = process_info(pid)[0]
            if not cmd:
                return                     # schon beendet
            # Flatpak-Programme hängen hinter einem D-Bus-Vermittler: dann das Programm selbst beenden
            m = re.search(r"\.flatpak/([0-9]+)/", cmd) if "xdg-dbus-proxy" in cmd else None
            if m:
                import subprocess
                try:
                    out = subprocess.run(["flatpak", "ps", "--columns=instance,application"],
                                         capture_output=True, text=True, timeout=5).stdout
                except (OSError, subprocess.SubprocessError):
                    return
                app = next((line.split()[1] for line in out.splitlines()
                            if line.split() and line.split()[0] == m.group(1) and len(line.split()) > 1), "")
                if app:
                    self._run.run(["flatpak", "kill", app])
                return
            try:
                os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass

        if entry is not None and it.get("menu"):
            self._run.run(["busctl", "--user", "call", it["service"], it["menu"], MENU_IF, "Event", "isvu",
                           str(entry["id"]), "clicked", "s", "", "0"])
            QTimer.singleShot(4000, term)
        else:
            term()

    def _list(self):
        return [{"key": i["key"], "title": i["title"], "icon": i["icon"], "creative": i["creative"],
                 "hasMenu": bool(i["menu"]), "canQuit": bool(i.get("pid")) and not i.get("system", True)}
                for i in self._items.values() if i["status"] != "Passive" and (i["id"] or i["icon"])]

    items = Property("QVariantList", _list, notify=changed)
    menu = Property("QVariantList", lambda self: self._menu, notify=menuChanged)
    menuTitle = Property(str, lambda self: self._items.get(self._menu_key, {}).get("title", ""), notify=menuChanged)
    menuKey = Property(str, lambda self: self._menu_key, notify=menuChanged)
    menuHasItems = Property(bool, lambda self: bool(self._items.get(self._menu_key, {}).get("menu")), notify=menuChanged)
    menuCanQuit = Property(bool, lambda self: (lambda i: bool(i.get("pid")) and not i.get("system", True))(
        self._items.get(self._menu_key, {})), notify=menuChanged)
