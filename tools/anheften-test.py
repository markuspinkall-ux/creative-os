"""Taskleiste: Programme anheften und lösen (Startmenü/Taskleiste › Rechtsklick).
   QT_QPA_PLATFORM=offscreen python3 tools/anheften-test.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

home = Path(tempfile.mkdtemp())
os.environ["HOME"] = str(home)
os.environ["XDG_CONFIG_HOME"] = str(home / ".config")
os.environ["XDG_DATA_HOME"] = str(home / ".local/share")
os.environ["XDG_DATA_DIRS"] = str(home / "share")
apps_dir = home / "share/applications"
apps_dir.mkdir(parents=True)
for did, name in (("creative-files", "Dateien"), ("brave-browser", "Brave"), ("creative-browser", "Creative Browser"),
                  ("org.kde.konsole", "Konsole"), ("creative-player", "Creative Player"),
                  ("creative-claude", "Claude")):
    (apps_dir / f"{did}.desktop").write_text(
        f"[Desktop Entry]\nType=Application\nName={name}\nExec=true\nIcon={did}\n")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shell"))
from PySide6.QtGui import QGuiApplication  # noqa: E402

app = QGuiApplication(sys.argv)
from creative_shell import config  # noqa: E402
from creative_shell.apps import AppModel  # noqa: E402


def ids(model):
    return [p["desktopId"] for p in model.pinned]


m = AppModel(config.load()["pinned"])
m.reload()
start = ids(m)
print("Grundausstattung:", start)
assert "creative-browser.desktop" in start and "brave-browser.desktop" not in start, "Creative Browser ersetzt Brave nicht"
assert start.index("creative-browser.desktop") == 1, start
claude = next(p for p in m.pinned if p["desktopId"] == "creative-claude.desktop")
assert claude["icon"] == "claude" and claude["match"], "Web-App verliert Symbol/Fensternamen"

m.pin("creative-player.desktop")
assert ids(m)[-1] == "creative-player.desktop" and m.isPinned("creative-player.desktop"), ids(m)
m.pin("creative-player.desktop")
assert ids(m).count("creative-player.desktop") == 1, "doppelt angeheftet"
m.unpin("org.kde.konsole.desktop")
assert "org.kde.konsole.desktop" not in ids(m)
m.pin("gibt-es-nicht.desktop")
assert "gibt-es-nicht.desktop" not in ids(m)
m.movePin("creative-player.desktop", 0)
assert ids(m)[0] == "creative-player.desktop", ids(m)

saved = json.loads((home / ".config/creative-os/shell.json").read_text())
assert saved["taskbarAppsSet"] is True and saved["taskbarApps"] == ids(m), saved

m2 = AppModel(config.load()["pinned"])     # nach einem Neustart
m2.reload()
assert ids(m2) == ids(m), (ids(m2), ids(m))
claude2 = next(p for p in m2.pinned if p["desktopId"] == "creative-claude.desktop")
assert claude2["icon"] == "claude" and claude2["match"]
print("Eigene Auswahl:", ids(m2))
print("Taskleiste anheften/lösen: alles in Ordnung")
