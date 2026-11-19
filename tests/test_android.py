"""Android-Apps (Waydroid): Hilfsprogramm, Startmenü und Abbild passen zusammen."""

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "android/gibeon-android-helper"


class AndroidAppsTest(unittest.TestCase):
    def test_helper_syntax(self):
        res = subprocess.run(["bash", "-n", str(HELPER)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_helper_befehle(self):
        text = HELPER.read_text(encoding="utf-8")
        for cmd in ("einrichten)", "grafik)", "gsf)", "entfernen)", '"cancel"'):
            self.assertIn(cmd, text)
        # NVIDIA: ohne Software-Darstellung bliebe Android schwarz
        self.assertIn("swiftshader", text)
        self.assertIn("waydroid0", text)          # Internet durch die Firewall

    def test_startmenue(self):
        # steht direkt im Startmenü, nicht im Ordner „Gibeon OS Suite“
        apps = (ROOT / "shell/creative_shell/apps.py").read_text(encoding="utf-8")
        suite = apps.split("SUITE = {", 1)[1].split("}", 1)[0]
        folder_out = apps.split("NOT_IN_FOLDER = {", 1)[1].split("}", 1)[0]
        self.assertNotIn("gibeon-android.desktop", suite)
        self.assertIn('"gibeon-android.desktop"', folder_out)
        self.assertIn('"gibeon-android.desktop"', (ROOT / "theme/apps/creative-apps-sync").read_text(encoding="utf-8"))
        desktop = (ROOT / "android/gibeon-android.desktop").read_text(encoding="utf-8")
        self.assertIn("Exec=gibeon-android\n", desktop)
        self.assertIn("Icon=gibeon-android\n", desktop)

    def test_abbild(self):
        cf = (ROOT / "image/Containerfile").read_text(encoding="utf-8")
        for part in ("dnf install -y waydroid", "/usr/libexec/gibeon-android-helper", "/usr/bin/gibeon-android",
                     "org.creativeos.android.policy", "gibeon-android.desktop", "gibeon-android --selftest"):
            self.assertIn(part, cf)
        policy = (ROOT / "android/org.creativeos.android.policy").read_text(encoding="utf-8")
        self.assertIn("/usr/libexec/gibeon-android-helper", policy)

    def test_symbole(self):
        for d in ("icons", "icons-light"):
            self.assertTrue((ROOT / f"shell/creative_shell/qml/Creative/{d}/android.svg").is_file())


if __name__ == "__main__":
    unittest.main()
