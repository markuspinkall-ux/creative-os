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
for did, name in (("creative-files", "Dateien"), ("brave-browser", "Brave"), ("creative-browser", "Browser"),
                  ("org.kde.konsole", "Konsole"), ("creative-player", "Player"),
                  ("creative-claude", "Claude"), ("creative-youtube", "YouTube"), ("creative-twitch", "Twitch")):
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
assert "creative-browser.desktop" in start and "brave-browser.desktop" not in start, "Browser ersetzt Brave nicht"
for gone in ("creative-youtube.desktop", "creative-twitch.desktop"):
    assert gone not in start, f"{gone} ist noch in der Taskleiste"
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

# Zähler an der Taskleiste (z. B. ungelesene WhatsApp-Nachrichten über D-Bus setBadge)
from creative_shell.tasks import TaskModel  # noqa: E402


class FakeKwin:
    def request_snapshot(self):
        pass


m2.pin("creative-claude.desktop")
t = TaskModel(m2, FakeKwin())
rev = t._revision
t.set_badge("creative-claude.desktop", 5)
item = next(i for i in t.taskbarItems("") if i["key"] == "creative-claude")
assert item["badge"] == 5 and t._revision > rev, item
t.set_badge("creative-claude", 0)
item = next(i for i in t.taskbarItems("") if i["key"] == "creative-claude")
assert item["badge"] == 0, item
assert all(i["badge"] == 0 for i in t.taskbarItems("")), "Zähler bei anderen Apps"
print("Zähler an der Taskleiste: in Ordnung")

# Startmenü: ausblenden und in der Systemsteuerung wieder einblenden
m2.hideFromStartMenu("creative-player.desktop")
assert [r["desktopId"] for r in m2.hidden_apps()] == ["creative-player.desktop"], m2.hidden_apps()
assert m2.hidden_apps()[0]["name"] == "Player"
shown = m2._shown + [x for e in m2._shown for x in (e.members or [])]
assert all(e.desktop_id != "creative-player.desktop" for e in shown), "noch im Startmenü"
m2.showInStartMenu("creative-player.desktop")
assert m2.hidden_apps() == [], m2.hidden_apps()
print("Ausgeblendete Apps wieder anzeigen: in Ordnung")
print("Taskleiste anheften/lösen: alles in Ordnung")
