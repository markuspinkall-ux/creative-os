"""Editor: Tasten einrichten (QML-Oberfläche in qml/Main.qml). Speichert automatisch."""

import copy
import queue
import threading
from pathlib import Path

from PySide6.QtCore import Property, QObject, Qt, QTimer, QUrl, Signal, Slot

from . import actions, apps, config, render
from .config import MODELS
from .keys import german

COLORS = ["", "#2b3550", "#5a2a32", "#24453d", "#5a4524", "#3d2f5a", "#2e3340", "#0f1116"]

QT_NAMED = {
    Qt.Key_Return: "enter", Qt.Key_Enter: "enter", Qt.Key_Escape: "esc", Qt.Key_Tab: "tab",
    Qt.Key_Backspace: "backspace", Qt.Key_Delete: "delete", Qt.Key_Insert: "insert",
    Qt.Key_Home: "home", Qt.Key_End: "end", Qt.Key_PageUp: "pageup", Qt.Key_PageDown: "pagedown",
    Qt.Key_Left: "left", Qt.Key_Right: "right", Qt.Key_Up: "up", Qt.Key_Down: "down",
    Qt.Key_Print: "print", Qt.Key_Pause: "pause", Qt.Key_Space: "space", Qt.Key_Minus: "minus",
    Qt.Key_Plus: "plus", Qt.Key_Comma: "comma", Qt.Key_Period: "period",
    Qt.Key_MediaTogglePlayPause: "playpause", Qt.Key_MediaPlay: "playpause", Qt.Key_MediaNext: "next",
    Qt.Key_MediaPrevious: "previous", Qt.Key_MediaStop: "stop", Qt.Key_VolumeUp: "volumeup",
    Qt.Key_VolumeDown: "volumedown", Qt.Key_VolumeMute: "mute",
}
QT_MODIFIER_KEYS = {Qt.Key_Shift, Qt.Key_Control, Qt.Key_Meta, Qt.Key_Alt, Qt.Key_AltGr,
                    Qt.Key_Super_L, Qt.Key_Super_R}


def _int(v):
    return v.value if hasattr(v, "value") else int(v)


def shortcut_from_qt(key, modifiers):
    """Qt-Taste + Modifikatoren → „ctrl+shift+m“ (oder "" bei reinen Modifikatortasten)."""
    key, modifiers = int(key), int(modifiers)
    if key in {_int(k) for k in QT_MODIFIER_KEYS}:
        return ""
    name = None
    for qk, n in QT_NAMED.items():
        if key == _int(qk):
            name = n
            break
    if name is None:
        if _int(Qt.Key_A) <= key <= _int(Qt.Key_Z):
            name = chr(key).lower()
        elif _int(Qt.Key_0) <= key <= _int(Qt.Key_9):
            name = chr(key)
        elif _int(Qt.Key_F1) <= key <= _int(Qt.Key_F24):
            name = f"f{key - _int(Qt.Key_F1) + 1}"
    if name is None:
        return ""
    mods = []
    for flag, n in ((Qt.ControlModifier, "ctrl"), (Qt.ShiftModifier, "shift"),
                    (Qt.AltModifier, "alt"), (Qt.MetaModifier, "meta")):
        if modifiers & _int(flag):
            mods.append(n)
    return "+".join(mods + [name])


class DeckEditor(QObject):
    changed = Signal()          # Seiten/Tasten
    selectionChanged = Signal()
    statusChanged = Signal()
    settingsChanged = Signal()
    messageChanged = Signal()

    def __init__(self, icon_files=None, parent=None):
        super().__init__(parent)
        self.cfg = config.load()
        self._page = 0
        self._sel = 0
        self._status = {}
        self._preview_model = self.cfg.get("letztes_geraet", {}).get("modell") or config.DEFAULT_MODEL
        self._message = ""
        self._apps = None
        self._icons = icon_files
        self.runner = actions.Runner()
        self._save = QTimer(self)
        self._save.setSingleShot(True)
        self._save.setInterval(300)
        self._save.timeout.connect(lambda: config.save(self.cfg))
        self._poll = QTimer(self)
        self._poll.timeout.connect(self.refreshStatus)
        self._poll.start(1500)
        # Meldungen aus Hintergrund-Threads nur im Haupt-Thread anzeigen (sonst kann PySide verklemmen)
        self._inbox = queue.SimpleQueue()
        self._drain = QTimer(self)
        self._drain.timeout.connect(self._take_messages)
        self._drain.start(100)
        self.refreshStatus()

    def _take_messages(self):
        while True:
            try:
                self._set_message(self._inbox.get_nowait())
            except queue.Empty:
                return

    # ---- Hilfen ---------------------------------------------------------------
    def _touch(self):
        self._save.start()
        self.changed.emit()
        self.selectionChanged.emit()

    def _pages(self):
        return self.cfg["seiten"]

    def _keys(self):
        return self._pages()[self._page]["tasten"]

    def _key(self, i=None):
        return self._keys().get(str(self._sel if i is None else i))

    def _ensure_key(self):
        k = self._key()
        if k is None:
            k = {"text": "", "symbol": "", "farbe": "", "aktion": {"typ": "keine"}}
            self._keys()[str(self._sel)] = k
        k.setdefault("aktion", {"typ": "keine"})
        return k

    def symbol_url(self, symbol):
        if not symbol:
            return ""
        kind, _, value = symbol.partition(":")
        if kind == "glyph":
            p = render.glyph_path(value)
            return QUrl.fromLocalFile(p).toString() if p else ""
        if kind in ("app", "icon"):
            name = apps.icon_of(value) if kind == "app" else value
            if self._icons is not None:
                return self._icons.url(name)
            return ""
        if symbol.startswith("/"):
            return QUrl.fromLocalFile(symbol).toString()
        return ""

    # ---- Gerät / Status ---------------------------------------------------------
    @Slot()
    def refreshStatus(self):
        st = config.read_status()
        if st != self._status:
            self._status = st
            devs = st.get("geraete") or []
            if devs:
                d = devs[0]
                last = {"modell": d.get("modell"), "spalten": d.get("spalten"), "zeilen": d.get("zeilen")}
                if self.cfg.get("letztes_geraet") != last:
                    self.cfg["letztes_geraet"] = last
                    self._save.start()
            self.statusChanged.emit()
            self.changed.emit()

    def _device(self):
        devs = self._status.get("geraete") or []
        return devs[0] if devs else None

    def _layout(self):
        d = self._device()
        if d:
            return d.get("spalten") or 5, d.get("zeilen") or 3
        return MODELS.get(self._preview_model, MODELS[config.DEFAULT_MODEL])

    connected = Property(bool, lambda self: self._device() is not None, notify=statusChanged)
    deviceName = Property(str, lambda self: (self._device() or {}).get("modell") or self._preview_model,
                          notify=statusChanged)
    statusError = Property(str, lambda self: self._status.get("fehler") or "", notify=statusChanged)
    daemonRunning = Property(bool, lambda self: bool(self._status) and not self._status.get("beendet"),
                             notify=statusChanged)
    cols = Property(int, lambda self: self._layout()[0], notify=statusChanged)
    rows = Property(int, lambda self: self._layout()[1], notify=statusChanged)
    models = Property("QVariantList", lambda self: list(MODELS), constant=True)

    @Slot(str)
    def setPreviewModel(self, name):
        if name in MODELS:
            self._preview_model = name
            self.statusChanged.emit()
            self.changed.emit()

    # ---- Seiten ---------------------------------------------------------------
    pageNames = Property("QVariantList", lambda self: [p["name"] for p in self._pages()], notify=changed)
    page = Property(int, lambda self: self._page, notify=changed)

    @Slot(int)
    def setPage(self, i):
        if 0 <= i < len(self._pages()):
            self._page = i
            self._sel = 0
            self.changed.emit()
            self.selectionChanged.emit()

    @Slot(str, result=int)
    def addPage(self, name):
        self._pages().append({"name": name.strip() or f"Seite {len(self._pages()) + 1}", "tasten": {
            "0": {"text": "Zurück", "symbol": "glyph:back", "farbe": "", "aktion": {"typ": "zurueck"}}}})
        self._touch()
        return len(self._pages()) - 1

    @Slot(int, str)
    def renamePage(self, i, name):
        if 0 <= i < len(self._pages()) and name.strip():
            self._pages()[i]["name"] = name.strip()
            self._touch()

    @Slot(int)
    def removePage(self, i):
        if len(self._pages()) <= 1 or not 0 <= i < len(self._pages()):
            return
        del self._pages()[i]
        # Verweise auf Seiten anpassen
        for p in self._pages():
            for k in p["tasten"].values():
                a = k.get("aktion") or {}
                if a.get("typ") == "seite" and isinstance(a.get("seite"), int):
                    if a["seite"] == i:
                        a["seite"] = 0
                    elif a["seite"] > i:
                        a["seite"] -= 1
        self._page = min(self._page, len(self._pages()) - 1)
        self._sel = 0
        self._touch()

    # ---- Tasten ---------------------------------------------------------------
    def _key_view(self, i):
        k = self._keys().get(str(i)) or {}
        a = k.get("aktion") or {}
        return {"text": k.get("text", ""), "symbolUrl": self.symbol_url(k.get("symbol", "")),
                "farbe": k.get("farbe") or "", "typ": a.get("typ", "keine"), "seite": a.get("typ") == "seite",
                "leer": not k or (not k.get("text") and not k.get("symbol") and a.get("typ", "keine") == "keine")}

    keys = Property("QVariantList", lambda self: [self._key_view(i) for i in range(self.cols * self.rows)],
                    notify=changed)
    selected = Property(int, lambda self: self._sel, notify=selectionChanged)

    @Slot(int)
    def select(self, i):
        self._sel = i
        self.selectionChanged.emit()

    def _sel_view(self):
        k = self._key() or {}
        a = dict(k.get("aktion") or {"typ": "keine"})
        a.setdefault("typ", "keine")
        return {"text": k.get("text", ""), "symbol": k.get("symbol", ""),
                "symbolUrl": self.symbol_url(k.get("symbol", "")), "farbe": k.get("farbe") or "",
                "aktion": a, "typName": actions.TYPE_NAMES.get(a["typ"], ""),
                "beschreibung": actions.describe(a, [p["name"] for p in self._pages()]),
                "tastenText": german(a.get("tasten", ""))}

    sel = Property("QVariantMap", _sel_view, notify=selectionChanged)

    @Slot(str)
    def setText(self, text):
        k = self._ensure_key()
        if k.get("text") != text:
            k["text"] = text
            self._touch()

    @Slot(str)
    def setSymbol(self, symbol):
        self._ensure_key()["symbol"] = symbol
        self._touch()

    @Slot(str)
    def setGlyph(self, name):
        self.setSymbol("glyph:" + name if name else "")

    @Slot(str)
    def setImage(self, url):
        path = QUrl(url).toLocalFile() if url.startswith("file:") else url
        self.setSymbol(path)

    @Slot(str)
    def setColor(self, color):
        self._ensure_key()["farbe"] = color
        self._touch()

    @Slot(str)
    def setActionType(self, typ):
        k = self._ensure_key()
        old = k["aktion"]
        if old.get("typ") == typ:
            return
        defaults = {"medien": {"was": "play-pause"}, "lautstaerke": {"was": "lauter"},
                    "obs": {"was": "aufnahme"}, "helligkeit": {"was": "hoch"}, "seite": {"seite": 0}}
        k["aktion"] = {"typ": typ, **defaults.get(typ, {})}
        # passende Vorschläge für Beschriftung und Symbol, solange die Taste noch leer ist
        if not k.get("symbol"):
            k["symbol"] = {"befehl": "glyph:terminal", "webseite": "glyph:browser", "tasten": "glyph:grid",
                           "text": "glyph:paste", "medien": "glyph:play", "lautstaerke": "glyph:volume",
                           "mikrofon": "glyph:mic", "obs": "glyph:video", "sound": "glyph:music",
                           "seite": "glyph:folder-plus", "zurueck": "glyph:back",
                           "helligkeit": "glyph:brightness"}.get(typ, "")
        self._touch()

    @Slot(str, str)
    def setActionField(self, field, value):
        a = self._ensure_key()["aktion"]
        if a.get(field) == value:
            return
        before = a.get(field, "")
        a[field] = value
        if field == "app" and value:
            k = self._key()
            # Beschriftung mitziehen, solange sie noch der Name des vorigen Programms ist
            if not k.get("text") or (before and k["text"] == apps.name_of(before)):
                k["text"] = apps.name_of(value)
            if not k.get("symbol") or k["symbol"].startswith("app:"):
                k["symbol"] = "app:" + value
        self._touch()

    @Slot(int)
    def setTargetPage(self, i):
        self._ensure_key()["aktion"] = {"typ": "seite", "seite": int(i)}
        k = self._key()
        if not k.get("text") and 0 <= i < len(self._pages()):
            k["text"] = self._pages()[i]["name"]
        self._touch()

    @Slot(int, int)
    def swap(self, a, b):
        keys = self._keys()
        ka, kb = keys.pop(str(a), None), keys.pop(str(b), None)
        if ka is not None:
            keys[str(b)] = ka
        if kb is not None:
            keys[str(a)] = kb
        self._sel = b
        self._touch()

    @Slot()
    def clearKey(self):
        self._keys().pop(str(self._sel), None)
        self._touch()

    @Slot()
    def copyKey(self):
        self._clip = copy.deepcopy(self._key())

    @Slot()
    def pasteKey(self):
        if getattr(self, "_clip", None):
            self._keys()[str(self._sel)] = copy.deepcopy(self._clip)
            self._touch()

    @Slot()
    def testKey(self):
        a = (self._key() or {}).get("aktion") or {}
        if a.get("typ") in actions.DECK_ACTIONS:
            if a.get("typ") == "seite" and isinstance(a.get("seite"), int):
                self.setPage(a["seite"])
            self._set_message("Diese Taste wirkt auf dem Stream Deck selbst.")
            return

        def work():
            err = self.runner.run(a, self.cfg)
            self._inbox.put(err or "Ausgeführt")
        threading.Thread(target=work, daemon=True).start()

    # ---- Tastenkürzel aufnehmen --------------------------------------------------------
    @Slot(int, int, result=str)
    def shortcutFromKey(self, key, modifiers):
        return shortcut_from_qt(key, modifiers)

    @Slot(str, result=str)
    def shortcutText(self, combo):
        return german(combo)

    # ---- Auswahl-Listen --------------------------------------------------------------
    actionTypes = Property("QVariantList", lambda self: [{"id": i, "name": n} for i, n in actions.TYPES],
                           constant=True)
    colors = Property("QVariantList", lambda self: COLORS, constant=True)

    def _glyphs(self):
        return [{"name": g, "url": QUrl.fromLocalFile(render.glyph_path(g)).toString()}
                for g in render.glyph_names()]

    glyphs = Property("QVariantList", _glyphs, constant=True)

    def _app_list(self):
        if self._apps is None:
            self._apps = [{"id": a["id"], "name": a["name"],
                           "iconUrl": self._icons.url(a["icon"] or "application-x-executable")
                           if self._icons is not None else ""} for a in apps.installed()]
        return self._apps

    appList = Property("QVariantList", _app_list, constant=True)

    @Slot(str, result=str)
    def appName(self, desktop_id):
        return apps.name_of(desktop_id) if desktop_id else ""

    # ---- Einstellungen ----------------------------------------------------------------
    brightness = Property(int, lambda self: self.cfg["helligkeit"], notify=settingsChanged)
    offMinutes = Property(int, lambda self: self.cfg["aus_nach_min"], notify=settingsChanged)
    obsHost = Property(str, lambda self: self.cfg["obs"].get("host", ""), notify=settingsChanged)
    obsPort = Property(int, lambda self: int(self.cfg["obs"].get("port") or 4455), notify=settingsChanged)
    obsPassword = Property(str, lambda self: self.cfg["obs"].get("passwort", ""), notify=settingsChanged)

    @Slot(int)
    def setBrightness(self, v):
        self.cfg["helligkeit"] = max(0, min(100, int(v)))
        self._save.start()
        self.settingsChanged.emit()

    @Slot(int)
    def setOffMinutes(self, v):
        self.cfg["aus_nach_min"] = max(0, int(v))
        self._save.start()
        self.settingsChanged.emit()

    @Slot(str, int, str)
    def setObs(self, host, port, password):
        self.cfg["obs"] = {"host": host.strip() or "localhost", "port": int(port or 4455), "passwort": password}
        self._save.start()
        self.settingsChanged.emit()

    @Slot()
    def testObs(self):
        def work():
            from . import obs
            try:
                info = obs.request(self.cfg["obs"], "GetVersion")
                self._inbox.put("Verbunden mit OBS " + str(info.get("obsVersion", "")))
            except obs.ObsError as exc:
                self._inbox.put(str(exc))
        threading.Thread(target=work, daemon=True).start()

    # ---- Meldungen ------------------------------------------------------------------
    def _set_message(self, text):
        self._message = text
        self.messageChanged.emit()

    message = Property(str, lambda self: self._message, notify=messageChanged)

    @Slot()
    def clearMessage(self):
        self._set_message("")

    @Slot()
    def saveNow(self):
        if self._save.isActive():
            self._save.stop()
            config.save(self.cfg)


def qml_path():
    return Path(__file__).resolve().parent / "qml" / "Main.qml"
