"""Tests für Creative 3D: Ersatz für torchmcubes und Skelett (Vorlage, Gewichte, GLB mit Skin).

python3 -m unittest tests/test_creative3d.py
Marching Cubes braucht numpy und scikit-image, das Skelett nur numpy.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "creative3d"))

try:
    import numpy as np
    HAVE = True
except ImportError:
    HAVE = False
try:
    import skimage  # noqa: F401
    HAVE_SKIMAGE = HAVE
except ImportError:
    HAVE_SKIMAGE = False


def signed_volume(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6)


@unittest.skipUnless(HAVE_SKIMAGE, "numpy/scikit-image fehlen")
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


try:
    import creative3d_rig as R
except ImportError:
    R = None


def stick_figure(t_pose=False):
    """Einfache Punktwolke in Menschenform (Y oben, 2 m hoch)."""
    pts = []
    def line(a, b, n=80, r=0.06):
        a, b = np.array(a), np.array(b)
        for t in np.linspace(0, 1, n):
            c = a + t * (b - a)
            for ang in np.linspace(0, 2 * np.pi, 8, endpoint=False):
                pts.append(c + [r * np.cos(ang), 0, r * np.sin(ang)])
    line((0, 1.0, 0), (0, 1.85, 0), r=0.15)
    for s in (1, -1):
        line((s * 0.1, 0.0, 0), (s * 0.1, 0.98, 0))
        line((s * 0.3, 1.58, 0), (s * 0.9, 1.58, 0)) if t_pose else line((s * 0.3, 1.58, 0), (s * 0.4, 0.95, 0))
    return np.array(pts)


@unittest.skipUnless(HAVE and R, "numpy fehlt")
class Skeleton(unittest.TestCase):
    def test_template_follows_pose(self):
        down = R.fit_template(stick_figure(False))
        tpose = R.fit_template(stick_figure(True))
        self.assertLess(down["LeftHand"][1], down["LeftArm"][1] - 0.3)          # Arme hängen
        self.assertAlmostEqual(tpose["LeftHand"][1], tpose["LeftArm"][1], 2)    # Arme waagerecht
        self.assertGreater(tpose["LeftHand"][0], 0.7)
        self.assertLess(down["RightHand"][0], 0)                                # rechts = −X

    def test_weights_stay_on_their_side(self):
        v = stick_figure(False)
        joints = R.fit_template(v)
        idx, w = R.skin_weights(v, joints)
        self.assertTrue(np.allclose(w.sum(1), 1, atol=1e-5))
        left_arm = v[:, 0] > 0.33
        names = np.array(R.NAMES)[idx[left_arm, 0]]
        self.assertTrue(all(n.startswith("Left") for n in names))

    def test_glb_with_skin_and_animation(self):
        import tempfile, os
        v = stick_figure(False)
        faces = np.array([[i, i + 1, i + 2] for i in range(0, len(v) - 3, 3)])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "f.glb")
            R.write_glb(path, v, faces, np.full((len(v), 3), 200, np.uint8), None,
                        R.fit_template(v), R.probe_animation())
            gltf, binary = R.read_glb(path)
        self.assertEqual(len(gltf["skins"][0]["joints"]), len(R.NAMES))
        self.assertTrue(all(gltf["nodes"][j]["name"].startswith("mixamorig:") for j in gltf["skins"][0]["joints"]))
        self.assertEqual(gltf["animations"][0]["name"], "Winken")
        attrs = gltf["meshes"][0]["primitives"][0]["attributes"]
        self.assertTrue({"POSITION", "COLOR_0", "JOINTS_0", "WEIGHTS_0"} <= set(attrs))
        self.assertEqual(gltf["buffers"][0]["byteLength"], len(binary))
        for view in gltf["bufferViews"]:
            self.assertEqual(view["byteOffset"] % 4, 0)

    def test_glb_without_skeleton(self):
        import tempfile, os
        v = stick_figure(False)
        faces = np.array([[0, 1, 2]])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "f.glb")
            R.write_glb(path, v, faces)
            gltf, _ = R.read_glb(path)
        self.assertNotIn("skins", gltf)
        self.assertEqual(len(gltf["nodes"]), 1)
