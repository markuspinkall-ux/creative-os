#!/usr/bin/python3
"""Fedora-Logos im System durch das Creative-OS-Logo ersetzen (läuft beim Bauen).

Fedora bleibt der Unterbau (Paketquellen, Updates), aber abgewandelte Systeme dürfen
das Fedora-Logo nicht zeigen. Ersetzt werden alle Bilddateien des Pakets fedora-logos
(gleicher Dateiname, gleiche Größe) – so bleiben alle Verweise darauf gültig.
Aufruf: debrand.py <logo-mit-schrift.png>
"""

import base64
import io
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

src = Image.open(sys.argv[1]).convert("RGBA")
full = src.crop(src.getbbox())                       # Kachel + Schriftzug
# nur die Kachel (oberer Teil bis zur ersten leeren Zeile unter ihr)
alpha = full.getchannel("A")
w, h = full.size
rows = [any(alpha.getpixel((x, y)) > 10 for x in range(0, w, 2)) for y in range(h)]
cut = next((y for y in range(10, h) if not rows[y]), h)
tile = full.crop((0, 0, w, cut))
tile = tile.crop(tile.getbbox())


def fit(img, size):
    """Bild mittig in size einpassen (transparenter Rand)."""
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    im = img.copy()
    im.thumbnail(size, Image.LANCZOS)
    out.paste(im, ((size[0] - im.width) // 2, (size[1] - im.height) // 2), im)
    return out


def svg_with(img, width, height):
    buf = io.BytesIO()
    fit(img, (max(16, int(width)), max(16, int(height)))).save(buf, "PNG")
    data = base64.b64encode(buf.getvalue()).decode()
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<image width="{width}" height="{height}" xlink:href="data:image/png;base64,{data}" '
            f'href="data:image/png;base64,{data}"/></svg>\n')


files = subprocess.run(["rpm", "-ql", "fedora-logos"], capture_output=True, text=True).stdout.split()
files += [str(p) for p in Path("/usr/share/icons/oxygen").rglob("start-here-kde-fedora.png")]
files += ["/usr/share/pixmaps/system-logo-white.png"]
done = 0
for f in files:
    p = Path(f)
    if not p.is_file() or "/anaconda/" in f:
        continue
    try:
        if p.suffix == ".png":
            with Image.open(p) as old:
                size = old.size
            wide = size[0] > size[1] * 1.3
            fit(full if wide else tile, size).save(p)
            done += 1
        elif p.suffix == ".svg":
            head = p.read_text(errors="ignore")[:3000]
            wm = re.search(r'\bwidth="([\d.]+)', head)
            hm = re.search(r'\bheight="([\d.]+)', head)
            width, height = (float(wm.group(1)) if wm else 256), (float(hm.group(1)) if hm else 256)
            wide = width > height * 1.3
            p.write_text(svg_with(full if wide else tile, round(width), round(height)))
            done += 1
    except Exception as exc:          # einzelne Datei nicht lesbar → überspringen
        print("übersprungen:", f, exc)
print(f"Fedora-Logos ersetzt: {done} Dateien")
