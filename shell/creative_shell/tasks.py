"""Was in der Taskleiste steht: angeheftete Apps plus laufende Programme.

Jede Taskleiste zeigt nur die Fenster ihres eigenen Monitors – wie in der
Systemsteuerung unter „Mehrere Bildschirme“ vorgesehen.

Klickverhalten wie bei Windows:
- App läuft nicht        → starten
- ein Fenster            → nach vorn holen; ist es schon vorn → minimieren
- mehrere Fenster        → der Reihe nach durchschalten
- mittlere Maustaste     → neues Fenster derselben App
"""

import json

from PySide6.QtCore import Property, QObject, Signal, Slot


def app_key(desktop_id_or_app):
    key = (desktop_id_or_app or "").strip()
    if key.endswith(".desktop"):
        key = key[: -len(".desktop")]
    return key.lower()


# Programme, deren Fenster anders heißen als ihre Startmenü-Verknüpfung
WINDOW_ALIASES = {
    "steamwebhelper": "steam",
    "steam": "steam",
    "brave-browser-stable": "brave-browser",
    "discord": "discord",
    "org.kde.kwrite": "org.kde.kwrite",
    "krita": "creative-art",
    "org.kde.krita": "creative-art",
}


class TaskModel(QObject):
    revisionChanged = Signal()

    def __init__(self, apps, kwin, parent=None):
        super().__init__(parent)
        self._apps = apps
        self._kwin = kwin
        self._windows = []
        self._active_output = ""
        self._revision = 0
        apps.pinnedChanged.connect(self._bump)

    # ---- Daten von KWin -------------------------------------------------------
    def update_from_json(self, payload):
        try:
            data = json.loads(payload)
        except ValueError:
            return
        windows = data.get("windows", []) if isinstance(data, dict) else []
        self._windows = [w for w in windows if isinstance(w, dict) and w.get("id")]
        self._active_output = data.get("activeOutput", "") if isinstance(data, dict) else ""
        self._bump()

    def _bump(self):
        self._revision += 1
        self.revisionChanged.emit()

    @property
    def active_output(self):
        return self._active_output

    def request_snapshot(self):
        self._kwin.request_snapshot()

    # ---- Für die Taskleiste ---------------------------------------------------
    def _window_key(self, w):
        key = app_key(w.get("app")) or (w.get("cls") or "").lower()
        key = WINDOW_ALIASES.get(key, key)
        # Web-Apps (Claude, Gemini, ChatGPT …) haben eigene Fensternamen –
        # die werden der angehefteten Verknüpfung zugeordnet.
        names = {key, (w.get("cls") or "").lower()} - {""}
        for pin in self._apps.pinned:
            if any(key.startswith(m) for m in pin.get("match", [])):
                return app_key(pin["desktopId"])
            # Programme melden sich unterschiedlich: „org.kde.konsole“, „konsole“, „Konsole“ …
            pk = app_key(pin["desktopId"])
            short = pk.rsplit(".", 1)[-1]
            if any(n == pk or n == short or n.rsplit(".", 1)[-1] == short for n in names):
                return pk
        return key

    def _items(self, screen):
        on_screen = [w for w in self._windows if w.get("output") == screen or not w.get("output")]
        items, index = [], {}
        for pin in self._apps.pinned:
            key = app_key(pin["desktopId"])
            index[key] = len(items)
            items.append({"key": key, "desktopId": pin["desktopId"], "name": pin["name"],
                          "icon": pin.get("icon", ""), "themeIcon": "", "windows": []})
        for w in on_screen:
            key = self._window_key(w)
            if not key:
                continue
            if key not in index:
                info = self._apps.lookup(key + ".desktop")
                index[key] = len(items)
                items.append({
                    "key": key,
                    "desktopId": info["desktopId"] if info else "",
                    "name": info["name"] if info else (w.get("title") or key),
                    "icon": "",
                    "themeIcon": (info["icon"] if info and info["icon"] else w.get("cls") or key),
                    "windows": [],
                })
            items[index[key]]["windows"].append(w)
        for item in items:
            wins = item["windows"]
            item["running"] = bool(wins)
            item["active"] = any(w.get("active") and not w.get("minimized") for w in wins)
            item["count"] = len(wins)
            item["title"] = wins[0].get("title", "") if len(wins) == 1 else item["name"]
            item["windowIds"] = [w["id"] for w in wins]
            del item["windows"]
        return items

    @Slot(str, result="QVariantList")
    def taskbarItems(self, screen):
        return self._items(screen)

    @Slot(str, str, str)
    def activate(self, screen, key, desktop_id):
        item = next((i for i in self._items(screen) if i["key"] == key), None)
        wins = [w for w in self._windows
                if self._window_key(w) == key and (w.get("output") == screen or not w.get("output"))]
        if not wins:
            if desktop_id:
                self._apps.launch(desktop_id)
            return
        if len(wins) == 1:
            w = wins[0]
            if w.get("active") and not w.get("minimized"):
                self._kwin.minimize(w["id"])
            else:
                self._kwin.activate(w["id"])
            return
        current = next((n for n, w in enumerate(wins) if w.get("active")), -1)
        target = wins[(current + 1) % len(wins)] if item else wins[0]
        self._kwin.activate(target["id"])

    @Slot(str)
    def launchNew(self, desktop_id):
        if desktop_id:
            self._apps.launch(desktop_id)

    revision = Property(int, lambda self: self._revision, notify=revisionChanged)
