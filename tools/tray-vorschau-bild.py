"""Setzt die einzeln fotografierten Shell-Flächen (Hintergrund, obere Leiste, Taskleiste) zu einem
Bild zusammen: tray-<pos>-1.png … → tray-<pos>.png. Größte = Hintergrund, Breite gleich: Leisten."""
import glob
import sys

from PIL import Image

base = sys.argv[1]
parts = [Image.open(p).convert("RGBA") for p in sorted(glob.glob(base + "-*.png"))]
bg = max(parts, key=lambda im: im.width * im.height)
out = bg.copy()
bars = [im for im in parts if im is not bg and im.width == bg.width]
bars.sort(key=lambda im: im.height)
# niedrigste = obere Leiste (50 px), höhere = Taskleiste (unten)
for im in bars:
    y = 0 if im.height <= 50 else bg.height - im.height
    out.alpha_composite(im, (0, y))
out.convert("RGB").save(base + ".png")
print("zusammengesetzt:", base + ".png", [im.size for im in parts])
