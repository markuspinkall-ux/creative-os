"""Prüfung der Foto-Projektion (Creative 3D) an einer Ellipsoid-Figur – ohne Grafikkarte.

  python3 tools/foto-projektion-test.py [ausgabeordner] [unterteilung]
"""
import sys, time
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "creative3d" / "trellis"))
sys.path.insert(0, "/opt/creative")
from foto_projektion import project_photo

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp")
FEIN = int(sys.argv[2]) if len(sys.argv) > 2 else 1
OUT.mkdir(parents=True, exist_ok=True)

def ellipsoid(a=1.0, b=1.6, c=0.5, nu=96, nv=64):
    th = np.linspace(0, np.pi, nv)        # von oben nach unten
    ph = np.linspace(-np.pi, np.pi, nu)
    T, P = np.meshgrid(th, ph, indexing="ij")
    x = a * np.sin(T) * np.sin(P); y = b * np.cos(T); z = c * np.sin(T) * np.cos(P)
    V = np.stack([x, y, z], -1).reshape(-1, 3)
    UV = np.stack([(P + np.pi) / (2 * np.pi), 1 - T / np.pi], -1).reshape(-1, 2)
    F = []
    for i in range(nv - 1):
        for j in range(nu - 1):
            k = i * nu + j
            F += [[k, k + nu, k + 1], [k + 1, k + nu, k + nu + 1]]
    F = np.array(F)
    N = V / np.array([a * a, b * b, c * c]); N /= np.linalg.norm(N, axis=1, keepdims=True)
    return V, F, UV, N

V, F, UV, N = ellipsoid(nu=96 * FEIN, nv=64 * FEIN)
SIZE = 512 * FEIN if FEIN > 1 else 512
tex = Image.new("RGB", (SIZE, SIZE), (128, 128, 128))
print("Dreiecke:", len(F), "Textur:", SIZE)
# Foto: Blick von +Z, rechts im Bild = +X; linke Hälfte rot, rechte blau
photo = Image.new("RGBA", (518, 518), (0, 0, 0, 0))
d = ImageDraw.Draw(photo)
cx, cy, sx, sy = 259, 259, 140, 224
d.ellipse([cx - sx, cy - sy, cx + sx, cy + sy], fill=(220, 30, 30, 255))
d.pieslice([cx - sx, cy - sy, cx + sx, cy + sy], -90, 90, fill=(30, 30, 220, 255))
t = time.time()
new, info = project_photo(V, F, UV, N, tex, photo)
print(info, round(time.time() - t, 1), "s")
arr = np.asarray(new)
def col(p):
    i = np.argmin(np.linalg.norm(V - p, axis=1)); u, v = UV[i]
    return arr[int((1 - v) * (SIZE - 1)), int(u * (SIZE - 1))]
a, b, c = col([0.6, 0, 0.4]), col([-0.6, 0, 0.4]), col([0, 0, -0.5])
print("vorne rechts:", a, "vorne links:", b, "hinten:", c)
assert info["projiziert"] and info["ansicht"] == "vorne"
assert a[2] > 180 and a[0] < 80, "rechts soll blau sein"
assert b[0] > 180 and b[2] < 80, "links soll rot sein"
assert abs(int(c[0]) - 128) < 3, "Rückseite soll unverändert sein"
new.save(OUT / "projektion-textur.png")
photo.save(OUT / "projektion-foto.png")
# Figur um 180° gedreht, Textur kennt schon grob die Farben → muss „hinten“ wählen
R = np.diag([-1, 1, -1.0])
blurred = new.resize((64, 64)).resize((SIZE, SIZE))
new2, info2 = project_photo(V @ R.T, F, UV, N @ R.T, blurred, photo)
print(info2)
assert info2["ansicht"] == "hinten", "gedrehte Figur: Rückseite muss erkannt werden"
# Foto passt nicht zur Form → nichts verändern
flach = Image.new("RGBA", (518, 518), (0, 0, 0, 0))
ImageDraw.Draw(flach).rectangle([20, 230, 498, 290], fill=(0, 200, 0, 255))
_, info3 = project_photo(V, F, UV, N, tex, flach)
assert not info3["projiziert"], info3
print("Foto-Projektion: Prüfung bestanden")
