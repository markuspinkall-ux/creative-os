"""Schreibtisch-Symbole: Plätze speichern, verdrängen, aufräumen (ohne Bildschirm).
   cd shell && python3 ../tools/schreibtisch-test.py modell"""
import os
import sys
import tempfile
from pathlib import Path

home = Path(tempfile.mkdtemp())
(home / "Schreibtisch").mkdir()
for n in ("a.txt", "b.txt", "c.txt"):
    (home / "Schreibtisch" / n).write_text("x")
os.environ["HOME"] = str(home)
os.environ["XDG_CONFIG_HOME"] = str(home / ".config")
os.environ["PATH"] = "/usr/bin:/bin"          # kein xdg-user-dir → ~/Schreibtisch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shell"))
from PySide6.QtGui import QGuiApplication  # noqa: E402

app = QGuiApplication(sys.argv)
from creative_shell import config  # noqa: E402
from creative_shell import desktop as dm  # noqa: E402
from creative_shell.desktop import DesktopModel  # noqa: E402

dm.desktop_dir = lambda: home / "Schreibtisch"

m = DesktopModel()
d = str(home / "Schreibtisch")
a, b, c = (f"{d}/{n}" for n in ("a.txt", "b.txt", "c.txt"))
m.placeDragged(a, "HDMI-1", 3, 2)
assert m.cells["HDMI-1"][a] == [3, 2], m.cells
m.placeDragged(b, "HDMI-1", 3, 2)               # b verdrängt a
assert m.cells["HDMI-1"][b] == [3, 2] and a not in m.cells["HDMI-1"], m.cells
m.placeDragged(b, "DP-2", 0, 0)                 # anderer Monitor: alter Platz vergessen
assert b not in m.cells["HDMI-1"] and m.cells["DP-2"][b] == [0, 0], m.cells
assert config.load()["desktopIconCells"]["DP-2"][b] == [0, 0], "nicht gespeichert"
m2 = DesktopModel()                             # nach Neustart noch da
assert m2.cells["DP-2"][b] == [0, 0]
os.remove(b)
m2.refresh()
assert b not in m2.cells.get("DP-2", {}), "gelöschte Datei hat noch einen Platz"
# Auswahl wandert gemeinsam, untereinander
m2.refresh()
rows = {r["path"]: i for i, r in enumerate(m2._rows)}
m2.selectRows([rows[a], rows[c]])
m2.placeDragged(c, "HDMI-1", 1, 4)
assert m2.cells["HDMI-1"][c] == [1, 4] and m2.cells["HDMI-1"][a] == [1, 5], m2.cells
print("Schreibtisch-Plätze: alles in Ordnung")
