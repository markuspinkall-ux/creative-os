#!/usr/bin/python3
"""Nur für Prüfungen: setzt vor jede Zeile einer GRUB-Konfiguration (auch in Blöcken) ein
„echo SPUR <datei>:<zeile>“ – so zeigt die serielle Ausgabe, welche Zeile eine Meldung auslöst."""
import re
import sys

path, tag = sys.argv[1], sys.argv[2]
out = []
for n, line in enumerate(open(path, encoding="utf-8").read().splitlines(), 1):
    s = line.strip()
    # nicht vor Fortsetzungen (else/elif/fi/}/then) und nicht in Leer-/Kommentarzeilen
    if s and not s.startswith("#") and not re.match(r"^(else|elif|fi|then|done|do)\b|^\}", s):
        out.append(f'echo "SPUR {tag}:{n}"')
    out.append(line)
open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
