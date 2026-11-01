"""Befehle an KWin (Fenster holen, minimieren, Liste anfordern).

KWin-Skripte können keine Befehle von außen empfangen. Deshalb wird für
jeden Befehl ein winziges Einmal-Skript erzeugt, über KWins D-Bus-Schnittstelle
geladen, ausgeführt und wieder entladen (so arbeitet auch kdotool).
"""

import itertools
import json
import os
import re
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QTimer

from .runner import Runner

SNAPSHOT_JS = """
function snapshot() {
    const active = workspace.activeWindow;
    const windows = [];
    for (const w of workspace.windowList()) {
        if (!w.normalWindow || w.skipTaskbar) continue;
        windows.push({ id: w.internalId.toString(), app: w.desktopFileName || "", cls: w.resourceClass || "", pid: w.pid || 0,
                       title: w.caption || "", output: w.output ? w.output.name : "",
                       minimized: !!w.minimized, active: w === active });
    }
    return JSON.stringify({ windows: windows,
                            activeOutput: workspace.activeScreen ? workspace.activeScreen.name : "" });
}
"""

_counter = itertools.count(1)


def _runtime_dir():
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    path = Path(base) / "creative-shell"
    path.mkdir(mode=0o700, exist_ok=True)
    return path


class KWinBridge(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._run = Runner(self, force_c_locale=True)

    def _gdbus(self, path, method, *args, callback=None):
        cmd = ["gdbus", "call", "--session", "--dest", "org.kde.KWin",
               "--object-path", path, "--method", method, *args]
        self._run.run(cmd, callback)

    def run_script(self, code):
        """Lädt Code als Einmal-Skript in KWin und führt ihn aus."""
        name = f"creative-cmd-{os.getpid()}-{next(_counter)}"
        file = _runtime_dir() / f"{name}.js"
        file.write_text(code, encoding="utf-8")

        def cleanup():
            self._gdbus("/Scripting", "org.kde.kwin.Scripting.unloadScript", name)
            try:
                file.unlink()
            except OSError:
                pass

        def loaded(code_, out, _err):
            match = re.search(r"\((-?\d+),?\)", out)
            if code_ != 0 or not match or int(match.group(1)) < 0:
                cleanup()
                return
            self._gdbus(f"/Scripting/Script{match.group(1)}", "org.kde.kwin.Script.run")
            QTimer.singleShot(3000, cleanup)

        self._gdbus("/Scripting", "org.kde.kwin.Scripting.loadScript", str(file), name, callback=loaded)

    # ---- Befehle ------------------------------------------------------------
    def request_snapshot(self):
        self.run_script(SNAPSHOT_JS + '\ncallDBus("org.creativeos.Shell", "/Shell", '
                        '"org.creativeos.Shell", "update", snapshot());\n')

    def _with_window(self, window_id, body):
        self.run_script(
            "for (const w of workspace.windowList()) {\n"
            f"    if (w.internalId.toString() !== {json.dumps(window_id)}) continue;\n"
            f"    {body}\n"
            "}\n"
        )

    def activate(self, window_id):
        self._with_window(window_id, "w.minimized = false; workspace.activeWindow = w;")

    def minimize(self, window_id):
        self._with_window(window_id, "w.minimized = true;")
