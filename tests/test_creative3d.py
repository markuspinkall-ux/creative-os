"""Tests für Creative 3D: Ersatz für torchmcubes (Achsen und Ausrichtung der Dreiecke).

python3 -m unittest tests/test_creative3d.py
Läuft nur, wenn numpy und scikit-image installiert sind.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "creative3d"))

try:
    import numpy as np
    import skimage  # noqa: F401
    HAVE = True
except ImportError:
    HAVE = False


def signed_volume(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6)


@unittest.skipUnless(HAVE, "numpy/scikit-image fehlen")
class MarchingCubes(unittest.TestCase):
    def grid(self):
        g = np.linspace(-1, 1, 48)
        return np.meshgrid(g, g, g, indexing="ij")

    def test_triangles_face_outward(self):
        from torchmcubes_shim import mc_numpy
        X, Y, Z = self.grid()
        v, f = mc_numpy(1 - (X ** 2 + Y ** 2 + Z ** 2) / 0.6, 0.0)
        self.assertGreater(len(f), 1000)
        self.assertGreater(signed_volume(v, f), 0)

    def test_axis_order_like_torchmcubes(self):
        from torchmcubes_shim import mc_numpy
        X, Y, Z = self.grid()
        v, _ = mc_numpy(1 - (X ** 2 / 0.8 ** 2 + Y ** 2 / 0.5 ** 2 + Z ** 2 / 0.3 ** 2), 0.0)
        extent = v.max(0) - v.min(0)
        self.assertEqual(int(np.argmax(extent)), 2)     # Achse 0 des Gitters → z
        self.assertEqual(int(np.argmin(extent)), 0)     # Achse 2 des Gitters → x

    def test_empty_volume(self):
        from torchmcubes_shim import mc_numpy
        v, f = mc_numpy(np.zeros((8, 8, 8)), 0.0)
        self.assertEqual((v.shape, f.shape), ((0, 3), (0, 3)))


if __name__ == "__main__":
    unittest.main()
