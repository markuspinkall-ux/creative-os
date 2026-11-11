"""Design Graphit/Porzellan: Einstellungen lesen/schreiben, Paletten, erzeugte Dateien aktuell."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shell"))
from creative_shell import look  # noqa: E402


class LookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XDG_CONFIG_HOME"] = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("XDG_CONFIG_HOME", None)

    def test_default_and_write(self):
        self.assertEqual(look.read(), ("graphit", "blau"))
        self.assertEqual(look.write("porzellan"), ("porzellan", "blau"))
        self.assertEqual(look.write(accent="lila"), ("porzellan", "lila"))
        self.assertEqual(look.write("quatsch", "pink"), ("porzellan", "lila"))
        text = look.path().read_text()
        self.assertIn("[Look]", text)
        self.assertIn("design=porzellan", text)
        self.assertTrue(look.is_light())

    def test_palette(self):
        dark = look.palette({"ground": "x", "eigene": "y"})
        self.assertEqual(dark, {"ground": "#12151b", "eigene": "y"})
        look.write("porzellan", "gruen")
        pal = look.palette()
        self.assertEqual((pal["ground"], pal["text"], pal["accent"], pal["accentText"]),
                         ("#e9eef6", "#1c2433", "#1f9e7f", "#ffffff"))

    def test_default_wallpaper(self):
        qml = ROOT / "shell/creative_shell/qml"
        self.assertEqual(look.default_wallpaper(qml).name, "graphit.svg")
        look.write("porzellan")
        self.assertEqual(look.default_wallpaper(qml).name, "porzellan.svg")

    def test_generated_files_current(self):
        res = subprocess.run([sys.executable, str(ROOT / "tools/porzellan.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stdout)
        icons = sorted(p.name for p in (ROOT / "shell/creative_shell/qml/Creative/icons").glob("*.svg"))
        light = sorted(p.name for p in (ROOT / "shell/creative_shell/qml/Creative/icons-light").glob("*.svg"))
        self.assertEqual(icons, light)


if __name__ == "__main__":
    unittest.main()
