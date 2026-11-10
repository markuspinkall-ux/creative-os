"""Creative 3D: Ausweich-Vorschau ohne Grafikkarte."""

import sys
import time
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "creative3d"))
import creative3d_softview as sv  # noqa: E402


class SoftViewTest(unittest.TestCase):
    def test_sphere_is_filled_and_lit(self):
        v, f = sv.uv_sphere()
        mesh = sv.Mesh(v, f)
        img = mesh.render(200)
        alpha = img[:, :, 3] > 0
        self.assertTrue(alpha[100, 100])
        self.assertFalse(alpha[2, 2])
        filled = alpha.sum() / (np.pi * (200 * .44) ** 2)
        self.assertGreater(filled, .93)                     # kaum Lücken
        # Licht von links oben: links oben heller als rechts unten
        self.assertGreater(img[70, 70, :3].mean(), img[130, 130, :3].mean())

    def test_colors_and_rotation(self):
        v, f = sv.uv_sphere(20, 30)
        colors = np.zeros((len(v), 4), np.uint8)
        colors[:, 0] = 255
        colors[v[:, 0] > 0, :3] = (0, 0, 255)               # rechte Hälfte blau
        mesh = sv.Mesh(v, f, colors=colors)
        front = mesh.render(160, yaw=0, pitch=0)
        self.assertGreater(front[80, 120, 2], front[80, 120, 0])   # rechts blau
        self.assertGreater(front[80, 40, 0], front[80, 40, 2])     # links rot
        turned = mesh.render(160, yaw=180, pitch=0)
        self.assertGreater(turned[80, 40, 2], turned[80, 40, 0])  # umgedreht

    def test_speed_large_mesh(self):
        v, f = sv.uv_sphere(220, 400)                       # ~176 000 Dreiecke
        mesh = sv.Mesh(v, f)
        start = time.time()
        mesh.render(520, fast=True)
        self.assertLess(time.time() - start, 1.5)

    def test_without_faces_or_normals(self):
        mesh = sv.Mesh(np.random.default_rng(1).normal(size=(500, 3)), None)
        self.assertEqual(mesh.render(64).shape, (64, 64, 4))
        with self.assertRaises(ValueError):
            sv.Mesh(np.zeros((0, 3)), None)


if __name__ == "__main__":
    unittest.main()
