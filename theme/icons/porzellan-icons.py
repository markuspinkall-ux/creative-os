#!/usr/bin/python3
"""Baut das Symbol-Design „CreativePorzellan“ aus „Creative“ (Graphit): helle Kachel,
dunkle Striche, ohne Blau – Kachelrand hellgrau, Akzente schiefergrau (passend zu Porzellan).

  porzellan-icons.py <Orbit-Theme-Ordner> <Ziel-Theme-Ordner> [<weitere SVGs …>]

Weitere SVGs (z. B. /usr/share/icons/hicolor/scalable/apps/creative-*.svg) kommen ebenfalls
umgefärbt ins Ziel – so gewinnen sie dort vor hicolor.
Die Farben entsprechen den hellen Shell-Symbolen (Creative/icons-light).
"""

import re
import shutil
import sys
from pathlib import Path

# Graphit → Porzellan (wie icons → icons-light, dazu die Kachelfarben)
MAP = {
    "#232836": "#edf0f5",   # runde Fläche (früher Kachel): zartes Grau
    "#1c2029": "#eef2f8",
    "#dce6ff": "#1c2433",   # Striche/Schrift
    "#12151b": "#e9eef6",   # Aussparungen auf Akzentflächen
    "#8fb3ff": "#5b6576",   # Akzent im Symbol: schiefergrau statt Blau
    "#ffb07a": "#d9773a",
    "#6fdcc0": "#1f9e7f",
    "#dce2ec": "#2a3448",
}
PATTERN = re.compile("|".join(re.escape(k) for k in MAP), re.I)


# Kachelrand (Rechteck mit Kachelfarbe): hellgrau statt Blau
TILE_EDGE = "#d3d9e3"
TILE_RECT = re.compile(r'<rect\b[^>]*fill="#232836"[^>]*>', re.I)


def recolor(text):
    text = TILE_RECT.sub(lambda m: re.sub(r'stroke="#8fb3ff"', f'stroke="{TILE_EDGE}"', m.group(0), flags=re.I), text)
    return PATTERN.sub(lambda m: MAP[m.group(0).lower()], text)


def main(src, dst, extra):
    src, dst = Path(src), Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    index = dst / "index.theme"
    text = index.read_text(encoding="utf-8")
    text = re.sub(r"^Name=.*$", "Name=Porzellan", text, flags=re.M)
    text = re.sub(r"^Comment=.*$", "Comment=Symbole von Gibeon OS im hellen Design", text, flags=re.M)
    text = re.sub(r"^Inherits=.*$", "Inherits=breeze,hicolor", text, flags=re.M)
    index.write_text(text, encoding="utf-8")
    apps = dst / "apps" / "scalable"
    count = 0
    for svg in apps.glob("*.svg"):
        svg.write_text(recolor(svg.read_text(encoding="utf-8")), encoding="utf-8")
        count += 1
    for f in extra:
        f = Path(f)
        if f.suffix == ".svg" and f.is_file():
            (apps / f.name).write_text(recolor(f.read_text(encoding="utf-8")), encoding="utf-8")
            count += 1
    (dst / "icon-theme.cache").unlink(missing_ok=True)
    print(f"Porzellan-Symbole: {count}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
