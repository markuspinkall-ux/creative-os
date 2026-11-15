"""BlueZ (/etc/bluetooth/main.conf) für stabile Controller-Verbindungen einstellen.

    python3 bluez-anpassen.py /etc/bluetooth/main.conf

- schnell wieder verbinden, wenn der Controller kurz weg war (FastConnectable, Wiederholungen)
- neu koppeln ohne Rückfrage, wenn ein Controller seine Kopplung vergessen hat (JustWorksRepairing)
- kurze, feste Abstände für Bluetooth-LE-Controller (Xbox Series, neuere Xbox-One-Firmware):
  weniger Verzögerung und keine Abbrüche durch zu lange Pausen (Werte in 1,25 ms)
Bestehende Zeilen werden ersetzt, fehlende ergänzt; alles andere bleibt, wie es ist.
"""
import re
import sys
from pathlib import Path

WERTE = {
    "General": {"FastConnectable": "true", "JustWorksRepairing": "always"},
    "Policy": {"AutoEnable": "true", "ReconnectAttempts": "7", "ReconnectIntervals": "1,2,4,8,16,32,64"},
    "LE": {"MinConnectionInterval": "7", "MaxConnectionInterval": "9", "ConnectionLatency": "0"},
}

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8") if path.exists() else ""
lines = text.splitlines()
for gruppe, werte in WERTE.items():
    start = next((i for i, l in enumerate(lines) if l.strip() == f"[{gruppe}]"), None)
    if start is None:
        lines += ["", f"[{gruppe}]"]
        start = len(lines) - 1
    ende = next((i for i in range(start + 1, len(lines)) if re.match(r"^\s*\[", lines[i])), len(lines))
    for key, value in werte.items():
        muster = re.compile(rf"^\s*#?\s*{key}\s*=")
        treffer = [i for i in range(start + 1, ende) if muster.match(lines[i])]
        neu = f"{key} = {value}"
        if treffer:
            lines[treffer[0]] = neu
        else:
            lines.insert(ende, neu)
            ende += 1
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("BlueZ eingestellt:", path)
