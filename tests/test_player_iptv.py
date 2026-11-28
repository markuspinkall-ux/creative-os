"""Player › IPTV: M3U-Listen einlesen, Senderlisten verwalten, Dateien übernehmen.

Läuft ohne Internet; ohne PySide6 wird ein Platzhalter für Qt eingesetzt,
damit die reine Logik trotzdem geprüft wird:
    python3 -m unittest tests/test_player_iptv.py
"""

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "media"))

_STUBBED = False
try:
    import PySide6.QtCore  # noqa: F401
except ImportError:
    _STUBBED = True  # nur die Logik testen – Qt-Klassen als Platzhalter
    core = types.ModuleType("PySide6.QtCore")

    class _Qt:
        class ItemDataRole:
            UserRole = 256
            DisplayRole = 0

    core.Property = lambda *a, **k: None
    core.QAbstractListModel = object
    core.QObject = object
    core.QByteArray = bytes
    core.QModelIndex = object
    core.Qt = _Qt
    core.Signal = lambda *a, **k: None
    core.Slot = lambda *a, **k: (lambda f: f)
    pyside = types.ModuleType("PySide6")
    pyside.QtCore = core
    sys.modules["PySide6"] = pyside
    sys.modules["PySide6.QtCore"] = core

from creative_media import iptv  # noqa: E402

if _STUBBED:  # Platzhalter wieder entfernen, damit andere Tests sauber „PySide6 fehlt“ erkennen
    for _name in ("PySide6", "PySide6.QtCore"):
        sys.modules.pop(_name, None)

EXTENDED = """#EXTM3U
#EXTINF:-1 tvg-name="Das Erste HD" tvg-logo="https://x/ard.png" group-title="Öffentlich-rechtlich",Das Erste HD
https://example.org/ard/master.m3u8
#EXTINF:-1 group-title="Sport",Sport 1
#EXTVLCOPT:http-user-agent=VLC
http://example.org/sport1.m3u8
#EXTINF:-1,Kaputter Eintrag
keine-adresse
"""


class ParseTest(unittest.TestCase):
    def test_extended(self):
        ch = iptv.parse_m3u(EXTENDED)
        self.assertEqual([c["name"] for c in ch], ["Das Erste HD", "Sport 1"])
        self.assertEqual(ch[0]["group"], "Öffentlich-rechtlich")
        self.assertEqual(ch[0]["logo"], "https://x/ard.png")
        self.assertEqual(ch[1]["url"], "http://example.org/sport1.m3u8")
        self.assertEqual([c["number"] for c in ch], [1, 2])

    def test_plain_list_and_extgrp(self):
        text = "﻿https://a.example/live/kanal1.m3u8\n#EXTGRP:Regional\nrtsp://b.example/stream\n"
        ch = iptv.parse_m3u(text)
        self.assertEqual(len(ch), 2)
        self.assertEqual(ch[0]["name"], "kanal1")
        self.assertEqual(ch[1]["group"], "Regional")

    def test_decode_latin1_and_bom(self):
        self.assertEqual(iptv.decode("Würzburg".encode("cp1252")), "Würzburg")
        self.assertEqual(iptv.decode(b"\xef\xbb\xbf#EXTM3U"), "#EXTM3U")

    def test_local_path(self):
        self.assertEqual(iptv.local_path("file:///home/a/Meine%20Liste.m3u"), Path("/home/a/Meine Liste.m3u"))
        self.assertEqual(iptv.local_path("/tmp/x.m3u"), Path("/tmp/x.m3u"))
        self.assertIsNone(iptv.local_path("https://example.org/x.m3u"))
        self.assertTrue(iptv.is_m3u_file("/a/B.M3U8"))
        self.assertFalse(iptv.is_m3u_file("/a/b.mp3"))


class ListsTest(unittest.TestCase):
    def test_migration_from_single_source(self):
        lists = iptv.normalize_lists([], "https://example.org/eigene.m3u", "https://default/de.m3u")
        self.assertEqual([i["source"] for i in lists], ["https://default/de.m3u", "https://example.org/eigene.m3u"])
        self.assertEqual(lists[1]["name"], "eigene")

    def test_cleans_duplicates_and_junk(self):
        stored = [{"name": "A", "source": "https://a/x.m3u"}, {"source": "https://a/x.m3u"}, "unsinn", {"name": "leer"}]
        lists = iptv.normalize_lists(stored, "https://a/x.m3u", "https://default/de.m3u")
        self.assertEqual(lists, [{"name": "A", "source": "https://a/x.m3u"}])


class CopyTest(unittest.TestCase):
    def test_copy_keeps_file_and_avoids_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "Meine Sender.m3u"
            src.write_text(EXTENDED, encoding="utf-8")
            lib = Path(tmp) / "lib"
            first = iptv.copy_into_library(src, lib)
            self.assertEqual(first.read_text(encoding="utf-8"), EXTENDED)
            self.assertEqual(iptv.copy_into_library(src, lib), first)          # gleiche Datei → kein Duplikat
            src.write_text(EXTENDED + "#EXTINF:-1,Neu\nhttp://n/1\n", encoding="utf-8")
            second = iptv.copy_into_library(src, lib)
            self.assertNotEqual(second, first)                                  # andere Datei, gleicher Name
            self.assertEqual(second.name, "Meine Sender (2).m3u")
            src.unlink()
            self.assertTrue(first.exists() and second.exists())                 # Original weg, Kopie bleibt

    def test_cache_per_source(self):
        os.environ.setdefault("XDG_CACHE_HOME", tempfile.gettempdir())
        self.assertNotEqual(iptv.cache_file("https://a/1.m3u"), iptv.cache_file("https://a/2.m3u"))


if __name__ == "__main__":
    unittest.main()
