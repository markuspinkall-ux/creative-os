"""KI-Bildgenerator: Prompt für 3D, Format, Dateinamen, Rechenteil – ohne Qt und ohne Grafikkarte.

    python3 -m unittest tests/test_bildgenerator.py
"""

import ast
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bildgenerator"))

import bildgen_prompt as bp  # noqa: E402


class PromptTest(unittest.TestCase):
    def test_figure_for_3d(self):
        p = bp.build_prompt("  ein Ritter   mit Schwert ", "figur", "spielfigur")
        self.assertTrue(p.startswith("single character, ein Ritter mit Schwert"))
        for part in ("full body", "A-pose", "front view", "plain light grey background", "no text"):
            self.assertIn(part, p)
        self.assertIn("game asset", p)

    def test_object_for_3d(self):
        p = bp.build_prompt("roter Sportwagen", "gegenstand")
        self.assertTrue(p.startswith("single object, roter Sportwagen"))
        self.assertIn("entire object fully visible", p)
        self.assertNotIn("A-pose", p)

    def test_free_image_untouched(self):
        self.assertEqual(bp.build_prompt("Sonnenuntergang am Meer", "frei"), "Sonnenuntergang am Meer")
        self.assertEqual(bp.build_prompt("   ", "figur"), "")

    def test_sizes(self):
        self.assertEqual(bp.size_for("figur", "quer"), (1024, 1024))      # 3D immer quadratisch
        self.assertEqual(bp.size_for("frei", "quer"), (1344, 768))
        self.assertEqual(bp.size_for("frei", "gibtsnicht"), (1024, 1024))
        for _, _, w, h in bp.SIZES:
            self.assertEqual((w % 16, h % 16), (0, 0))

    def test_safe_stem(self):
        self.assertEqual(bp.safe_stem("Größe: Über/Äpfel!"), "groesse-ueber-aepfel")
        self.assertEqual(bp.safe_stem("???"), "bild")
        self.assertLessEqual(len(bp.safe_stem("a" * 200)), 40)


class WorkerTest(unittest.TestCase):
    def test_run_py_parses_and_rejects_empty_prompt(self):
        run = ROOT / "bildgenerator" / "container" / "run.py"
        ast.parse(run.read_text(encoding="utf-8"))
        out = subprocess.run([sys.executable, str(run), "--prompt", "  "], capture_output=True, text=True,
                             env={"BILDGEN_CACHE": "/nonexistent"})
        self.assertEqual(out.returncode, 1)
        self.assertTrue(out.stdout.startswith("ERR "))

    def test_setup_script_syntax(self):
        script = ROOT / "bildgenerator" / "gibeon-bildgenerator-setup"
        self.assertEqual(subprocess.run(["sh", "-n", str(script)]).returncode, 0)

    def test_desktop_entry(self):
        text = (ROOT / "bildgenerator" / "gibeon-bildgenerator.desktop").read_text(encoding="utf-8")
        self.assertIn("Name=KI-Bildgenerator", text)
        self.assertIn("Exec=gibeon-bildgenerator", text)


if __name__ == "__main__":
    unittest.main()
