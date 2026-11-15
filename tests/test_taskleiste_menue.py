"""Rechtsklick-Menü der Taskleiste: Alles, was TaskMenu.qml aus shell.taskMenu liest, muss
Taskbar.qml beim Öffnen mitgeben. Fehlte „pinned“, bot das Menü bei angehefteten Apps nur
„Anheften“ an, und man konnte sie nie wieder lösen."""
import re
from pathlib import Path

QML = Path(__file__).resolve().parent.parent / "shell/creative_shell/qml/surfaces"


def test_taskmenue_bekommt_alle_felder():
    menu = (QML / "TaskMenu.qml").read_text(encoding="utf-8")
    bar = (QML / "Taskbar.qml").read_text(encoding="utf-8")
    used = set(re.findall(r"root\.item\.(\w+)", menu)) | set(re.findall(r"\bitem\.(\w+)", menu))
    call = bar[bar.index("shell.toggleTaskMenu("):]
    call = call[:call.index("}, mapToItem")]
    given = set(re.findall(r"(\w+):", call))
    missing = used - given - {"x"}          # x setzt die Shell selbst
    assert not missing, f"Taskbar.qml gibt dem Menü nicht mit: {sorted(missing)}"
