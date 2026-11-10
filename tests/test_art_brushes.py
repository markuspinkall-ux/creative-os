"""Creative Art: Pinsel-Import (.abr/.gbr), Spitzen, Fülleimer – ohne Qt."""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "art"))
from creative_art import brushes as B  # noqa: E402


def sample_tips():
    a = B.round_tip(33, 40)
    b = np.zeros((20, 47), np.uint8)
    b[5:15, 3:44] = 200
    b[:, 20] = 255
    return [a, b]


class AbrTest(unittest.TestCase):
    def roundtrip(self, version, compress):
        tips = sample_tips()
        data = B.write_test_abr(tips, version, ["Weich", "Balken"], compress)
        parsed = B.parse_abr(data, "datei")
        self.assertEqual(len(parsed), 2)
        for (name, tip), original in zip(parsed, tips):
            self.assertEqual(tip.shape, original.shape)
            self.assertTrue(np.array_equal(tip, original), (version, compress, name))
        return [name for name, _ in parsed]

    def test_v6_names_and_pixels(self):
        for compress in (True, False):
            self.assertEqual(self.roundtrip(6, compress), ["Weich", "Balken"])

    def test_v10(self):
        self.assertEqual(self.roundtrip(10, True), ["Weich", "Balken"])

    def test_v2_names(self):
        self.assertEqual(self.roundtrip(2, True), ["Weich", "Balken"])

    def test_v1_generic_names(self):
        self.assertEqual(self.roundtrip(1, False), ["datei 1", "datei 2"])

    def test_bad_files(self):
        for data in (b"", b"\0\x09\0\0", b"\0\x06\0\x02" + b"8BIMdesc\0\0\0\0", b"\0\x02\0\x05\0\x02"):
            with self.assertRaises(B.BrushError):
                B.parse_abr(data)

    def test_packbits_runs(self):
        for row in (bytes(300), bytes(range(256)) * 2, b"\1\1\2\3\3\3" * 50, b"\7"):
            enc = B._packbits_encode(row)
            r = B._Reader(np.array([len(enc)], ">u2").tobytes() + enc)
            self.assertEqual(B._packbits(r, 1, len(row)), row)


class GbrAndTipsTest(unittest.TestCase):
    def test_gbr(self):
        tip = B.star_tip(40)
        [(name, parsed)] = B.parse_gbr(B.write_test_gbr(tip, "Stern"))
        self.assertEqual(name, "Stern")
        self.assertTrue(np.array_equal(parsed, tip))

    def test_builtin_tips(self):
        for make in [lambda: B.round_tip(64, 100), lambda: B.round_tip(64, 0), *B.BUILTIN_TIPS.values()]:
            tip = make()
            self.assertEqual(tip.dtype, np.uint8)
            self.assertGreater(tip.max(), 100)
            self.assertEqual(tip[0, 0], 0)

    def test_soft_round_is_softer(self):
        hard, soft = B.round_tip(64, 100), B.round_tip(64, 0)
        self.assertEqual(hard[32, 32], 255)
        self.assertLess(soft[32, 52], hard[32, 52])

    def test_image_to_tip(self):
        gray = np.array([[0, 255]], np.uint8)
        alpha = np.array([[255, 255]], np.uint8)
        self.assertEqual(B.image_to_tip(gray, alpha).tolist(), [[255, 0]])
        white_on_clear = B.image_to_tip(np.full((1, 2), 255, np.uint8), np.array([[255, 0]], np.uint8))
        self.assertEqual(white_on_clear.tolist(), [[255, 0]])

    def test_presets(self):
        p = B.Preset.from_dict({"name": "x", "size": 99999, "spacing": 0, "unbekannt": 1})
        self.assertEqual((p.size, p.spacing), (2500, 1))
        lib = B.load_library(B.dump_library(B.default_presets()))
        self.assertEqual([x.name for x in lib], [x.name for x in B.default_presets()])
        self.assertEqual(B.load_library("kaputt"), [])


class FloodTest(unittest.TestCase):
    def test_contiguous_fill(self):
        img = np.zeros((40, 40, 4), np.uint8)
        img[:, 20] = 255                    # Wand
        img[5, 5] = (10, 10, 10, 10)       # kleine Abweichung
        region = B.flood_region(img, 2, 2, tolerance=20)
        self.assertTrue(region[:, :20].all())
        self.assertFalse(region[:, 20:].any())
        self.assertFalse(B.flood_region(img, 2, 2, tolerance=5)[5, 5])
        self.assertTrue(B.flood_region(img, 2, 2, 0, contiguous=False)[:, 30].all())
        self.assertFalse(B.flood_region(img, -1, 2).any())

    def test_spiral_speed(self):
        img = np.zeros((400, 400, 4), np.uint8)
        for k in range(10, 200, 20):
            img[k, k:400 - k] = 255
        self.assertTrue(B.flood_region(img, 0, 0).sum() > 1000)


if __name__ == "__main__":
    unittest.main()
