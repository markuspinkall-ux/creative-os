"""Dateien › „Öffnen mit“: Apps finden, Standard-App, Exec-Zeile – ohne Qt.

    python3 -m unittest tests/test_oeffnen_mit.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "files"))

from creative_files import openwith  # noqa: E402

APPS = {
    "creative-writer.desktop": """[Desktop Entry]
Type=Application
Name=Creative Writer
Name[de]=Writer
Exec=creative-writer %F
Icon=creative-writer
MimeType=application/vnd.openxmlformats-officedocument.wordprocessingml.document;text/plain;
""",
    "creative-notes.desktop": """[Desktop Entry]
Type=Application
Name=Notizen
Exec=creative-notes %f
MimeType=text/plain;text/markdown;
""",
    "org.gimp.GIMP.desktop": """[Desktop Entry]
Type=Application
Name=GIMP
Exec=gimp %U
MimeType=image/*;
""",
    "creative-pictures.desktop": """[Desktop Entry]
Type=Application
Name=Bilder
Exec=creative-pictures %f
NoDisplay=true
MimeType=image/png;image/jpeg;
""",
    "versteckt.desktop": """[Desktop Entry]
Type=Application
Name=Versteckt
Exec=x %f
Hidden=true
""",
    "nur-gnome.desktop": """[Desktop Entry]
Type=Application
Name=Nur GNOME
Exec=x %f
OnlyShowIn=GNOME;
""",
    "ohne-datei.desktop": """[Desktop Entry]
Type=Application
Name=Rechner
Exec=calc
""",
    "terminal-app.desktop": """[Desktop Entry]
Type=Application
Name=Vim
Exec=vim %F
Terminal=true
""",
}


class OpenWithTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.data = root / "share"
        (self.data / "applications").mkdir(parents=True)
        for name, text in APPS.items():
            (self.data / "applications" / name).write_text(text, encoding="utf-8")
        self.env = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(root / "config"),
                                                "XDG_CONFIG_DIRS": str(root / "etc"), "LANG": "de_DE.UTF-8"})
        self.env.start()
        self.dirs = [self.data]

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_finds_and_filters(self):
        apps = openwith.installed_apps(self.dirs)
        self.assertEqual(apps["creative-writer.desktop"].name, "Writer")
        self.assertNotIn("versteckt.desktop", apps)
        self.assertNotIn("nur-gnome.desktop", apps)

    def test_text_file(self):
        res = openwith.apps_for(["text/plain"], dirs=self.dirs)
        names = [a["name"] for a in res["recommended"]]
        self.assertEqual(set(names), {"Writer", "Notizen"})
        others = [a["name"] for a in res["others"]]
        self.assertIn("GIMP", others)
        self.assertNotIn("Rechner", others)          # nimmt keine Datei an
        self.assertNotIn("Vim", others)              # Terminal-App
        self.assertNotIn("Bilder", others)           # versteckt und passt nicht

    def test_image_wildcard_and_hidden_handler(self):
        res = openwith.apps_for(["image/png", "application/octet-stream"], dirs=self.dirs)
        names = [a["name"] for a in res["recommended"]]
        self.assertEqual(names[0], "Bilder")         # genauer Treffer und eigene App vor GIMP
        self.assertIn("GIMP", names)

    def test_set_default(self):
        openwith.set_default("text/plain", "creative-notes.desktop")
        res = openwith.apps_for(["text/plain"], dirs=self.dirs)
        self.assertEqual(res["recommended"][0]["name"], "Notizen")
        self.assertTrue(res["recommended"][0]["isDefault"])
        openwith.set_default("text/plain", "creative-writer.desktop")
        text = (Path(os.environ["XDG_CONFIG_HOME"]) / "mimeapps.list").read_text()
        self.assertIn("text/plain=creative-writer.desktop;", text)
        self.assertIn("creative-writer.desktop;creative-notes.desktop;", text)

    def test_exec_args(self):
        apps = openwith.installed_apps(self.dirs)
        f = str(Path(self.tmp.name) / "Mein Brief.docx")
        self.assertEqual(openwith.exec_args(apps["creative-writer.desktop"], [f]), ["creative-writer", f])
        uri = openwith.exec_args(apps["org.gimp.GIMP.desktop"], [f])
        self.assertTrue(uri[1].startswith("file://") and uri[1].endswith("Mein%20Brief.docx"))
        self.assertEqual(openwith.exec_args(apps["ohne-datei.desktop"], [f]), ["calc", f])
        self.assertEqual(openwith.exec_args(apps["terminal-app.desktop"], [f])[:3], ["x-terminal-emulator", "-e", "vim"])


if __name__ == "__main__":
    unittest.main()
