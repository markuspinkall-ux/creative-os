#!/usr/bin/python3
"""Schlichte App-Symbole: aus der Graphit-Kachel (Rechteck mit blauem Rand) wird eine runde Fläche
ohne Rand, und das Symbol darin bekommt durchgehend die Schriftfarbe (keine bunten Akzente).
Passt zu den runden Symbolen der Android-Apps. Porzellan entsteht danach wie gewohnt daraus.

  round-icons.py <datei.svg> …      Dateien an Ort und Stelle umwandeln
"""

import re
import sys
from pathlib import Path

TILE = "#232836"
# Runde Fläche: deutlich dunkler als das Startmenü, damit der Kreis gut zu sehen ist
CIRCLE_FILL = "#10131a"
TEXT = "#dce6ff"
# Kachel-Rechteck (64er-Symbol): fill="#232836", meist mit stroke="#8fb3ff"
TILE_RECT = re.compile(r'<rect\b(?=[^>]*\bfill="#(?:232836|1c2029)")(?=[^>]*\bwidth="(?:5[4-8]|6[0-4])")[^>]*?/?>(?:\s*</rect>)?', re.I)
CIRCLE = f'<circle cx="32" cy="32" r="29" fill="{CIRCLE_FILL}"/>'
# Akzente im Symbol → Schriftfarbe (Aussparungen #12151b/#232836 bleiben)
ACCENTS = re.compile(r"#8fb3ff|#ffb07a|#6fdcc0|#e5484d|#9f7aea", re.I)


def is_tile(text):
    m = re.search(r'viewBox="\s*0\s+0\s+(\d+)\s+(\d+)', text)
    return bool(m) and m.group(1) == "64" and bool(TILE_RECT.search(text))


def roundify(text):
    if not is_tile(text):
        return text
    text = TILE_RECT.sub(CIRCLE, text, count=1)
    # Aussparungen in Kachelfarbe gehen mit der Fläche mit
    text = re.sub(TILE, CIRCLE_FILL, text, flags=re.I)
    return ACCENTS.sub(TEXT, text)


def main(paths):
    n = 0
    for p in paths:
        p = Path(p)
        if p.suffix != ".svg" or not p.is_file():
            continue
        old = p.read_text(encoding="utf-8")
        new = roundify(old)
        if new != old:
            p.write_text(new, encoding="utf-8")
            n += 1
    print(f"Runde Symbole: {n}")


if __name__ == "__main__":
    main(sys.argv[1:])
