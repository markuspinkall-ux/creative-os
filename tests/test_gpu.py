"""Systemsteuerung › Grafikkarte: Werte lesen und Beleuchtung erkennen."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "settings"))
from creative_settings import gpu  # noqa: E402

OPENRGB = """0: ASUS ROG STRIX RTX 3060
  Type:           GPU
  Description:    ASUS Aura GPU Device
  Location:       I2C: /dev/i2c-3, address 0x67
  Modes: [Direct] Static Breathing Flashing 'Spectrum Cycle' Rainbow
  Zones: 'GPU'
1: Corsair K70
  Type:           Keyboard
  Modes: Direct Static
"""


class Grafikkarte(unittest.TestCase):
    def test_nvidia_smi(self):
        g = gpu.parse_nvsmi("NVIDIA GeForce RTX 3060, 12288, 1024, 580.95.05, 45, 7, 23.45, 170.00, 210, 2100, 405, 30, 4, 16, 94.06.2F.00.9A")
        self.assertEqual(g["name"], "NVIDIA GeForce RTX 3060")
        self.assertEqual(g["vramMb"], 12288)
        self.assertEqual(g["pcie"], "PCIe 4.0 x16")
        self.assertEqual(g["fan"], 30)
        n = gpu.parse_nvsmi("NVIDIA GeForce RTX 4060 Laptop GPU, 8188, 5, 580.1, 40, 0, [N/A], [N/A], 210, 2370, 405, [N/A], 4, 8, [N/A]")
        self.assertIsNone(n["fan"])
        self.assertEqual(n["bios"], "")
        self.assertIsNone(gpu.parse_nvsmi("kaputt"))

    def test_abzeichen(self):
        self.assertEqual(gpu.series("NVIDIA GeForce RTX 3060"), ("GeForce RTX", "3060"))
        self.assertEqual(gpu.series("AMD Radeon RX 7800 XT"), ("Radeon RX", "7800 XT"))
        self.assertEqual(gpu.series("Intel Arc A770"), ("Arc", "A770"))

    def test_openrgb(self):
        devs = gpu.parse_openrgb(OPENRGB)
        self.assertEqual(len(devs), 1)
        self.assertEqual(devs[0]["index"], 0)
        self.assertIn("spectrum cycle", devs[0]["modes"])
        self.assertIn("direct", devs[0]["modes"])
        self.assertEqual(gpu.parse_openrgb(""), [])


class MikrofonLicht(unittest.TestCase):
    def test_hyperx_erkennen(self):
        import tempfile
        from creative_settings import mikro_rgb
        with tempfile.TemporaryDirectory() as d:
            for name, maker, product in (("1-3", "HP, Inc", "HyperX QuadCast S"), ("1-4", "HyperX", "DuoCast"),
                                         ("1-5", "Logitech", "C920"), ("1-6", "Kingston", "HyperX Alloy")):
                p = Path(d) / name
                p.mkdir()
                (p / "manufacturer").write_text(maker)
                (p / "product").write_text(product)
            self.assertEqual(sorted(mikro_rgb.hyperx_mics(d)), ["HyperX DuoCast", "HyperX QuadCast S"])

    def test_openrgb_mikrofon(self):
        from creative_settings import mikro_rgb
        text = OPENRGB + "2: HyperX Quadcast S\n  Type:           Microphone\n  Modes: [Direct] Static Breathing Rainbow\n"
        devs = gpu.parse_openrgb(text, "microphone")
        self.assertEqual([d["name"] for d in devs], ["HyperX Quadcast S"])
        self.assertEqual([m["label"] for m in mikro_rgb.modes_for(devs[0])], ["Statisch", "Atmen", "Regenbogen", "Aus"])


if __name__ == "__main__":
    unittest.main()


class MikroQuadcastTests(unittest.TestCase):
    def test_befehle(self):
        from creative_settings import mikro_rgb as m
        self.assertEqual(m.quadcast_args("static", "#4C0099"), ["-a", "solid", "4c0099"])
        self.assertEqual(m.quadcast_args("direct", "#ff6000"), ["-a", "solid", "ff6000"])
        self.assertEqual(m.quadcast_args("off", "#ff6000"), ["-a", "solid", "0"])
        self.assertEqual(m.quadcast_args("rainbow", "#ff6000"), ["-a", "wave"])

    def test_duocast_erkannt(self):
        import tempfile, pathlib
        from unittest import mock
        from creative_settings import mikro_rgb as m
        with tempfile.TemporaryDirectory() as d:
            dev = pathlib.Path(d) / "1-4"
            dev.mkdir()
            (dev / "idVendor").write_text("03f0\n")
            (dev / "idProduct").write_text("098c\n")
            with mock.patch.object(m.shutil, "which", return_value="/usr/bin/quadcastrgb"):
                self.assertTrue(m.quadcast_ready(d))
            (dev / "idProduct").write_text("1234\n")
            with mock.patch.object(m.shutil, "which", return_value="/usr/bin/quadcastrgb"):
                self.assertFalse(m.quadcast_ready(d))
