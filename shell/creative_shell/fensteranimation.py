"""Fenster öffnen dynamisch: meldet dem KWin-Effekt „gibeon-fenster“, wo die Symbole liegen.

Der Effekt (shell/kwin/gibeon-fenster) lässt neue Fenster aus dem angeklickten Symbol wachsen und
minimierte Fenster in ihr Taskleisten-Symbol schrumpfen. Die Lage der Symbole steht in kwinrc,
Gruppe [Effect-gibeon-fenster]; danach wird der Effekt neu geladen (das dauert Millisekunden).
"""

import json
import shutil
import subprocess
import time

from PySide6.QtCore import QObject, QTimer, Slot

GROUP = "Effect-gibeon-fenster"
EFFECT = "gibeon-fenster"


def _write(key, value):
    if not shutil.which("kwriteconfig6"):
        return
    script = ('kwriteconfig6 --file kwinrc --group "$1" --key "$2" "$3" && '
              'dbus-send --session --type=method_call --dest=org.kde.KWin /Effects '
              'org.kde.kwin.Effects.reconfigureEffect "string:$4" >/dev/null 2>&1')
    try:
        subprocess.Popen(["sh", "-c", script, "sh", GROUP, key, value, EFFECT],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


def names_for(key, desktop_id, windows=()):
    """Alle Namen, unter denen sich die Fenster dieses Programms melden können."""
    out = []

    def add(v):
        v = (v or "").strip().lower()
        if v.endswith(".desktop"):
            v = v[:-8]
        if v and v not in out:
            out.append(v)

    add(key)
    add(desktop_id)
    for v in list(out):
        add(v.rsplit(".", 1)[-1])          # org.kde.dolphin → dolphin
    for w in windows:
        add(w.get("app"))
        add(w.get("cls"))
    return out


class WindowAnimation(QObject):
    def __init__(self, tasks=None, parent=None):
        super().__init__(parent)
        self._tasks = tasks
        self._points = {}            # Monitor → [{"n": [...], "x", "y"}]
        self._last = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self._flush)

    def _windows_for(self, key):
        tasks = self._tasks
        if tasks is None:
            return []
        try:
            return [w for w in tasks._windows if tasks._window_key(w) == key]
        except Exception:  # noqa: BLE001
            return []

    @Slot(str, "QVariantList")
    def setTaskPoints(self, screen, items):
        """Taskleiste: Mitte jedes Symbols in Bildschirm-Koordinaten (key, desktopId, x, y)."""
        pts = []
        for it in items or []:
            try:
                key = str(it.get("key") or "")
                pts.append({"n": names_for(key, str(it.get("desktopId") or ""), self._windows_for(key)),
                            "x": round(float(it["x"])), "y": round(float(it["y"]))})
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
        self._points[screen] = pts
        self._timer.start()

    def _flush(self):
        data = [p for pts in self._points.values() for p in pts if p["n"]]
        text = json.dumps(data, separators=(",", ":"))
        if text != self._last:
            self._last = text
            _write("Tasten", text)

    @Slot(float, float)
    def noteLaunch(self, x, y):
        """Startmenü: Das nächste neue Fenster wächst aus dieser Stelle."""
        _write("Start", f"{round(x)},{round(y)},{int(time.time() * 1000)}")
