#!/usr/bin/python3
"""Erzeugt die hellen „Porzellan“-Fassungen aus den Graphit-Dateien (Farbtausch).

  python3 tools/porzellan.py          – alle Dateien neu erzeugen
  python3 tools/porzellan.py --check  – nur prüfen, ob sie aktuell sind (für Tests)

Erzeugt: Symbole (icons-light/), GTK-CSS (gtk-light.css), KDE-Farbschema
(CreativePorzellan.colors), Konsole-Farbschema/-Profil, heller Hintergrund (porzellan.svg).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CREATIVE = ROOT / "shell/creative_shell/qml/Creative"

# Graphit → Porzellan
HEX = {
    "#12151b": "#e9eef6", "#171a22": "#f4f6fa", "#171b22": "#f4f6fa", "#1c2029": "#ffffff",
    "#232836": "#eef1f6", "#161920": "#ffffff", "#2c3242": "#d9dfe9", "#2a303d": "#d9dfe9",
    "#3a4252": "#cdd5e2", "#dce6ff": "#1c2433", "#9aa6c4": "#5d6884", "#6f7a92": "#8a93a8",
    "#8fb3ff": "#3d6fe0", "#a6c3ff": "#2f5fcf", "#a3c1ff": "#2f5fcf", "#6fdcc0": "#1f9e7f",
    "#ffb07a": "#d9773a", "#ff8a8e": "#d23c45", "#dce2ec": "#2a3448", "#23304a": "#dfe8fb",
}


def swap_hex(text, mapping=HEX):
    def repl(m):
        low = m.group(0).lower()
        return mapping.get(low, m.group(0))
    return re.sub(r"#[0-9a-fA-F]{6}\b", repl, text)


def swap_rgba(text):
    # helle Schleier → dunkle Schleier
    return re.sub(r"rgba\(\s*255\s*,\s*255\s*,\s*255\s*,", "rgba(20, 30, 50,", text)


def rgb_triplets():
    out = {}
    for a, b in HEX.items():
        ta = ",".join(str(int(a[i:i + 2], 16)) for i in (1, 3, 5))
        tb = ",".join(str(int(b[i:i + 2], 16)) for i in (1, 3, 5))
        out[ta] = tb
    return out


def swap_triplets(text):
    table = rgb_triplets()
    table.update({"18,21,27": "233,238,246", "28,32,41": "255,255,255", "35,40,54": "238,241,246",
                  "220,230,255": "28,36,51", "140,150,175": "93,104,132", "255,255,255": "28,36,51",
                  "186,198,223": "70,80,100", "143,179,255": "61,111,224", "111,220,192": "31,158,127",
                  "255,176,122": "217,119,58", "23,27,34": "244,246,250", "22,25,32": "255,255,255"})
    return re.sub(r"(?<=[=,])?(\d{1,3},\d{1,3},\d{1,3})(?=\s*$)",
                  lambda m: table.get(m.group(1), m.group(1)), text, flags=re.M)


def outputs():
    files = {}
    icons = CREATIVE / "icons"
    for svg in sorted(icons.glob("*.svg")):
        files[CREATIVE / "icons-light" / svg.name] = swap_hex(svg.read_text())
    gtk = ROOT / "theme/gtk/gtk.css"
    css = swap_rgba(swap_hex(gtk.read_text()))
    css = css.replace("/* Creative OS – Graphit", "/* Creative OS – Porzellan", 1)
    files[ROOT / "theme/gtk/gtk-light.css"] = css
    colors = (ROOT / "theme/CreativeGraphit.colors").read_text()
    colors = swap_triplets(colors).replace("Name=Creative Graphit", "Name=Creative Porzellan") \
        .replace("ColorScheme=CreativeGraphit", "ColorScheme=CreativePorzellan")
    files[ROOT / "theme/CreativePorzellan.colors"] = colors
    kon = (ROOT / "theme/konsole/CreativeGraphit.colorscheme").read_text()
    kon = swap_triplets(kon).replace("Description=Creative Graphit", "Description=Creative Porzellan")
    files[ROOT / "theme/konsole/CreativePorzellan.colorscheme"] = kon
    prof = (ROOT / "theme/konsole/CreativeGraphit.profile").read_text()
    prof = prof.replace("ColorScheme=CreativeGraphit", "ColorScheme=CreativePorzellan") \
        .replace("Name=Creative Graphit", "Name=Creative Porzellan") \
        .replace("CustomCursorColor=143,179,255", "CustomCursorColor=61,111,224") \
        .replace("CustomCursorTextColor=18,21,27", "CustomCursorTextColor=255,255,255")
    files[ROOT / "theme/konsole/CreativePorzellan.profile"] = prof
    wall = (CREATIVE / "wallpapers/graphit.svg").read_text()
    files[CREATIVE / "wallpapers-light/porzellan.svg"] = wall_light(wall)
    return files


def wall_light(svg):
    """Heller Tag-Himmel: Hintergrundfarben aufhellen, Planet und Rakete bleiben."""
    def lighten(m):
        h = m.group(0)
        r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
        lum = (0.299 * r + 0.587 * g + 0.114 * b)
        if lum < 90:           # dunkle Himmelsflächen → helles Blaugrau
            base = (232, 238, 249)
            r, g, b = (int(bc - (90 - lum) * 0.25 + (c - lum) * 0.9) for bc, c in zip(base, (r, g, b)))
            r, g, b = (max(0, min(255, c)) for c in (r, g, b))
            return f"#{r:02x}{g:02x}{b:02x}"
        return h
    return re.sub(r"#[0-9a-fA-F]{6}\b", lighten, svg)


def main():
    check = "--check" in sys.argv
    stale = []
    for path, text in outputs().items():
        if check:
            if not path.exists() or path.read_text() != text:
                stale.append(str(path.relative_to(ROOT)))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    if check and stale:
        print("Veraltet (python3 tools/porzellan.py ausführen):", *stale, sep="\n  ")
        return 1
    if not check:
        print("Porzellan-Dateien erzeugt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
