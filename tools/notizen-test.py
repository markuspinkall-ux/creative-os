"""Notizen-Widget: installieren, tippen, speichern, Neustart, entfernen (ohne Bildschirm).
   QT_QPA_PLATFORM=offscreen python3 tools/notizen-test.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

home = Path(tempfile.mkdtemp())
os.environ["HOME"] = str(home)
os.environ["XDG_CONFIG_HOME"] = str(home / ".config")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shell"))

from PySide6.QtCore import QCoreApplication  # noqa: E402

app = QCoreApplication(sys.argv)
from creative_shell import widget_extras as we  # noqa: E402

we.twitch_status = lambda name: {"name": name, "status": "unknown"}   # kein Netz
m = we.WidgetExtras()
assert not m.notesInstalled and not m.notesEnabled and m.notesText == ""
try:
    m.setEnabled("notes", True)
    raise AssertionError("ohne Installation einschaltbar")
except ValueError:
    pass
m.installNotes()
assert m.notesInstalled and m.notesEnabled
text = "Einkauf:\n– Milch\n– Brot 🍞\nTermin Kathrin 18 Uhr"
assert m.saveNotes(text) == ""
path = home / ".config" / "creative-os" / "notizen.json"
saved = json.loads(path.read_text(encoding="utf-8"))
assert saved == {"version": 1, "text": text}, saved
assert oct(path.stat().st_mode & 0o777) == "0o600", oct(path.stat().st_mode)
m.setPosition("notes", 0.3, 1.7)
assert (m.notesX, m.notesY) == (0.3, 1.0)
m2 = we.WidgetExtras()                       # nach Neustart noch da
assert m2.notesText == text and m2.notesEnabled and m2.notesX == 0.3
assert m2.saveNotes("x" * (we.NOTES_MAX + 50)) == "" and len(m2.notesText) == we.NOTES_MAX
m2.setEnabled("notes", False)
assert m2.notesInstalled and not m2.notesEnabled
m2.removeNotes()
assert not m2.notesInstalled and path.exists(), "Text darf beim Entfernen nicht verloren gehen"
m2.installNotes()
assert m2.notesText == "x" * we.NOTES_MAX
path.write_text("kaputt", encoding="utf-8")
assert we.read_notes() == "", "kaputte Datei bringt das Widget zum Absturz"
print("Notizen-Widget: alles in Ordnung")

# Analoge Uhr: herunterladen, einschalten, wieder entfernen (wie die Notizen)
m2.installClock('{"id": "analog-clock", "version": 1, "face": "graphit"}')
assert m2.clockInstalled and m2.clockEnabled
m2.setPosition("clock", 0.7, 0.2)
m2.removeClock()
assert not m2.clockInstalled and not m2.clockEnabled
m3 = we.WidgetExtras()                       # nach Neustart weiterhin entfernt
assert not m3.clockInstalled and not m3.clockEnabled
try:
    m3.setEnabled("clock", True)
    raise AssertionError("entfernte Uhr ließ sich einschalten")
except ValueError:
    pass
m3.installClock('{"id": "analog-clock", "version": 1, "face": "graphit"}')
assert m3.clockInstalled and m3.clockX == 0.7, "Position soll beim Wiederholen erhalten bleiben"
print("Analoge Uhr: entfernen in Ordnung")
