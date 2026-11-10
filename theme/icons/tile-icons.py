#!/usr/bin/python3
"""Setzt einfache Creative-Strichsymbole in die Graphit-Kachel der App-Symbole.

Die Shell-Symbole (24×24, nur Striche) sehen im Startmenü neben den neueren
App-Symbolen (Art, Writer, Cut …) nackt aus. Dieses Werkzeug legt sie auf
die gleiche Kachel: dunkles Rechteck mit runden Ecken und blauem Rand.

  tile-icons.py <ordner> [<ordner> …]     alle kleinen SVGs darin umwandeln (an Ort und Stelle)
  tile-icons.py --file <quelle> <ziel>    eine Datei umwandeln
  tile-icons.py --inplace <datei> …        einzelne Dateien an Ort und Stelle umwandeln

Symbole, die schon Kacheln sind (viewBox größer als 32), bleiben unverändert.
Es entsteht nur einfaches SVG (Gruppe mit transform), das auch Qt darstellen kann.
"""

import re
import sys
from pathlib import Path

TILE = '<rect x="4" y="4" width="56" height="56" rx="16" fill="#232836" stroke="#8fb3ff" stroke-width="2"/>'
INHERIT = ("fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-miterlimit",
           "fill-rule", "opacity", "style", "color")
GLYPH = 36.0                      # Kantenlänge des Symbols in der 64er-Kachel


def is_tile(svg):
    m = re.search(r'viewBox="\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)', svg)
    return bool(m) and max(float(m.group(1)), float(m.group(2))) > 32


def tile(svg):
    m = re.match(r'\s*(?:<\?xml[^>]*>\s*)?(?:<!--.*?-->\s*)*<svg\b([^>]*)>(.*)</svg>\s*$', svg, re.S)
    if not m:
        raise ValueError("kein einfaches SVG")
    attrs = dict(re.findall(r'([\w:-]+)="([^"]*)"', m.group(1)))
    box = [float(v) for v in attrs.get("viewBox", "0 0 24 24").replace(",", " ").split()]
    size = max(box[2], box[3])
    scale = GLYPH / size
    dx = 32 - (box[0] + box[2] / 2) * scale
    dy = 32 - (box[1] + box[3] / 2) * scale
    inherited = "".join(f' {k}="{attrs[k]}"' for k in INHERIT if k in attrs)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">\n'
            f'  {TILE}\n'
            f'  <g transform="translate({dx:.3f} {dy:.3f}) scale({scale:.4f})"{inherited}>{m.group(2)}</g>\n'
            '</svg>\n')


def convert(source, target):
    text = Path(source).read_text(encoding="utf-8")
    if is_tile(text):
        if Path(source) != Path(target):
            Path(target).write_text(text, encoding="utf-8")
        return False
    Path(target).write_text(tile(text), encoding="utf-8")
    return True


def main(args):
    if args[:1] == ["--file"] and len(args) == 3:
        convert(args[1], args[2])
        return 0
    changed = 0
    if args[:1] == ["--inplace"]:
        for path in args[1:]:
            try:
                changed += convert(path, path)
            except (OSError, ValueError) as error:
                print(f"übersprungen: {path} ({error})", file=sys.stderr)
        print(f"Graphit-Kacheln: {changed} Symbole umgewandelt.")
        return 0
    for folder in args:
        for path in sorted(Path(folder).glob("*.svg")):
            try:
                changed += convert(path, path)
            except (OSError, ValueError) as error:
                print(f"übersprungen: {path} ({error})", file=sys.stderr)
    print(f"Graphit-Kacheln: {changed} Symbole umgewandelt.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
