"""Tests für Creative 3D: Skelett (Vorlage, Gewichte, GLB mit Skin).

python3 -m unittest tests/test_creative3d.py   (braucht numpy)
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
