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

    def test_themed(self):
        css = "background:#12151b; color:#DCE6FF; border:1px solid rgba(255,255,255,0.1); a:#8fb3ff; x:#123456"
        self.assertEqual(look.themed(css), css)            # Graphit + Blau: unverändert
        look.write("porzellan", "blau")
        out = look.themed(css)
        self.assertIn("#e9eef6", out)
        self.assertIn("#1c2433", out)
        self.assertIn("rgba(28,36,51,0.1)", out)
        self.assertIn("#3d6fe0", out)
        self.assertIn("#123456", out)                      # unbekannte Farben bleiben
        look.write("graphit", "gruen")
        self.assertEqual(look.themed("#8fb3ff"), "#6fdcc0")
        self.assertEqual(look.themed(None), None)

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
